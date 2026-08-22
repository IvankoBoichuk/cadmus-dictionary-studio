"""Application-owned ports for sources infrastructure."""

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import BinaryIO, Protocol, Self
from uuid import UUID

from cadmus.sources.domain import (
    Abbreviation,
    AbbreviationCategory,
    AbbreviationVariant,
    Contributor,
    Dictionary,
    DictionaryEvent,
    DictionaryLanguage,
    DictionaryPage,
    DictionaryPageRange,
    DictionarySettlementMapping,
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

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None: ...

    def list_source_files_pending_page_split(self) -> list[SourceFile]: ...

    def get_page(
        self, source_file_id: UUID, page_index: int
    ) -> DictionaryPage | None: ...

    def get_page_by_id(self, page_id: UUID) -> DictionaryPage | None: ...

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]: ...

    def delete_dictionary(self, dictionary_id: UUID) -> None: ...

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        """List every abbreviation of one dictionary (also the AC8 pipeline seam)."""
        ...

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None: ...

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None: ...

    def add_abbreviation(self, abbreviation: Abbreviation) -> None: ...

    def update_abbreviation(self, abbreviation: Abbreviation) -> None: ...

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None: ...

    def delete_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> None: ...

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]: ...

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None: ...

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        settlement_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None: ...

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None: ...

    def update_settlement_mapping(
        self, mapping: DictionarySettlementMapping
    ) -> None: ...

    def delete_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> None: ...

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]: ...

    def replace_page_ranges(
        self, dictionary_id: UUID, ranges: Sequence[DictionaryPageRange]
    ) -> None: ...


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


SPLIT_PAGES_TASK_NAME = "cadmus.sources.split_dictionary_pages"


class SourcePagesQueueUnavailableError(RuntimeError):
    """Raised when the page-split queue infrastructure cannot be reached."""


class SourcePagesQueue(Protocol):
    """Port used to hand off worker-side PDF page rendering."""

    def enqueue_split(self, source_file_id: UUID) -> None: ...


@dataclass(frozen=True)
class RenderedPage:
    """One rendered page image, before it is uploaded and hashed."""

    page_index: int
    width: int
    height: int
    content: bytes


class PdfPageRenderer(Protocol):
    """Worker-only boundary for rendering PDF pages to raster images."""

    def render_pages(self, stream: BinaryIO) -> Iterator[RenderedPage]: ...
