"""Application-owned ports for sources infrastructure."""

from collections.abc import Callable, Sequence
from types import TracebackType
from typing import BinaryIO, Protocol, Self
from uuid import UUID

from cadmus.sources.domain import (
    Contributor,
    Dictionary,
    DictionaryEvent,
    DictionaryLanguage,
    SourceFile,
)


class SourcesRepository(Protocol):
    """Persistence operations needed by the dictionary draft use cases."""

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None: ...

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None: ...

    def get_source_file_by_id(self, source_file_id: UUID) -> SourceFile | None: ...

    def find_duplicate_source(
        self, owner_id: UUID, checksum_sha256: str
    ) -> Dictionary | None: ...

    def add_dictionary(self, dictionary: Dictionary) -> None: ...

    def update_dictionary(self, dictionary: Dictionary) -> None: ...

    def add_source_file(self, source_file: SourceFile) -> None: ...

    def update_source_file(self, source_file: SourceFile) -> None: ...

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None: ...

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None: ...

    def add_event(self, event: DictionaryEvent) -> None: ...


class SourcesUnitOfWork(Protocol):
    """Transaction boundary controlled by a sources use case."""

    @property
    def sources(self) -> SourcesRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type SourcesUnitOfWorkFactory = Callable[[], SourcesUnitOfWork]


INSPECT_SOURCE_TASK_NAME = "cadmus.sources.inspect_dictionary_source"


class SourceInspectionQueueUnavailableError(RuntimeError):
    """Raised when the inspection queue infrastructure cannot be reached."""


class SourceInspectionQueue(Protocol):
    """Port used to hand off worker-side PDF structural inspection."""

    def enqueue_inspection(self, source_file_id: UUID) -> None: ...


class InvalidPdfError(ValueError):
    """Raised when a stored object does not parse as a well-formed PDF."""


class PdfInspector(Protocol):
    """Worker-only boundary for bounded, defensive PDF structural parsing."""

    def page_count(self, stream: BinaryIO) -> int: ...
