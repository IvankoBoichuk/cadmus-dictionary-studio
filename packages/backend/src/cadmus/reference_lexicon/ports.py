"""Application-owned ports for external reference lexicons."""

from collections.abc import Callable, Sequence
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.reference_lexicon.domain import (
    ReferenceLemma,
    ReferenceLemmaMatch,
    ReferenceLexicon,
    VesumRecord,
)


class ReferenceLexiconRepository(Protocol):
    """Persistence operations for locally cached lexical reference data."""

    def get_lexicon_by_code(self, code: str) -> ReferenceLexicon | None: ...

    def get_lemma(self, lemma_id: UUID) -> ReferenceLemma | None: ...

    def search_lemmas(
        self,
        *,
        lexicon_id: UUID,
        query: str,
        standard_only: bool,
        limit: int,
    ) -> list[ReferenceLemmaMatch]: ...

    def upsert_lexicon(self, lexicon: ReferenceLexicon) -> None: ...

    def deactivate_content(self, lexicon_id: UUID) -> None: ...

    def begin_bulk_load(self) -> None: ...

    def finish_bulk_load(self) -> None: ...

    def upsert_records(self, records: Sequence[VesumRecord]) -> None: ...


class ReferenceLexiconUnitOfWork(Protocol):
    """Transaction boundary controlled by one reference-lexicon use case."""

    @property
    def reference_lexicon(self) -> ReferenceLexiconRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type ReferenceLexiconUnitOfWorkFactory = Callable[[], ReferenceLexiconUnitOfWork]
