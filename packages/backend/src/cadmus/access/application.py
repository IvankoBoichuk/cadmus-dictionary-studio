"""Access-control application use cases: authorization and project membership."""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cadmus.access.domain import (
    ASSIGNABLE_ROLES,
    ROLE_PERMISSIONS,
    AccessDeniedError,
    DuplicateMembershipError,
    InvalidRoleAssignmentError,
    MembershipNotFoundError,
    Permission,
    ProjectMembership,
    Role,
)
from cadmus.access.ports import MembershipsUnitOfWorkFactory


class AuthorizationService:
    """Resolve an actor's ``Role`` on a dictionary and enforce permissions.

    Constructible with no membership backing
    (``membership_unit_of_work_factory=None``) so every caller across the
    codebase keeps working unchanged when it doesn't explicitly wire one in
    -- resolving to owner-only access, identical to the inline
    ``owner_id != actor_id`` checks this service replaces.
    """

    def __init__(
        self,
        membership_unit_of_work_factory: MembershipsUnitOfWorkFactory | None = None,
    ) -> None:
        self._membership_unit_of_work_factory = membership_unit_of_work_factory

    def resolve_role(
        self, dictionary_id: UUID, owner_id: UUID, actor_id: UUID
    ) -> Role | None:
        if owner_id == actor_id:
            return Role.OWNER
        if self._membership_unit_of_work_factory is None:
            return None
        with self._membership_unit_of_work_factory() as unit_of_work:
            membership = unit_of_work.memberships.get_membership(
                dictionary_id, actor_id
            )
        return membership.role if membership is not None else None

    def require(
        self,
        dictionary_id: UUID,
        owner_id: UUID,
        actor_id: UUID,
        permission: Permission,
    ) -> Role:
        role = self.resolve_role(dictionary_id, owner_id, actor_id)
        if role is None or permission not in ROLE_PERMISSIONS[role]:
            raise AccessDeniedError(dictionary_id)
        return role

    def list_member_dictionary_ids(self, actor_id: UUID) -> list[UUID]:
        """Dictionaries ``actor_id`` can see as a non-owner member (BH-170)."""
        if self._membership_unit_of_work_factory is None:
            return []
        with self._membership_unit_of_work_factory() as unit_of_work:
            memberships = unit_of_work.memberships.list_memberships_for_user(actor_id)
        return [membership.dictionary_id for membership in memberships]

    def list_reviewer_dictionary_ids(self, actor_id: UUID) -> list[UUID]:
        """Dictionaries ``actor_id`` can review as a non-owner member.

        The membership slice of ``Permission.REVIEW`` -- rows whose role is
        ``Role.REVIEWER``. Owners hold ``REVIEW`` too, but never through a
        membership row, so callers union this with the actor's own
        dictionaries.
        """
        if self._membership_unit_of_work_factory is None:
            return []
        with self._membership_unit_of_work_factory() as unit_of_work:
            memberships = unit_of_work.memberships.list_memberships_for_user(actor_id)
        return [
            membership.dictionary_id
            for membership in memberships
            if membership.role is Role.REVIEWER
        ]


class ManageMembersService:
    """Add, re-role, and remove non-owner project members (BH-170)."""

    def __init__(
        self,
        unit_of_work_factory: MembershipsUnitOfWorkFactory,
        authorization: AuthorizationService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._authorization = authorization
        self._clock = clock

    def add_member(
        self,
        dictionary_id: UUID,
        owner_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        role: Role,
    ) -> ProjectMembership:
        self._authorization.require(
            dictionary_id, owner_id, actor_id, Permission.MANAGE_MEMBERS
        )
        if role not in ASSIGNABLE_ROLES:
            raise InvalidRoleAssignmentError(role)
        if target_user_id == owner_id:
            raise DuplicateMembershipError(target_user_id)

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.memberships.get_membership(
                dictionary_id, target_user_id
            )
            if existing is not None:
                raise DuplicateMembershipError(target_user_id)
            membership = ProjectMembership(
                id=uuid4(),
                dictionary_id=dictionary_id,
                user_id=target_user_id,
                role=role,
                created_at=now,
                created_by=actor_id,
                updated_at=now,
                updated_by=actor_id,
            )
            unit_of_work.memberships.add_member(membership)
            unit_of_work.commit()
        return membership

    def change_role(
        self,
        dictionary_id: UUID,
        owner_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        role: Role,
    ) -> ProjectMembership:
        self._authorization.require(
            dictionary_id, owner_id, actor_id, Permission.MANAGE_MEMBERS
        )
        if role not in ASSIGNABLE_ROLES:
            raise InvalidRoleAssignmentError(role)

        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.memberships.get_membership(
                dictionary_id, target_user_id
            )
            if existing is None:
                raise MembershipNotFoundError(dictionary_id, target_user_id)
            existing.role = role
            existing.updated_at = now
            existing.updated_by = actor_id
            unit_of_work.memberships.update_member(existing)
            unit_of_work.commit()
        return existing

    def remove_member(
        self,
        dictionary_id: UUID,
        owner_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
    ) -> None:
        self._authorization.require(
            dictionary_id, owner_id, actor_id, Permission.MANAGE_MEMBERS
        )
        with self._unit_of_work_factory() as unit_of_work:
            existing = unit_of_work.memberships.get_membership(
                dictionary_id, target_user_id
            )
            if existing is None:
                raise MembershipNotFoundError(dictionary_id, target_user_id)
            unit_of_work.memberships.remove_member(dictionary_id, target_user_id)
            unit_of_work.commit()


class ListMembersService:
    """Read every non-owner member of a dictionary (BH-170)."""

    def __init__(
        self,
        unit_of_work_factory: MembershipsUnitOfWorkFactory,
        authorization: AuthorizationService,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._authorization = authorization

    def list_members(
        self, dictionary_id: UUID, owner_id: UUID, actor_id: UUID
    ) -> list[ProjectMembership]:
        self._authorization.require(dictionary_id, owner_id, actor_id, Permission.VIEW)
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.memberships.list_members(dictionary_id)
