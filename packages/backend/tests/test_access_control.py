"""BH-170: project RBAC (roles, permissions, and membership management)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.access import (
    ASSIGNABLE_ROLES,
    ROLE_PERMISSIONS,
    AccessDeniedError,
    AuthorizationService,
    DuplicateMembershipError,
    InvalidRoleAssignmentError,
    ListMembersService,
    ManageMembersService,
    MembershipNotFoundError,
    Permission,
    ProjectMembership,
    Role,
)

NOW = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)


@dataclass
class MemoryMembershipsRepository:
    memberships: dict[tuple[UUID, UUID], ProjectMembership] = field(
        default_factory=dict
    )

    def get_membership(
        self, dictionary_id: UUID, user_id: UUID
    ) -> ProjectMembership | None:
        return self.memberships.get((dictionary_id, user_id))

    def list_members(self, dictionary_id: UUID) -> list[ProjectMembership]:
        return [
            membership
            for (dict_id, _), membership in self.memberships.items()
            if dict_id == dictionary_id
        ]

    def add_member(self, membership: ProjectMembership) -> None:
        self.memberships[(membership.dictionary_id, membership.user_id)] = membership

    def update_member(self, membership: ProjectMembership) -> None:
        self.memberships[(membership.dictionary_id, membership.user_id)] = membership

    def remove_member(self, dictionary_id: UUID, user_id: UUID) -> None:
        self.memberships.pop((dictionary_id, user_id), None)


class MemoryMembershipsUnitOfWork:
    def __init__(self, repository: MemoryMembershipsRepository) -> None:
        self.memberships = repository

    def __enter__(self) -> "MemoryMembershipsUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        pass


class Fixture:
    """Wires a fake memberships repository behind the access-control services."""

    def __init__(self) -> None:
        self.owner_id = uuid4()
        self.dictionary_id = uuid4()
        self.repository = MemoryMembershipsRepository()
        self.authorization = AuthorizationService(
            membership_unit_of_work_factory=lambda: MemoryMembershipsUnitOfWork(
                self.repository
            )
        )
        self.manage_service = ManageMembersService(
            unit_of_work_factory=lambda: MemoryMembershipsUnitOfWork(self.repository),
            authorization=self.authorization,
        )
        self.list_service = ListMembersService(
            unit_of_work_factory=lambda: MemoryMembershipsUnitOfWork(self.repository),
            authorization=self.authorization,
        )

    def add_member(self, role: Role) -> UUID:
        user_id = uuid4()
        self.repository.memberships[(self.dictionary_id, user_id)] = ProjectMembership(
            id=uuid4(),
            dictionary_id=self.dictionary_id,
            user_id=user_id,
            role=role,
            created_at=NOW,
            created_by=self.owner_id,
            updated_at=NOW,
            updated_by=self.owner_id,
        )
        return user_id


@pytest.mark.parametrize(
    ("role", "permission", "allowed"),
    [
        (Role.OWNER, Permission.VIEW, True),
        (Role.OWNER, Permission.EDIT, True),
        (Role.OWNER, Permission.REVIEW, True),
        (Role.OWNER, Permission.MANAGE_MEMBERS, True),
        (Role.EDITOR, Permission.VIEW, True),
        (Role.EDITOR, Permission.EDIT, True),
        (Role.EDITOR, Permission.REVIEW, False),
        (Role.EDITOR, Permission.MANAGE_MEMBERS, False),
        (Role.REVIEWER, Permission.VIEW, True),
        (Role.REVIEWER, Permission.REVIEW, True),
        (Role.REVIEWER, Permission.EDIT, False),
        (Role.REVIEWER, Permission.MANAGE_MEMBERS, False),
        (Role.VIEWER, Permission.VIEW, True),
        (Role.VIEWER, Permission.EDIT, False),
        (Role.VIEWER, Permission.REVIEW, False),
        (Role.VIEWER, Permission.MANAGE_MEMBERS, False),
    ],
)
def test_role_permission_matrix(
    role: Role, permission: Permission, allowed: bool
) -> None:
    assert (permission in ROLE_PERMISSIONS[role]) is allowed


def test_assignable_roles_excludes_owner() -> None:
    assert Role.OWNER not in ASSIGNABLE_ROLES
    assert ASSIGNABLE_ROLES == {Role.EDITOR, Role.REVIEWER, Role.VIEWER}


def test_resolve_role_returns_owner_for_the_dictionary_owner() -> None:
    fixture = Fixture()

    role = fixture.authorization.resolve_role(
        fixture.dictionary_id, fixture.owner_id, fixture.owner_id
    )

    assert role is Role.OWNER


def test_resolve_role_returns_none_for_a_stranger() -> None:
    fixture = Fixture()

    role = fixture.authorization.resolve_role(
        fixture.dictionary_id, fixture.owner_id, uuid4()
    )

    assert role is None


def test_resolve_role_returns_none_without_a_membership_backing() -> None:
    authorization = AuthorizationService()

    role = authorization.resolve_role(uuid4(), uuid4(), uuid4())

    assert role is None


def test_resolve_role_returns_the_membership_role() -> None:
    fixture = Fixture()
    member_id = fixture.add_member(Role.EDITOR)

    role = fixture.authorization.resolve_role(
        fixture.dictionary_id, fixture.owner_id, member_id
    )

    assert role is Role.EDITOR


def test_require_raises_access_denied_for_a_stranger() -> None:
    fixture = Fixture()

    with pytest.raises(AccessDeniedError):
        fixture.authorization.require(
            fixture.dictionary_id, fixture.owner_id, uuid4(), Permission.VIEW
        )


def test_require_raises_access_denied_when_role_lacks_permission() -> None:
    fixture = Fixture()
    viewer_id = fixture.add_member(Role.VIEWER)

    with pytest.raises(AccessDeniedError):
        fixture.authorization.require(
            fixture.dictionary_id, fixture.owner_id, viewer_id, Permission.EDIT
        )


def test_owner_can_add_a_member() -> None:
    fixture = Fixture()
    target_id = uuid4()

    membership = fixture.manage_service.add_member(
        fixture.dictionary_id,
        fixture.owner_id,
        fixture.owner_id,
        target_id,
        Role.EDITOR,
    )

    assert membership.role is Role.EDITOR
    assert (
        fixture.repository.memberships[(fixture.dictionary_id, target_id)] is membership
    )


def test_add_member_rejects_a_non_owner_actor() -> None:
    fixture = Fixture()
    editor_id = fixture.add_member(Role.EDITOR)

    with pytest.raises(AccessDeniedError):
        fixture.manage_service.add_member(
            fixture.dictionary_id, fixture.owner_id, editor_id, uuid4(), Role.VIEWER
        )


def test_add_member_rejects_assigning_the_owner_role() -> None:
    fixture = Fixture()

    with pytest.raises(InvalidRoleAssignmentError):
        fixture.manage_service.add_member(
            fixture.dictionary_id,
            fixture.owner_id,
            fixture.owner_id,
            uuid4(),
            Role.OWNER,
        )


def test_add_member_rejects_adding_the_owner_as_a_member() -> None:
    fixture = Fixture()

    with pytest.raises(DuplicateMembershipError):
        fixture.manage_service.add_member(
            fixture.dictionary_id,
            fixture.owner_id,
            fixture.owner_id,
            fixture.owner_id,
            Role.EDITOR,
        )


def test_add_member_rejects_a_duplicate_member() -> None:
    fixture = Fixture()
    member_id = fixture.add_member(Role.VIEWER)

    with pytest.raises(DuplicateMembershipError):
        fixture.manage_service.add_member(
            fixture.dictionary_id,
            fixture.owner_id,
            fixture.owner_id,
            member_id,
            Role.EDITOR,
        )


def test_owner_can_change_a_member_s_role() -> None:
    fixture = Fixture()
    member_id = fixture.add_member(Role.VIEWER)

    updated = fixture.manage_service.change_role(
        fixture.dictionary_id,
        fixture.owner_id,
        fixture.owner_id,
        member_id,
        Role.REVIEWER,
    )

    assert updated.role is Role.REVIEWER


def test_change_role_missing_member_raises_not_found() -> None:
    fixture = Fixture()

    with pytest.raises(MembershipNotFoundError):
        fixture.manage_service.change_role(
            fixture.dictionary_id,
            fixture.owner_id,
            fixture.owner_id,
            uuid4(),
            Role.VIEWER,
        )


def test_owner_can_remove_a_member() -> None:
    fixture = Fixture()
    member_id = fixture.add_member(Role.EDITOR)

    fixture.manage_service.remove_member(
        fixture.dictionary_id, fixture.owner_id, fixture.owner_id, member_id
    )

    assert (fixture.dictionary_id, member_id) not in fixture.repository.memberships


def test_remove_member_missing_member_raises_not_found() -> None:
    fixture = Fixture()

    with pytest.raises(MembershipNotFoundError):
        fixture.manage_service.remove_member(
            fixture.dictionary_id, fixture.owner_id, fixture.owner_id, uuid4()
        )


def test_viewer_can_list_members() -> None:
    fixture = Fixture()
    viewer_id = fixture.add_member(Role.VIEWER)

    members = fixture.list_service.list_members(
        fixture.dictionary_id, fixture.owner_id, viewer_id
    )

    assert len(members) == 1


def test_list_members_rejects_a_stranger() -> None:
    fixture = Fixture()

    with pytest.raises(AccessDeniedError):
        fixture.list_service.list_members(
            fixture.dictionary_id, fixture.owner_id, uuid4()
        )
