"""Lexicography application use cases: manual lexeme selection (BH-54)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cadmus.lexicography.domain import (
    DictionaryNotReadyToScanError,
    DictionaryScanSnapshot,
    DuplicateLexemeError,
    Lexeme,
    LexemeAccessError,
    LexemeEvent,
    LexemeEventType,
    LexemeNotFoundError,
    LexemeOrigin,
    LexemePageNotFoundError,
    LexemeValidationError,
    OcrSuggestionStatus,
    OcrSuggestionTaskSnapshot,
    changed_lexeme_fields,
    find_overlapping_lexeme,
    resolve_ocr_language,
    validate_lexeme_fields,
    validate_second_box_fields,
)
from cadmus.lexicography.ports import (
    DictionaryScanQueue,
    LexicographyUnitOfWorkFactory,
    OcrSuggestionQueue,
)
from cadmus.sources import (
    Dictionary,
    DictionaryAccessError,
    DictionaryPage,
    DictionaryStatus,
    MarkDictionaryScannedService,
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
) -> DictionaryPage:
    """Resolve a BH-53 viewer ordinal to its ``DictionaryPage``.

    Reuses ``GetDictionaryService.get_viewable_page``, so a lexeme can only
    ever be created on a page within the dictionary's saved ranges and
    ownership is checked the same way the viewer already checks it.
    """
    page = dictionary_pages.get_viewable_page(dictionary_id, actor_id, page_number)
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
                self._dictionary_pages, dictionary_id, actor_id, data.page_number
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
    """One BH-56 lexeme edit submission: full replacement text and box."""

    source_text: str
    x: float
    y: float
    width: float
    height: float
    x2: float | None = None
    y2: float | None = None
    width2: float | None = None
    height2: float | None = None


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
            self._dictionary_pages.get(dictionary_id, actor_id)
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.lexicography.get_lexeme(dictionary_id, lexeme_id)
            if existing is None:
                raise LexemeNotFoundError(dictionary_id, lexeme_id)

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
            self._dictionary_pages.get(dictionary_id, actor_id)
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.lexicography.get_lexeme(dictionary_id, lexeme_id)
            if existing is None:
                raise LexemeNotFoundError(dictionary_id, lexeme_id)

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


@dataclass(frozen=True)
class PageProgress:
    """BH-57: one viewer page's scan status."""

    page_number: int
    has_lexemes: bool


@dataclass(frozen=True)
class ScanProgress:
    """BH-57 AC1/AC2: how much of a dictionary's pages have been scanned."""

    total_pages: int
    processed_pages: int
    pages: tuple[PageProgress, ...]


class ScanProgressService:
    """Report per-page and aggregate scan progress (BH-57).

    "Processed" means "has at least one lexeme" (the Story's own
    definition) -- a page is never marked processed by any other signal.
    Combines ``sources`` (page ordering) and ``lexicography`` (lexeme
    presence) with exactly two extra queries beyond the viewable-page
    lookup, regardless of how many pages the dictionary has.
    """

    def __init__(
        self,
        unit_of_work_factory: LexicographyUnitOfWorkFactory,
        dictionary_pages: GetDictionaryService,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._dictionary_pages = dictionary_pages

    def get_progress(self, dictionary_id: UUID, actor_id: UUID) -> ScanProgress:
        try:
            pages = self._dictionary_pages.list_viewable_pages(dictionary_id, actor_id)
        except DictionaryAccessError as error:
            raise LexemeAccessError(dictionary_id) from error

        with self._unit_of_work_factory() as unit_of_work:
            pages_with_lexemes = unit_of_work.lexicography.list_page_ids_with_lexemes(
                dictionary_id
            )

        entries = tuple(
            PageProgress(page_number=index, has_lexemes=page.id in pages_with_lexemes)
            for index, page in enumerate(pages, start=1)
        )
        processed = sum(1 for entry in entries if entry.has_lexemes)
        return ScanProgress(
            total_pages=len(entries), processed_pages=processed, pages=entries
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
            dictionary = self._dictionary_pages.get(dictionary_id, actor_id)
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
            dictionary = self._dictionary_pages.get(dictionary_id, actor_id)
            page = _resolve_page(
                self._dictionary_pages, dictionary_id, actor_id, page_number
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
            self._dictionary_pages.get(dictionary_id, actor_id)
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
