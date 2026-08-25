"""Access-control domain objects: project roles and membership (BH-170)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    """A user's standing on one dictionary ("project")."""

    OWNER = "owner"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class Permission(StrEnum):
    """One capability a ``Role`` may or may not grant."""

    VIEW = "view"
    EDIT = "edit"
    REVIEW = "review"
    MANAGE_MEMBERS = "manage_members"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: frozenset(
        {Permission.VIEW, Permission.EDIT, Permission.REVIEW, Permission.MANAGE_MEMBERS}
    ),
    Role.EDITOR: frozenset({Permission.VIEW, Permission.EDIT}),
    Role.REVIEWER: frozenset({Permission.VIEW, Permission.REVIEW}),
    Role.VIEWER: frozenset({Permission.VIEW}),
}

ASSIGNABLE_ROLES: frozenset[Role] = frozenset({Role.EDITOR, Role.REVIEWER, Role.VIEWER})
"""Roles that can be granted through membership management.

``Role.OWNER`` is never a membership row -- it's always the dictionary's own
``owner_id``, which this module never transfers (out of scope for BH-170).
"""


@dataclass
class ProjectMembership:
    """One non-owner collaborator's role on a dictionary."""

    id: UUID
    dictionary_id: UUID
    user_id: UUID
    role: Role
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    updated_by: UUID


class AccessDeniedError(LookupError):
    """Raised when an actor lacks a required permission on a dictionary.

    Deliberately generic and module-agnostic (mirrors
    ``sources.DictionaryAccessError``'s "indistinguishable from not-found"
    shape) -- callers in other modules catch this and re-raise their own
    access error, the same way ``lexicography`` already re-wraps
    ``sources.DictionaryAccessError``.
    """

    def __init__(self, dictionary_id: UUID) -> None:
        super().__init__(f"dictionary {dictionary_id} is not accessible")
        self.dictionary_id = dictionary_id


class DuplicateMembershipError(ValueError):
    """Raised when adding a user who is already a member, or is the owner."""

    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"user {user_id} is already a member of this project")
        self.user_id = user_id


class MembershipNotFoundError(LookupError):
    """Raised when changing or removing a membership that doesn't exist."""

    def __init__(self, dictionary_id: UUID, user_id: UUID) -> None:
        super().__init__(
            f"user {user_id} is not a member of dictionary {dictionary_id}"
        )
        self.dictionary_id = dictionary_id
        self.user_id = user_id


class MemberEmailNotFoundError(ValueError):
    """Raised when inviting an email that doesn't match a registered user."""

    def __init__(self, email: str) -> None:
        super().__init__(f"no registered user with email {email}")
        self.email = email


class InvalidRoleAssignmentError(ValueError):
    """Raised when assigning ``Role.OWNER`` through the membership API."""

    def __init__(self, role: Role) -> None:
        super().__init__(
            f"role {role} cannot be assigned through membership management"
        )
        self.role = role
