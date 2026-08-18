"""Application-owned ports for lexicography infrastructure."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.lexicography.domain import Lexeme, LexemeEvent


class LexicographyRepository(Protocol):
    """Persistence operations needed by the lexeme use cases."""

    def add_lexeme(self, lexeme: Lexeme) -> None: ...

    def list_lexemes_for_page(self, page_id: UUID) -> list[Lexeme]: ...

    def get_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> Lexeme | None: ...

    def update_lexeme(self, lexeme: Lexeme) -> None: ...

    def delete_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> None: ...

    def add_lexeme_event(self, event: LexemeEvent) -> None: ...

    def list_page_ids_with_lexemes(self, dictionary_id: UUID) -> set[UUID]: ...


class LexicographyUnitOfWork(Protocol):
    """Transaction boundary controlled by a lexicography use case."""

    @property
    def lexicography(self) -> LexicographyRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type LexicographyUnitOfWorkFactory = Callable[[], LexicographyUnitOfWork]
