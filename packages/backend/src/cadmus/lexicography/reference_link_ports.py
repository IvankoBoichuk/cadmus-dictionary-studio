"""Application-owned persistence port for entry to reference-lemma links."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.lexicography.reference_link_domain import (
    EntryReferenceLink,
    ReferenceRelationType,
)


class EntryReferenceLinkRepository(Protocol):
    """Persistence operations needed by reference-link use cases."""

    def add(self, link: EntryReferenceLink) -> None: ...

    def list_for_entry(self, entry_id: UUID) -> list[EntryReferenceLink]: ...

    def get(self, entry_id: UUID, link_id: UUID) -> EntryReferenceLink | None: ...

    def find(
        self,
        entry_id: UUID,
        reference_lemma_id: UUID,
        relation_type: ReferenceRelationType,
    ) -> EntryReferenceLink | None: ...

    def delete(self, entry_id: UUID, link_id: UUID) -> None: ...


class EntryReferenceLinkUnitOfWork(Protocol):
    """Transaction boundary for one reference-link write."""

    @property
    def reference_links(self) -> EntryReferenceLinkRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type EntryReferenceLinkUnitOfWorkFactory = Callable[[], EntryReferenceLinkUnitOfWork]
