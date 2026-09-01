"""Lexicography application use cases: manual lexeme selection (BH-54)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from cadmus.access import Permission
from cadmus.lexicography.domain import (
    ArticleSchema,
    ArticleSchemaAccessError,
    ArticleSchemaGenerationSnapshot,
    ArticleSchemaValidationError,
    DictionaryEntry,
    DictionaryNotReadyToScanError,
    DictionaryScanSnapshot,
    DuplicateEntryError,
    DuplicateLexemeError,
    EntryAccessError,
    EntryExtractionSnapshot,
    EntryField,
    EntryFieldAccessError,
    EntryFieldOrigin,
    EntryFieldRole,
    EntryFieldValidationError,
    EntryFragment,
    EntryRenderResult,
    EntryStatus,
    EntryValidationError,
    Lexeme,
    LexemeAccessError,
    LexemeEvent,
    LexemeEventType,
    LexemeNotEditableError,
    LexemeNotFoundError,
    LexemeOrigin,
    LexemePageNotFoundError,
    LexemeStatus,
    LexemeValidationError,
    OcrSuggestionStatus,
    OcrSuggestionTaskSnapshot,
    PresentationTemplateError,
    SchemaGenerationStatus,
    build_entry_presentation_context,
    changed_lexeme_fields,
    find_overlapping_lexeme,
    normalize_schema_definition,
    resolve_ocr_language,
    resolve_schema_node,
    validate_entry_against_schema,
    validate_field_value,
    validate_lexeme_fields,
    validate_schema_definition,
    validate_second_box_fields,
)
from cadmus.lexicography.ports import (
    ArticleSchemaQueue,
    DictionaryScanQueue,
    EntryExtractionQueue,
    EntryPresentationRenderer,
    LexicographyUnitOfWork,
    LexicographyUnitOfWorkFactory,
    OcrSuggestionQueue,
)
from cadmus.sources import (
    AdvanceDictionaryProcessingStatusService,
    Dictionary,
    DictionaryAccessError,
    DictionaryPage,
    DictionaryStatus,
    MarkDictionaryScannedService,
    ProcessingSignals,
    SourcesUnitOfWorkFactory,
)
from cadmus.sources.application import GetDictionaryService


@dataclass(frozen=True)
class LexemeInput:
    """One BH-54 lexeme submission, already type-checked at the boundary."""

    page_number: int
    source_text: str
    x: float
    y: float
    width: float
    height: float
    confirm_duplicate: bool = False
    origin: LexemeOrigin = LexemeOrigin.MANUAL
    x2: float | None = None
    y2: float | None = None
    width2: float | None = None
    height2: float | None = None


def _resolve_page(
    dictionary_pages: GetDictionaryService,
    dictionary_id: UUID,
    actor_id: UUID,
    page_number: int,
    *,
    required_permission: Permission = Permission.VIEW,
) -> DictionaryPage:
    """Resolve a BH-53 viewer ordinal to its ``DictionaryPage``.

    Reuses ``GetDictionaryService.get_viewable_page``, so a lexeme can only
    ever be created on a page within the dictionary's saved ranges and
    ownership/role is checked the same way the viewer already checks it.
    """
    page = dictionary_pages.get_viewable_page(
        dictionary_id, actor_id, page_number, required_permission=required_permission
    )
    if page is None:
        raise LexemePageNotFoundError(dictionary_id, page_number)
    return page


class CreateLexemeService:
    """Validate and persist a manually drawn BH-54 lexeme (AC1-AC6)."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._clock = clock

    def create(self, dictionary_id: UUID, actor_id: UUID, data: LexemeInput) -> Lexeme:
        try:
            page = _resolve_page(
                self._dictionary_pages,
                dictionary_id,
                actor_id,
                data.page_number,
                required_permission=Permission.EDIT,
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        errors = validate_lexeme_fields(
            source_text=data.source_text,
            x=data.x,
            y=data.y,
            width=data.width,
            height=data.height,
            page_width=page.width,
            page_height=page.height,
        )
        errors.update(
            validate_second_box_fields(
                x2=data.x2,
                y2=data.y2,
                width2=data.width2,
                height2=data.height2,
                page_width=page.width,
                page_height=page.height,
            )
        )
        if errors:
            raise LexemeValidationError(errors)

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.lexicography.list_lexemes_for_page(page.id)
            overlap = find_overlapping_lexeme(
                x=data.x,
                y=data.y,
                width=data.width,
                height=data.height,
                existing=existing,
            )
            if overlap is not None and not data.confirm_duplicate:
                raise DuplicateLexemeError(overlap.id)

            lexeme = Lexeme(
                id=uuid4(),
                dictionary_id=dictionary_id,
                page_id=page.id,
                source_text=data.source_text.strip(),
                x=data.x,
                y=data.y,
                width=data.width,
                height=data.height,
                origin=data.origin,
                created_at=now,
                created_by=actor_id,
                updated_at=now,
                updated_by=actor_id,
                x2=data.x2,
                y2=data.y2,
                width2=data.width2,
                height2=data.height2,
            )
            unit_of_work.lexicography.add_lexeme(lexeme)
            unit_of_work.commit()
        return lexeme


@dataclass(frozen=True)
class UpdateLexemeInput:
    """One BH-56 lexeme edit submission: full replacement text and box.

    ``status`` is ``None`` unless the caller is explicitly requesting a
    status change (BH-113) -- most edits leave it untouched.
    """

    source_text: str
    x: float
    y: float
    width: float
    height: float
    x2: float | None = None
    y2: float | None = None
    width2: float | None = None
    height2: float | None = None
    status: LexemeStatus | None = None


class UpdateLexemeService:
    """Validate and persist an edit to a lexeme's text or bounding box (BH-56)."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._clock = clock

    def update(
        self,
        dictionary_id: UUID,
        lexeme_id: UUID,
        actor_id: UUID,
        data: UpdateLexemeInput,
    ) -> Lexeme:
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.lexicography.get_lexeme(dictionary_id, lexeme_id)
            if existing is None:
                raise LexemeNotFoundError(dictionary_id, lexeme_id)
            if existing.status == LexemeStatus.COMPLETE:
                raise LexemeNotEditableError(dictionary_id, lexeme_id)

            page = self._dictionary_pages.get_page_by_id(
                dictionary_id, actor_id, existing.page_id
            )
            if page is None:
                # The lexeme's own page vanished (e.g. a concurrent source
                # re-split) -- practically unreachable given ADR-0006's page
                # FKs, but if it ever happens the lexeme is effectively gone.
                raise LexemeNotFoundError(dictionary_id, lexeme_id)

            errors = validate_lexeme_fields(
                source_text=data.source_text,
                x=data.x,
                y=data.y,
                width=data.width,
                height=data.height,
                page_width=page.width,
                page_height=page.height,
            )
            errors.update(
                validate_second_box_fields(
                    x2=data.x2,
                    y2=data.y2,
                    width2=data.width2,
                    height2=data.height2,
                    page_width=page.width,
                    page_height=page.height,
                )
            )
            if errors:
                raise LexemeValidationError(errors)

            changed = changed_lexeme_fields(
                existing,
                source_text=data.source_text.strip(),
                x=data.x,
                y=data.y,
                width=data.width,
                height=data.height,
                x2=data.x2,
                y2=data.y2,
                width2=data.width2,
                height2=data.height2,
                status=data.status,
            )
            if changed:
                existing.source_text = data.source_text.strip()
                existing.x = data.x
                existing.y = data.y
                existing.width = data.width
                existing.height = data.height
                existing.x2 = data.x2
                existing.y2 = data.y2
                existing.width2 = data.width2
                existing.height2 = data.height2
                if data.status is not None:
                    existing.status = data.status
                existing.updated_at = now
                existing.updated_by = actor_id
                unit_of_work.lexicography.update_lexeme(existing)
                unit_of_work.lexicography.add_lexeme_event(
                    LexemeEvent(
                        id=uuid4(),
                        lexeme_id=lexeme_id,
                        dictionary_id=dictionary_id,
                        event_type=LexemeEventType.UPDATED,
                        actor_user_id=actor_id,
                        occurred_at=now,
                        changed_fields=tuple(changed),
                    )
                )
                unit_of_work.commit()
        return existing


class DeleteLexemeService:
    """Delete a lexeme and record who removed it, and when (BH-56)."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._clock = clock

    def delete(self, dictionary_id: UUID, lexeme_id: UUID, actor_id: UUID) -> None:
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.lexicography.get_lexeme(dictionary_id, lexeme_id)
            if existing is None:
                raise LexemeNotFoundError(dictionary_id, lexeme_id)
            if existing.status == LexemeStatus.COMPLETE:
                raise LexemeNotEditableError(dictionary_id, lexeme_id)

            unit_of_work.lexicography.delete_lexeme(dictionary_id, lexeme_id)
            unit_of_work.lexicography.add_lexeme_event(
                LexemeEvent(
                    id=uuid4(),
                    lexeme_id=lexeme_id,
                    dictionary_id=dictionary_id,
                    event_type=LexemeEventType.DELETED,
                    actor_user_id=actor_id,
                    occurred_at=now,
                )
            )
            unit_of_work.commit()


class LexemeQueryService:
    """Read lexemes for one page, scoped to the caller's own dictionary (AC7)."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages

    def list_for_page(
        self, dictionary_id: UUID, actor_id: UUID, page_number: int
    ) -> list[Lexeme]:
        try:
            page = _resolve_page(
                self._dictionary_pages, dictionary_id, actor_id, page_number
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.lexicography.list_lexemes_for_page(page.id)


class EntryQueryService:
    """List a dictionary's structured entries (BH-148), scoped to any member."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages

    def list_for_dictionary(
        self, dictionary_id: UUID, actor_id: UUID
    ) -> list[tuple[DictionaryEntry, int]]:
        try:
            self._dictionary_pages.get(dictionary_id, actor_id)
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        with self._unit_of_work_factory() as unit_of_work:
            entries = unit_of_work.lexicography.list_entries_for_dictionary(
                dictionary_id
            )
            field_counts = unit_of_work.lexicography.count_fields_by_entry(
                dictionary_id
            )
        return [(entry, field_counts.get(entry.id, 0)) for entry in entries]


@dataclass(frozen=True)
class PageProgress:
    """BH-57: one viewer page's scan status."""

    page_number: int
    has_lexemes: bool


@dataclass(frozen=True)
class ScanProgress:
    """BH-57 AC1/AC2: how much of a dictionary's pages have been scanned,
    plus lexeme- and entry-level completion and the current dictionary
    status (kept in sync by :meth:`ScanProgressService.get_progress`)."""

    status: DictionaryStatus
    total_pages: int
    processed_pages: int
    pages: tuple[PageProgress, ...]
    total_lexemes: int
    completed_lexemes: int
    total_entries: int
    completed_entries: int


class ScanProgressService:
    """Report per-page and aggregate scan progress (BH-57).

    "Processed" means "has at least one lexeme" (the Story's own
    definition) -- a page is never marked processed by any other signal.
    Combines ``sources`` (page ordering) and ``lexicography`` (lexeme
    presence).

    Reading progress also keeps the dictionary's post-scanning status in
    step with lexeme/entry completion (``scanned`` -> ``in_progress`` ->
    ``processed``) for editors; viewers get the current status without a
    write.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        status_service: AdvanceDictionaryProcessingStatusService,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._status_service = status_service

    def get_progress(self, dictionary_id: UUID, actor_id: UUID) -> ScanProgress:
        try:
            pages = self._dictionary_pages.list_viewable_pages(dictionary_id, actor_id)
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        with self._unit_of_work_factory() as unit_of_work:
            pages_with_lexemes = unit_of_work.lexicography.list_page_ids_with_lexemes(
                dictionary_id
            )
            lexeme_counts = unit_of_work.lexicography.count_lexemes_by_status(
                dictionary_id
            )
            entry_counts = unit_of_work.lexicography.count_entries_by_status(
                dictionary_id
            )

        total_lexemes = sum(lexeme_counts.values())
        draft_lexemes = lexeme_counts.get(LexemeStatus.DRAFT, 0)
        completed_lexemes = lexeme_counts.get(LexemeStatus.COMPLETE, 0)
        total_entries = sum(entry_counts.values())
        completed_entries = entry_counts.get(EntryStatus.COMPLETE, 0)

        signals = ProcessingSignals(
            has_any_lexeme=total_lexemes > 0,
            has_processing_work=(total_lexemes - draft_lexemes) > 0
            or total_entries > 0,
            all_lexemes_complete=total_lexemes > 0
            and completed_lexemes == total_lexemes,
            all_entries_complete=completed_entries == total_entries,
        )
        try:
            dictionary = self._status_service.advance(dictionary_id, actor_id, signals)
        except DictionaryAccessError:
            # Viewer without edit rights: report the status, do not change it.
            dictionary = self._dictionary_pages.get(dictionary_id, actor_id)

        entries = tuple(
            PageProgress(page_number=index, has_lexemes=page.id in pages_with_lexemes)
            for index, page in enumerate(pages, start=1)
        )
        processed = sum(1 for entry in entries if entry.has_lexemes)
        return ScanProgress(
            status=DictionaryStatus(dictionary.status),
            total_pages=len(entries),
            processed_pages=processed,
            pages=entries,
            total_lexemes=total_lexemes,
            completed_lexemes=completed_lexemes,
            total_entries=total_entries,
            completed_entries=completed_entries,
        )


class FinishScanningService:
    """BH-58: finish the scanning stage once the dictionary has any lexeme.

    An explicit use case, not a hidden side effect: checks the precondition
    (a ``lexicography`` fact) itself, then delegates the actual status
    mutation and audit trail to ``sources.MarkDictionaryScannedService``,
    which owns the ``Dictionary`` aggregate. Idempotent -- an already
    ``scanned`` dictionary short-circuits without re-checking lexemes, so a
    later bulk-delete of lexemes never un-finishes a completed stage.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        scanning_service: MarkDictionaryScannedService,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._scanning_service = scanning_service

    def finish(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        try:
            dictionary = self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        if dictionary.status == DictionaryStatus.SCANNED:
            return dictionary

        with self._unit_of_work_factory() as unit_of_work:
            has_lexemes = unit_of_work.lexicography.has_any_lexeme(dictionary_id)
        if not has_lexemes:
            raise DictionaryNotReadyToScanError(dictionary_id)

        return self._scanning_service.mark_scanned(dictionary_id, actor_id)


class SuggestLexemesService:
    """Enqueue and read back OCR word suggestions for one page.

    Suggestions are never persisted (see ``LexemeSuggestion``); accepting
    one goes through the ordinary ``CreateLexemeService`` with
    ``origin=LexemeOrigin.OCR``, so validation, duplicate-overlap
    detection, and provenance stay on the one existing write path.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        queue: OcrSuggestionQueue,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._queue = queue

    def enqueue(self, dictionary_id: UUID, actor_id: UUID, page_number: int) -> str:
        try:
            dictionary = self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
            page = _resolve_page(
                self._dictionary_pages,
                dictionary_id,
                actor_id,
                page_number,
                required_permission=Permission.EDIT,
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        language = resolve_ocr_language(
            [language.language_code for language in dictionary.languages]
        )
        return self._queue.enqueue_suggestions(page.source_file_id, page.id, language)

    def get_task(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        page_number: int,
        task_id: str,
    ) -> OcrSuggestionTaskSnapshot:
        try:
            page = _resolve_page(
                self._dictionary_pages, dictionary_id, actor_id, page_number
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        snapshot = self._queue.get_suggestions_task(task_id)
        if snapshot.status != OcrSuggestionStatus.SUCCEEDED or not snapshot.suggestions:
            return snapshot

        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.lexicography.list_lexemes_for_page(page.id)

        remaining = tuple(
            suggestion
            for suggestion in snapshot.suggestions
            if find_overlapping_lexeme(
                x=suggestion.x,
                y=suggestion.y,
                width=suggestion.width,
                height=suggestion.height,
                existing=existing,
            )
            is None
        )
        return OcrSuggestionTaskSnapshot(
            task_id=snapshot.task_id,
            status=snapshot.status,
            suggestions=remaining,
            error=snapshot.error,
        )


class QueueDictionaryScanService:
    """Enqueue and read back a whole-dictionary OCR scan.

    Unlike ``SuggestLexemesService`` (one page, review-then-accept), the
    worker task behind this queues every unscanned page of a dictionary and
    persists each surviving suggestion directly as a draft lexeme
    (``LexemeOrigin.OCR``) -- no manual accept step. A page that already has
    at least one lexeme is left untouched, so running the queue again only
    fills gaps.
    """

    def __init__(
        self,
        dictionary_pages: GetDictionaryService,
        queue: DictionaryScanQueue,
    ) -> None:
        self._dictionary_pages = dictionary_pages
        self._queue = queue

    def enqueue(self, dictionary_id: UUID, actor_id: UUID) -> str:
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error
        return self._queue.enqueue_scan(dictionary_id, actor_id)

    def get_task(
        self, dictionary_id: UUID, actor_id: UUID, task_id: str
    ) -> DictionaryScanSnapshot:
        try:
            self._dictionary_pages.get(dictionary_id, actor_id)
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error
        return self._queue.get_scan_task(task_id)


class QueueArticleSchemaGenerationService:
    """Enqueue and read back AI article-schema generation for one dictionary.

    The worker task behind this persists the resulting ``ArticleSchema``
    version itself (``READY``/``FAILED``) -- this port only reports
    progress, mirroring ``QueueDictionaryScanService``.
    """

    def __init__(
        self,
        dictionary_pages: GetDictionaryService,
        queue: ArticleSchemaQueue,
    ) -> None:
        self._dictionary_pages = dictionary_pages
        self._queue = queue

    def enqueue(self, dictionary_id: UUID, actor_id: UUID) -> str:
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error
        return self._queue.enqueue_generation(dictionary_id, actor_id)

    def get_task(
        self, dictionary_id: UUID, actor_id: UUID, task_id: str
    ) -> ArticleSchemaGenerationSnapshot:
        try:
            self._dictionary_pages.get(dictionary_id, actor_id)
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error
        return self._queue.get_generation_task(task_id)


class ActivateArticleSchemaService:
    """Confirm one ``READY`` article-schema version as the dictionary's active one.

    AI-generated schemas are a proposal (AGENTS.md) until an editor
    explicitly activates a version; at most one version per dictionary is
    ever active at a time.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._clock = clock

    def list_versions(self, dictionary_id: UUID, actor_id: UUID) -> list[ArticleSchema]:
        try:
            self._dictionary_pages.get(dictionary_id, actor_id)
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.lexicography.list_article_schemas(dictionary_id)

    def activate(
        self, dictionary_id: UUID, schema_id: UUID, actor_id: UUID
    ) -> ArticleSchema:
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            schema = unit_of_work.lexicography.get_article_schema(schema_id)
            if schema is None or schema.dictionary_id != dictionary_id:
                raise ArticleSchemaAccessError(schema_id)
            if schema.status != SchemaGenerationStatus.READY:
                raise ArticleSchemaValidationError(
                    {"status": "Тільки готову схему можна активувати."}
                )

            active = unit_of_work.lexicography.get_active_article_schema(dictionary_id)
            if active is not None and active.id != schema.id:
                active.activated_at = None
                active.activated_by = None
                unit_of_work.lexicography.update_article_schema(active)

            schema.activated_at = now
            schema.activated_by = actor_id
            unit_of_work.lexicography.update_article_schema(schema)
            unit_of_work.commit()
        return schema


class SaveArticleSchemaService:
    """Persist a hand-edited article-schema ``definition`` as a new version.

    Editing never mutates an existing version (they are immutable history);
    it always appends a fresh ``READY`` version, left inactive until an
    editor activates it via ``ActivateArticleSchemaService``.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._clock = clock

    def save(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        *,
        definition: dict[str, Any],
        source_description: str | None = None,
        presentation_formula: str | None = None,
    ) -> ArticleSchema:
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        errors = validate_schema_definition(definition)
        if errors:
            raise ArticleSchemaValidationError(errors)

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            next_version = (
                len(unit_of_work.lexicography.list_article_schemas(dictionary_id)) + 1
            )
            schema = ArticleSchema(
                id=uuid4(),
                dictionary_id=dictionary_id,
                version=next_version,
                status=SchemaGenerationStatus.READY,
                source_description=(source_description or "").strip(),
                definition=normalize_schema_definition(definition),
                created_at=now,
                created_by=actor_id,
                provider_name=None,
                presentation_formula=(presentation_formula or "").strip() or None,
            )
            unit_of_work.lexicography.add_article_schema(schema)
            unit_of_work.commit()
        return schema


class PromoteLexemeToEntryService:
    """Promote a ``COMPLETE`` lexeme into a ``DictionaryEntry`` (BH-148).

    Creates one ``EntryFragment`` copying the lexeme's page, box, and text --
    a lexeme may be promoted at most once (``DuplicateEntryError``).
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._clock = clock

    def create(
        self, dictionary_id: UUID, lexeme_id: UUID, actor_id: UUID
    ) -> DictionaryEntry:
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            lexeme = unit_of_work.lexicography.get_lexeme(dictionary_id, lexeme_id)
            if lexeme is None:
                raise LexemeNotFoundError(dictionary_id, lexeme_id)
            if lexeme.status != LexemeStatus.COMPLETE:
                raise EntryValidationError(
                    {
                        "lexeme": (
                            "Лексему потрібно завершити перед перетворенням на статтю."
                        )
                    }
                )

            existing = unit_of_work.lexicography.get_entry_by_lexeme(lexeme_id)
            if existing is not None:
                raise DuplicateEntryError(existing.id, lexeme_id)

            entry = DictionaryEntry(
                id=uuid4(),
                dictionary_id=dictionary_id,
                lexeme_id=lexeme_id,
                headword=lexeme.source_text,
                status=EntryStatus.DRAFT,
                created_at=now,
                updated_at=now,
                created_by=actor_id,
                updated_by=actor_id,
            )
            fragment = EntryFragment(
                id=uuid4(),
                entry_id=entry.id,
                page_id=lexeme.page_id,
                x=lexeme.x,
                y=lexeme.y,
                width=lexeme.width,
                height=lexeme.height,
                reading_order=0,
                recognized_text=lexeme.source_text,
                x2=lexeme.x2,
                y2=lexeme.y2,
                width2=lexeme.width2,
                height2=lexeme.height2,
            )
            unit_of_work.lexicography.add_entry(entry)
            unit_of_work.lexicography.add_fragment(fragment)
            unit_of_work.commit()
        return entry


class QueueEntryFieldExtractionService:
    """Enqueue and read back AI field extraction for one entry.

    The worker task behind this persists each extracted field itself
    (``origin=EntryFieldOrigin.MODEL``) and runs the rule-based
    abbreviation/geography pass -- this port only reports progress,
    mirroring ``QueueArticleSchemaGenerationService``.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        queue: EntryExtractionQueue,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._queue = queue

    def _authorized_entry(
        self,
        entry_id: UUID,
        actor_id: UUID,
        *,
        required_permission: Permission = Permission.VIEW,
    ) -> DictionaryEntry:
        with self._unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
        if entry is None:
            raise EntryAccessError(entry_id)
        try:
            self._dictionary_pages.get(
                entry.dictionary_id,
                actor_id,
                required_permission=required_permission,
            )
        except DictionaryAccessError as error:
            raise EntryAccessError(entry_id) from error
        return entry

    def get(
        self, entry_id: UUID, actor_id: UUID
    ) -> tuple[DictionaryEntry, list[EntryFragment], list[EntryField]]:
        entry = self._authorized_entry(entry_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            fragments = unit_of_work.lexicography.list_fragments_for_entry(entry_id)
            fields = unit_of_work.lexicography.list_fields_for_entry(entry_id)
        return entry, fragments, fields

    def enqueue(self, entry_id: UUID, actor_id: UUID) -> str:
        entry = self._authorized_entry(
            entry_id, actor_id, required_permission=Permission.EDIT
        )
        return self._queue.enqueue_extraction(entry.id, actor_id)

    def get_task(
        self, entry_id: UUID, actor_id: UUID, task_id: str
    ) -> EntryExtractionSnapshot:
        self._authorized_entry(entry_id, actor_id)
        return self._queue.get_extraction_task(task_id)


class RuleBasedAnnotationService:
    """Tag abbreviation and geographic-label spans within an entry's fields.

    Deterministic, no AI call: matches each field's ``source_text`` against
    the dictionary's own BH-29/BH-30 abbreviation and settlement reference
    data, creating child ``EntryField`` rows (``origin=EntryFieldOrigin.RULE``)
    for every match found -- run as a step after AI extraction, or on its
    own to re-tag an entry after the reference data changes.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        sources_unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._sources_unit_of_work_factory = sources_unit_of_work_factory
        self._clock = clock

    def tag_abbreviations_and_geography(
        self, dictionary_id: UUID, entry_id: UUID, actor_id: UUID
    ) -> list[EntryField]:
        with self._sources_unit_of_work_factory() as sources_unit_of_work:
            abbreviations = sources_unit_of_work.sources.list_abbreviations(
                dictionary_id
            )
            settlements = sources_unit_of_work.sources.list_settlement_mappings(
                dictionary_id
            )

        needles: list[tuple[str, EntryFieldRole]] = [
            (item.abbreviation, EntryFieldRole.ABBREVIATION)
            for item in abbreviations
            if item.abbreviation
        ] + [
            (item.source_label, EntryFieldRole.GEOGRAPHIC_LABEL)
            for item in settlements
            if item.source_label
        ]
        if not needles:
            return []

        now = self._clock()
        created: list[EntryField] = []
        with self._unit_of_work_factory() as unit_of_work:
            fields = unit_of_work.lexicography.list_fields_for_entry(entry_id)
            for source_field in fields:
                if source_field.origin == EntryFieldOrigin.RULE:
                    continue  # don't re-tag matches found by this same pass
                haystack = source_field.source_text.lower()
                for needle, role in needles:
                    start = haystack.find(needle.lower())
                    if start < 0:
                        continue
                    end = start + len(needle)
                    tag = EntryField(
                        id=uuid4(),
                        entry_id=entry_id,
                        fragment_id=source_field.fragment_id,
                        parent_field_id=source_field.id,
                        field_path=f"{source_field.field_path}.{role.value}",
                        role=role,
                        position=len(created),
                        source_text=source_field.source_text[start:end],
                        source_start=start,
                        source_end=end,
                        origin=EntryFieldOrigin.RULE,
                        created_at=now,
                        created_by=actor_id,
                        updated_at=now,
                        updated_by=actor_id,
                    )
                    unit_of_work.lexicography.add_field(tag)
                    created.append(tag)
            if created:
                unit_of_work.commit()
        return created


class ValidateEntryService:
    """Check an entry against its ``ArticleSchema`` and gate the
    ``READY_TO_REVIEW`` and ``COMPLETE`` transitions (BH-148)."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._clock = clock

    def validate(self, entry_id: UUID) -> dict[str, str]:
        with self._unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
            if entry is None:
                raise EntryAccessError(entry_id)
            if entry.schema_id is None:
                return {"schema": "Для статті ще не визначено схему."}
            schema = unit_of_work.lexicography.get_article_schema(entry.schema_id)
            if schema is None:
                return {"schema": "Схему статті не знайдено."}
            fields = unit_of_work.lexicography.list_fields_for_entry(entry_id)
        return validate_entry_against_schema(entry, fields, schema)

    def complete(
        self, dictionary_id: UUID, entry_id: UUID, actor_id: UUID
    ) -> DictionaryEntry:
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        errors = self.validate(entry_id)
        if errors:
            raise EntryValidationError(errors)

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
            if entry is None:
                raise EntryAccessError(entry_id)
            entry.status = EntryStatus.COMPLETE
            entry.updated_at = now
            entry.updated_by = actor_id
            unit_of_work.lexicography.update_entry(entry)
            unit_of_work.commit()
        return entry

    def submit_for_review(
        self, dictionary_id: UUID, entry_id: UUID, actor_id: UUID
    ) -> DictionaryEntry:
        """Move a ``DRAFT`` entry to ``READY_TO_REVIEW`` so it enters the
        cross-dictionary review queue.

        Gated on the same schema check as :meth:`complete` (an editor submits
        what they believe is finished). A no-op on an entry already awaiting
        review; a ``COMPLETE`` entry is rejected with a field error.
        """
        try:
            self._dictionary_pages.get(
                dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        with self._unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
            if entry is None:
                raise EntryAccessError(entry_id)
            if entry.status is EntryStatus.READY_TO_REVIEW:
                return entry
            if entry.status is EntryStatus.COMPLETE:
                raise EntryValidationError(
                    {"status": "Завершену статтю не можна подати на перевірку."}
                )

        errors = self.validate(entry_id)
        if errors:
            raise EntryValidationError(errors)

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
            if entry is None:
                raise EntryAccessError(entry_id)
            entry.status = EntryStatus.READY_TO_REVIEW
            entry.updated_at = now
            entry.updated_by = actor_id
            unit_of_work.lexicography.update_entry(entry)
            unit_of_work.commit()
        return entry


class RenderEntryService:
    """Render one entry to Markdown via its schema's ``presentation_formula``
    (BH-148).

    Read-only and non-fatal: a missing schema/formula or a broken template
    yields an ``EntryRenderResult`` with ``markdown=None`` and a ``reason``, so
    the entry-editor preview panel can show a hint instead of erroring. Uses
    ``entry.schema_id`` (the version the entry's fields were extracted against),
    not the dictionary's currently active schema -- consistent with
    ``ValidateEntryService``.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        renderer: EntryPresentationRenderer,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages
        self._renderer = renderer

    def render(self, entry_id: UUID, actor_id: UUID) -> EntryRenderResult:
        with self._unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
            if entry is None:
                raise EntryAccessError(entry_id)
            try:
                self._dictionary_pages.get(entry.dictionary_id, actor_id)
            except DictionaryAccessError as error:
                raise EntryAccessError(entry_id) from error

            if entry.schema_id is None:
                return EntryRenderResult(markdown=None, reason="no_schema")
            schema = unit_of_work.lexicography.get_article_schema(entry.schema_id)
            if schema is None:
                return EntryRenderResult(markdown=None, reason="no_schema")

            formula = (schema.presentation_formula or "").strip()
            if not formula:
                return EntryRenderResult(markdown=None, reason="no_formula")

            fields = unit_of_work.lexicography.list_fields_for_entry(entry_id)

        context = build_entry_presentation_context(entry, fields, schema)
        try:
            markdown = self._renderer.render(formula, context)
        except PresentationTemplateError as error:
            return EntryRenderResult(
                markdown=None, reason="template_error", error=error.message
            )
        return EntryRenderResult(markdown=markdown)


class _EntryFieldWriteService:
    """Shared authorization for the manual ``EntryField`` CRUD services."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages

    def _authorize(self, entry_id: UUID, actor_id: UUID) -> DictionaryEntry:
        with self._unit_of_work_factory() as unit_of_work:
            entry = unit_of_work.lexicography.get_entry(entry_id)
        if entry is None:
            raise EntryAccessError(entry_id)
        try:
            self._dictionary_pages.get(
                entry.dictionary_id, actor_id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError as error:
            raise EntryAccessError(entry_id) from error
        return entry

    @staticmethod
    def _reject_invalid_typed_value(
        unit_of_work: LexicographyUnitOfWork,
        entry: DictionaryEntry,
        field_path: str,
        value: str,
    ) -> None:
        """Enforce a schema node's typed constraint (enum options, number,
        date, boolean) on a field value the editor is saving."""
        if entry.schema_id is None:
            return
        schema = unit_of_work.lexicography.get_article_schema(entry.schema_id)
        if schema is None:
            return
        node = resolve_schema_node(schema.definition, field_path)
        if node is None:
            return
        message = validate_field_value(node, value)
        if message is not None:
            raise EntryFieldValidationError({"source_text": message})


class CreateEntryFieldService(_EntryFieldWriteService):
    """Manually add a field an automatic pass missed (BH-148)."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(unit_of_work_factory, dictionary_pages)
        self._clock = clock

    def create(
        self,
        entry_id: UUID,
        actor_id: UUID,
        *,
        fragment_id: UUID,
        field_path: str,
        role: EntryFieldRole,
        source_text: str,
        source_start: int,
        source_end: int,
        parent_field_id: UUID | None = None,
        normalized_text: str | None = None,
    ) -> EntryField:
        entry = self._authorize(entry_id, actor_id)
        if not source_text.strip():
            raise EntryFieldValidationError({"source_text": "Вкажіть текст поля."})

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            self._reject_invalid_typed_value(
                unit_of_work, entry, field_path, source_text
            )
            existing = unit_of_work.lexicography.list_fields_for_entry(entry_id)
            field = EntryField(
                id=uuid4(),
                entry_id=entry_id,
                fragment_id=fragment_id,
                parent_field_id=parent_field_id,
                field_path=field_path,
                role=role,
                position=len(existing),
                source_text=source_text,
                source_start=source_start,
                source_end=source_end,
                normalized_text=normalized_text,
                origin=EntryFieldOrigin.MANUAL,
                created_at=now,
                created_by=actor_id,
                updated_at=now,
                updated_by=actor_id,
            )
            unit_of_work.lexicography.add_field(field)
            unit_of_work.commit()
        return field


class UpdateEntryFieldService(_EntryFieldWriteService):
    """Edit a field's value; any manual edit flips its origin to ``MANUAL``."""

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        super().__init__(unit_of_work_factory, dictionary_pages)
        self._clock = clock

    def update(
        self,
        entry_id: UUID,
        field_id: UUID,
        actor_id: UUID,
        *,
        role: EntryFieldRole | None = None,
        source_text: str | None = None,
        normalized_text: str | None = None,
    ) -> EntryField:
        entry = self._authorize(entry_id, actor_id)
        if source_text is not None and not source_text.strip():
            raise EntryFieldValidationError({"source_text": "Вкажіть текст поля."})

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            fields = unit_of_work.lexicography.list_fields_for_entry(entry_id)
            field = next((f for f in fields if f.id == field_id), None)
            if field is None:
                raise EntryFieldAccessError(field_id)

            if source_text is not None:
                self._reject_invalid_typed_value(
                    unit_of_work, entry, field.field_path, source_text
                )
                field.source_text = source_text
            if normalized_text is not None and normalized_text.strip():
                self._reject_invalid_typed_value(
                    unit_of_work, entry, field.field_path, normalized_text
                )
            if role is not None:
                field.role = role
            if normalized_text is not None:
                field.normalized_text = normalized_text
            field.origin = EntryFieldOrigin.MANUAL
            field.updated_at = now
            field.updated_by = actor_id
            unit_of_work.lexicography.update_field(field)
            unit_of_work.commit()
        return field


class DeleteEntryFieldService(_EntryFieldWriteService):
    """Remove a manually-added or mistakenly-extracted field (BH-148)."""

    def delete(self, entry_id: UUID, field_id: UUID, actor_id: UUID) -> None:
        self._authorize(entry_id, actor_id)
        with self._unit_of_work_factory() as unit_of_work:
            fields = unit_of_work.lexicography.list_fields_for_entry(entry_id)
            if not any(f.id == field_id for f in fields):
                raise EntryFieldAccessError(field_id)
            unit_of_work.lexicography.delete_field(field_id)
            unit_of_work.commit()
