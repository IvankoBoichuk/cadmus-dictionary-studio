"""Celery entrypoint for AI-driven entry field extraction (BH-148), kept
separate from ``article_schema_tasks.py`` -- extracting one entry's fields
against an already-active schema is a different capability from generating
that schema in the first place.

Fields are extracted from each fragment's immutable ``recognized_text``
(plain running text). The model returns verbatim substrings; this task
locates each value in the text to record its ``source_start``/``source_end``
offsets (ADR-0008). No OCR pass, no per-field bounding box -- the earlier
ALTO word-segmentation experiment is retired (its helpers stay dormant in
``infrastructure/ocr.py``).
"""

import json
import logging
from collections.abc import Callable
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
from cadmus.infrastructure.reference_lexicon import (
    create_reference_lexicon_unit_of_work_factory,
)
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.lexicography import (
    EXTRACT_ENTRY_FIELDS_TASK_NAME,
    EntryField,
    EntryFieldOrigin,
    EntryStatus,
    LexicographyUnitOfWorkFactory,
    RuleBasedAnnotationService,
    dedupe_extracted_fields,
    dehyphenate_line_breaks,
)
from cadmus.reference_lexicon import (
    VESUM_CODE,
    ReferenceLexiconNotFoundError,
    ReferenceLexiconQueryService,
    normalize_ukrainian_text,
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
    sources_unit_of_work_factory: SourcesUnitOfWorkFactory
    ai_schema_provider: AnthropicAiSchemaProvider
    annotation_service: RuleBasedAnnotationService
    reference_lexicon_query: ReferenceLexiconQueryService | None = None


_UNCERTAIN_HYPHEN_CONFIDENCE = 0.5
"""Cap on a field's confidence when a line-break hyphen was rejoined without a
reference-lexicon match either way -- low enough to trip the entry editor's
"< 0.8" warning badge so an editor confirms the join."""


def _make_hyphen_resolver(
    query: ReferenceLexiconQueryService | None,
) -> Callable[[str, str], str] | None:
    """Build a ``dehyphenate_line_breaks`` resolver backed by VESUM: keep the
    hyphen when the hyphenated form is a known lemma/word-form
    (``військово-політичний``), drop it when the joined form is
    (``кожусі``), otherwise leave the decision open. Returns ``None`` when no
    reference lexicon is wired, and stops probing once VESUM proves absent."""
    if query is None:
        return None

    state = {"available": True}

    def _known(candidate: str) -> bool:
        normalized = normalize_ukrainian_text(candidate)
        if not normalized:
            return False
        try:
            matches = query.search(VESUM_CODE, candidate, standard_only=True, limit=20)
        except ReferenceLexiconNotFoundError:
            state["available"] = False
            return False
        for match in matches:
            if match.lemma.normalized_lemma == normalized:
                return True
            if (
                match.matched_form is not None
                and normalize_ukrainian_text(match.matched_form) == normalized
            ):
                return True
        return False

    def _resolve(joined: str, hyphenated: str) -> str:
        if not state["available"]:
            return "unknown"
        if _known(hyphenated):
            return "keep"
        if _known(joined):
            return "join"
        return "unknown"

    return _resolve


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
        ai_schema_provider=AnthropicAiSchemaProvider(
            api_key=api_key.get_secret_value() if api_key is not None else "",
            model=settings.ai_schema_model,
            timeout_seconds=settings.ai_schema_timeout_seconds,
        ),
        annotation_service=RuleBasedAnnotationService(
            lexicography_unit_of_work_factory, sources_unit_of_work_factory
        ),
        reference_lexicon_query=ReferenceLexiconQueryService(
            create_reference_lexicon_unit_of_work_factory(engine)
        ),
    )


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=EXTRACT_ENTRY_FIELDS_TASK_NAME,
    soft_time_limit=150,
    time_limit=180,
)
def extract_entry_fields(task: Task, entry_id: str, actor_id: str) -> dict[str, object]:
    """Extract structured fields for one entry's fragments, per the
    dictionary's active ``ArticleSchema``, then run the rule-based
    abbreviation/geography pass -- a provider failure on one fragment never
    crashes the task, it just skips that fragment.
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
    hyphen_resolver = _make_hyphen_resolver(deps.reference_lexicon_query)
    with deps.lexicography_unit_of_work_factory() as unit_of_work:
        for fragment in fragments:
            text = fragment.recognized_text
            if not text.strip():
                _log_task_event(
                    "entry_extraction_fragment_no_text",
                    task_id,
                    fragment_id=str(fragment.id),
                )
                continue

            try:
                extracted = deps.ai_schema_provider.extract_fields(schema, text)
            except AiSchemaProviderError as error:
                _log_task_event(
                    "entry_extraction_fragment_failed",
                    task_id,
                    fragment_id=str(fragment.id),
                    error=str(error),
                )
                continue

            for position, item in enumerate(dedupe_extracted_fields(schema, extracted)):
                index = text.find(item.value)
                if index >= 0:
                    source_text = text[index : index + len(item.value)]
                    source_start: int | None = index
                    source_end: int | None = index + len(item.value)
                    normalized_text = item.value if item.value != source_text else None
                else:
                    source_text = item.value
                    source_start = source_end = None
                    normalized_text = None

                # Rejoin words the OCR split across a printed line ("ко- жусі"
                # -> "кожусі"). The verbatim span stays on ``source_text`` /
                # the offsets; the joined form lands in ``normalized_text``,
                # which is what the presentation formula and validation read.
                confidence = item.confidence
                base = normalized_text if normalized_text is not None else source_text
                dehyphenated, uncertain = dehyphenate_line_breaks(
                    base, resolve=hyphen_resolver
                )
                if dehyphenated != base:
                    normalized_text = dehyphenated
                    if uncertain and confidence is not None:
                        confidence = min(confidence, _UNCERTAIN_HYPHEN_CONFIDENCE)

                field = EntryField(
                    id=uuid4(),
                    entry_id=entry_uuid,
                    fragment_id=fragment.id,
                    field_path=item.field_path,
                    role=item.role,
                    position=position,
                    source_text=source_text,
                    normalized_text=normalized_text,
                    source_start=source_start,
                    source_end=source_end,
                    confidence=confidence,
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

    resolved = deps.annotation_service.resolve_geographic_labels(
        entry.dictionary_id, entry_uuid, actor_uuid
    )

    _log_task_event(
        "entry_extraction_succeeded",
        task_id,
        created_fields=created_fields,
        resolved_geo_labels=len(resolved),
    )
    return {"status": "succeeded", "created_fields": created_fields}
