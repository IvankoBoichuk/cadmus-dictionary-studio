"""Celery entrypoint for AI-driven entry field extraction (BH-148), kept
separate from ``article_schema_tasks.py`` -- extracting one entry's fields
against an already-active schema is a different capability from generating
that schema in the first place.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
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
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.lexicography import (
    EXTRACT_ENTRY_FIELDS_TASK_NAME,
    EntryField,
    EntryFieldOrigin,
    EntryStatus,
    LexicographyUnitOfWorkFactory,
    RuleBasedAnnotationService,
)
from cadmus.sources import SourcesUnitOfWorkFactory
from celery import Task

from cadmus_worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _log_task_event(event: str, task_id: str, **fields: object) -> None:
    logger.info(
        json.dumps({"event": event, "task_id": task_id, **fields}, sort_keys=True)
    )


@dataclass(frozen=True)
class _EntryExtractionDependencies:
    lexicography_unit_of_work_factory: LexicographyUnitOfWorkFactory
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
        ai_schema_provider=AnthropicAiSchemaProvider(
            api_key=api_key.get_secret_value() if api_key is not None else "",
            model=settings.ai_schema_model,
            timeout_seconds=settings.ai_schema_timeout_seconds,
        ),
        annotation_service=RuleBasedAnnotationService(
            lexicography_unit_of_work_factory, sources_unit_of_work_factory
        ),
    )


def _clamp_span(text: str, start: int, end: int) -> tuple[int, int]:
    length = len(text)
    clamped_start = max(0, min(start, length))
    clamped_end = max(clamped_start, min(end, length))
    return clamped_start, clamped_end


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=EXTRACT_ENTRY_FIELDS_TASK_NAME,
    soft_time_limit=90,
    time_limit=120,
)
def extract_entry_fields(task: Task, entry_id: str, actor_id: str) -> dict[str, object]:
    """Extract structured fields for one entry's fragments, per the
    dictionary's active ``ArticleSchema``, then run the rule-based
    abbreviation/geography pass -- a provider failure never crashes the task.
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

    now = datetime.now(UTC)
    created_fields = 0
    with deps.lexicography_unit_of_work_factory() as unit_of_work:
        for fragment in fragments:
            try:
                extracted = deps.ai_schema_provider.extract_fields(
                    schema, fragment.recognized_text
                )
            except AiSchemaProviderError as error:
                _log_task_event(
                    "entry_extraction_fragment_failed",
                    task_id,
                    fragment_id=str(fragment.id),
                    error=str(error),
                )
                continue

            for position, item in enumerate(extracted):
                start, end = _clamp_span(
                    fragment.recognized_text, item.source_start, item.source_end
                )
                field = EntryField(
                    id=uuid4(),
                    entry_id=entry_uuid,
                    fragment_id=fragment.id,
                    field_path=item.field_path,
                    role=item.role,
                    position=position,
                    source_text=fragment.recognized_text[start:end],
                    source_start=start,
                    source_end=end,
                    normalized_text=item.value,
                    confidence=item.confidence,
                    origin=EntryFieldOrigin.MODEL,
                    created_at=now,
                    created_by=actor_uuid,
                    updated_at=now,
                    updated_by=actor_uuid,
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
