"""Lexicography application use cases: manual lexeme selection (BH-54)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cadmus.lexicography.domain import (
    DuplicateLexemeError,
    Lexeme,
    LexemeAccessError,
    LexemeOrigin,
    LexemePageNotFoundError,
    LexemeValidationError,
    find_overlapping_lexeme,
    validate_lexeme_fields,
)
from cadmus.lexicography.ports import LexicographyUnitOfWorkFactory
from cadmus.sources import DictionaryAccessError, DictionaryPage
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
                origin=LexemeOrigin.MANUAL,
                created_at=now,
                created_by=actor_id,
                updated_at=now,
                updated_by=actor_id,
            )
            unit_of_work.lexicography.add_lexeme(lexeme)
            unit_of_work.commit()
        return lexeme


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
