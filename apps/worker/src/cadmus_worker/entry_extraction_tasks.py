"""Celery entrypoint for AI-driven entry field extraction (BH-148), kept
separate from ``article_schema_tasks.py`` -- extracting one entry's fields
against an already-active schema is a different capability from generating
that schema in the first place.

BH-148 experimental variant 1: fields are extracted from word-level ALTO
segmentation of each fragment's own page region (cropped in memory, never
persisted -- see ``cadmus.infrastructure.ocr.crop_region``) rather than from
the fragment's flat ``recognized_text``, so the AI picks contiguous OCR
words instead of guessing character offsets, and every extracted field gets
a real bounding box.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, cast
from uuid import UUID, uuid4

from cadmus.config import Settings
from cadmus.infrastructure.ai_schema import (
    AiSchemaProviderError,
    AnthropicAiSchemaProvider,
)
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.lexicography import (
    create_lexicography_unit_of_work_factory,
)
from cadmus.infrastructure.object_storage import create_object_storage
from cadmus.infrastructure.ocr import OcrExecutionError, TesseractAltoOcrProvider
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.lexicography import (
    EXTRACT_ENTRY_FIELDS_TASK_NAME,
    EntryField,
    EntryFieldOrigin,
    EntryFragment,
    EntryStatus,
    FragmentSegment,
    LexicographyUnitOfWorkFactory,
    RuleBasedAnnotationService,
    resolve_ocr_language,
)
from cadmus.sources import ObjectNotFoundError, ObjectStorage, SourcesUnitOfWorkFactory
from celery import Task

from cadmus_worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_PAGE_IMAGE_SPOOL_MAX_BYTES = 8 * 1024 * 1024


def _log_task_event(event: str, task_id: str, **fields: object) -> None:
    logger.info(
        json.dumps({"event": event, "task_id": task_id, **fields}, sort_keys=True)
    )


@dataclass(frozen=True)
class _EntryExtractionDependencies:
    lexicography_unit_of_work_factory: LexicographyUnitOfWorkFactory
    sources_unit_of_work_factory: SourcesUnitOfWorkFactory
    object_storage: ObjectStorage
    ocr_provider: TesseractAltoOcrProvider
    ai_schema_provider: AnthropicAiSchemaProvider
    annotation_service: RuleBasedAnnotationService


@lru_cache(maxsize=1)
def _entry_extraction_dependencies() -> _EntryExtractionDependencies:
    settings = Settings()
    engine = create_database_engine(settings)
    api_key = settings.anthropic_api_key
    sources_unit_of_work_factory: SourcesUnitOfWorkFactory = (
        create_sources_unit_of_work_factory(engine)
    )
    lexicography_unit_of_work_factory = create_lexicography_unit_of_work_factory(engine)
    return _EntryExtractionDependencies(
        lexicography_unit_of_work_factory=lexicography_unit_of_work_factory,
        sources_unit_of_work_factory=sources_unit_of_work_factory,
        object_storage=create_object_storage(settings),
        ocr_provider=TesseractAltoOcrProvider(
            timeout_seconds=settings.ocr_task_timeout_seconds
        ),
        ai_schema_provider=AnthropicAiSchemaProvider(
            api_key=api_key.get_secret_value() if api_key is not None else "",
            model=settings.ai_schema_model,
            timeout_seconds=settings.ai_schema_timeout_seconds,
        ),
        annotation_service=RuleBasedAnnotationService(
            lexicography_unit_of_work_factory, sources_unit_of_work_factory
        ),
    )


def _fragment_boxes(
    fragment: EntryFragment,
) -> list[tuple[float, float, float, float]]:
    boxes = [(fragment.x, fragment.y, fragment.width, fragment.height)]
    if (
        fragment.x2 is not None
        and fragment.y2 is not None
        and fragment.width2 is not None
        and fragment.height2 is not None
    ):
        boxes.append((fragment.x2, fragment.y2, fragment.width2, fragment.height2))
    return boxes


def _segment_fragment(
    deps: _EntryExtractionDependencies,
    fragment: EntryFragment,
    language: str,
) -> list[FragmentSegment]:
    """Downloads the fragment's page image and runs word-level ALTO
    segmentation over its padded region.

    The image is only ever held in memory/a ``SpooledTemporaryFile`` for
    this one OCR pass (see ``TesseractAltoOcrProvider.segment_region`` /
    ``crop_region``) -- nothing is written back to object storage. Returns
    ``[]`` (rather than raising) on any missing page/image/OCR failure, so
    the caller can simply skip this fragment.
    """
    with deps.sources_unit_of_work_factory() as unit_of_work:
        page = unit_of_work.sources.get_page_by_id(fragment.page_id)
    if page is None:
        return []

    spooled_file: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
        max_size=_PAGE_IMAGE_SPOOL_MAX_BYTES
    )
    buffer = cast(BinaryIO, spooled_file)
    try:
        try:
            deps.object_storage.download(page.processed_asset_key, buffer)
        except ObjectNotFoundError:
            return []
        buffer.seek(0)
        image_bytes = buffer.read()
    finally:
        buffer.close()

    try:
        return deps.ocr_provider.segment_region(
            image_bytes, _fragment_boxes(fragment), language
        )
    except OcrExecutionError:
        return []


def _union_geometry(
    segments: list[FragmentSegment], start: int, end: int
) -> tuple[float, float, float, float]:
    covered = segments[start : end + 1]
    min_x = min(segment.x for segment in covered)
    min_y = min(segment.y for segment in covered)
    max_x = max(segment.x + segment.width for segment in covered)
    max_y = max(segment.y + segment.height for segment in covered)
    return min_x, min_y, max_x - min_x, max_y - min_y


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=EXTRACT_ENTRY_FIELDS_TASK_NAME,
    soft_time_limit=150,
    time_limit=180,
)
def extract_entry_fields(task: Task, entry_id: str, actor_id: str) -> dict[str, object]:
    """Extract structured fields for one entry's fragments, per the
    dictionary's active ``ArticleSchema``, then run the rule-based
    abbreviation/geography pass -- an OCR or provider failure on one
    fragment never crashes the task, it just skips that fragment.
    """
    task_id = str(task.request.id)
    _log_task_event("entry_extraction_started", task_id)
    deps = _entry_extraction_dependencies()
    entry_uuid = UUID(entry_id)
    actor_uuid = UUID(actor_id)

    with deps.lexicography_unit_of_work_factory() as unit_of_work:
        entry = unit_of_work.lexicography.get_entry(entry_uuid)
        if entry is None:
            _log_task_event("entry_extraction_entry_missing", task_id)
            return {"status": "failed", "error": "entry not found"}

        schema = unit_of_work.lexicography.get_active_article_schema(
            entry.dictionary_id
        )
        if schema is None:
            _log_task_event("entry_extraction_no_active_schema", task_id)
            return {"status": "failed", "error": "no active article schema"}

        fragments = unit_of_work.lexicography.list_fragments_for_entry(entry_uuid)

    with deps.sources_unit_of_work_factory() as sources_unit_of_work:
        dictionary = sources_unit_of_work.sources.get_dictionary(entry.dictionary_id)
    language = resolve_ocr_language(
        [lang.language_code for lang in dictionary.languages] if dictionary else []
    )

    now = datetime.now(UTC)
    created_fields = 0
    with deps.lexicography_unit_of_work_factory() as unit_of_work:
        for fragment in fragments:
            segments = _segment_fragment(deps, fragment, language)
            if not segments:
                _log_task_event(
                    "entry_extraction_fragment_unsegmented",
                    task_id,
                    fragment_id=str(fragment.id),
                )
                continue

            try:
                extracted = deps.ai_schema_provider.extract_fields(schema, segments)
            except AiSchemaProviderError as error:
                _log_task_event(
                    "entry_extraction_fragment_failed",
                    task_id,
                    fragment_id=str(fragment.id),
                    error=str(error),
                )
                continue

            for position, item in enumerate(extracted):
                x, y, width, height = _union_geometry(
                    segments, item.segment_start, item.segment_end
                )
                source_text = " ".join(
                    segment.text
                    for segment in segments[item.segment_start : item.segment_end + 1]
                )
                field = EntryField(
                    id=uuid4(),
                    entry_id=entry_uuid,
                    fragment_id=fragment.id,
                    field_path=item.field_path,
                    role=item.role,
                    position=position,
                    source_text=source_text,
                    normalized_text=item.value,
                    confidence=item.confidence,
                    origin=EntryFieldOrigin.MODEL,
                    created_at=now,
                    created_by=actor_uuid,
                    updated_at=now,
                    updated_by=actor_uuid,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                )
                unit_of_work.lexicography.add_field(field)
                created_fields += 1

        entry.schema_id = schema.id
        if entry.status == EntryStatus.DRAFT:
            entry.status = EntryStatus.READY_TO_REVIEW
        entry.updated_at = now
        entry.updated_by = actor_uuid
        unit_of_work.lexicography.update_entry(entry)
        unit_of_work.commit()

    tagged = deps.annotation_service.tag_abbreviations_and_geography(
        entry.dictionary_id, entry_uuid, actor_uuid
    )
    created_fields += len(tagged)

    _log_task_event(
        "entry_extraction_succeeded", task_id, created_fields=created_fields
    )
    return {"status": "succeeded", "created_fields": created_fields}
