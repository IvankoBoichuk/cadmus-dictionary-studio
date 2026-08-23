"""Application-owned ports for lexicography infrastructure."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.lexicography.domain import (
    DictionaryScanSnapshot,
    Lexeme,
    LexemeEvent,
    OcrSuggestionTaskSnapshot,
)


class LexicographyRepository(Protocol):
    """Persistence operations needed by the lexeme use cases."""

    def add_lexeme(self, lexeme: Lexeme) -> None: ...

    def list_lexemes_for_page(self, page_id: UUID) -> list[Lexeme]: ...

    def get_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> Lexeme | None: ...

    def update_lexeme(self, lexeme: Lexeme) -> None: ...

    def delete_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> None: ...

    def add_lexeme_event(self, event: LexemeEvent) -> None: ...

    def list_page_ids_with_lexemes(self, dictionary_id: UUID) -> set[UUID]: ...

    def has_any_lexeme(self, dictionary_id: UUID) -> bool: ...


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


SUGGEST_LEXEMES_TASK_NAME = "cadmus.lexicography.suggest_lexemes"


class OcrSuggestionQueueUnavailableError(RuntimeError):
    """Raised when the OCR suggestion queue infrastructure cannot be reached."""


class OcrSuggestionQueue(Protocol):
    """Port used to hand off worker-side OCR word suggestion and read it back.

    Ephemeral by design: implementations are expected to hold the result in
    a short-lived store (e.g. the Celery result backend), not Postgres --
    suggestions are candidates, never source evidence, until a user accepts
    one and it becomes a real ``Lexeme`` (see ``CreateLexemeService``).
    """

    def enqueue_suggestions(
        self, source_file_id: UUID, page_id: UUID, language: str
    ) -> str: ...

    def get_suggestions_task(self, task_id: str) -> OcrSuggestionTaskSnapshot: ...


SCAN_DICTIONARY_TASK_NAME = "cadmus.lexicography.scan_dictionary"


class DictionaryScanQueueUnavailableError(RuntimeError):
    """Raised when the whole-dictionary OCR scan queue cannot be reached."""


class DictionaryScanQueue(Protocol):
    """Port used to hand off a whole-dictionary OCR scan and read it back.

    Unlike ``OcrSuggestionQueue`` (one page, suggestions only), the worker
    task behind this port creates draft ``Lexeme`` rows itself as it walks
    every unscanned page -- this port only reports progress, never
    suggestions.
    """

    def enqueue_scan(self, dictionary_id: UUID, actor_id: UUID) -> str: ...

    def get_scan_task(self, task_id: str) -> DictionaryScanSnapshot: ...
