"""Application-owned ports for access-control infrastructure."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.access.domain import ProjectMembership


class MembershipsRepository(Protocol):
    """Persistence operations needed by the project-membership use cases."""

    def get_membership(
        self, dictionary_id: UUID, user_id: UUID
    ) -> ProjectMembership | None: ...

    def list_members(self, dictionary_id: UUID) -> list[ProjectMembership]: ...

    def list_memberships_for_user(self, user_id: UUID) -> list[ProjectMembership]: ...

    def add_member(self, membership: ProjectMembership) -> None: ...

    def update_member(self, membership: ProjectMembership) -> None: ...

    def remove_member(self, dictionary_id: UUID, user_id: UUID) -> None: ...


class MembershipsUnitOfWork(Protocol):
    """Transaction boundary controlled by an access-control use case."""

    @property
    def memberships(self) -> MembershipsRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type MembershipsUnitOfWorkFactory = Callable[[], MembershipsUnitOfWork]
