"""Application-owned ports for lexicography infrastructure."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.lexicography.domain import Lexeme


class LexicographyRepository(Protocol):
    """Persistence operations needed by the lexeme use cases."""

    def add_lexeme(self, lexeme: Lexeme) -> None: ...

    def list_lexemes_for_page(self, page_id: UUID) -> list[Lexeme]: ...


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
