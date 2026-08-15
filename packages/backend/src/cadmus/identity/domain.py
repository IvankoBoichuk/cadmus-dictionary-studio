"""Identity domain objects and invariants."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AccountStatus(StrEnum):
    """Lifecycle states currently owned by the identity module."""

    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"


@dataclass
class User:
    """A registered Cadmus user."""

    id: UUID
    email: str
    password_hash: str
    status: AccountStatus
    created_at: datetime
    activated_at: datetime | None = None

    def activate(self, activated_at: datetime) -> None:
        """Activate a pending user without weakening an already active account."""
        if self.status is not AccountStatus.PENDING_VERIFICATION:
            raise ValueError("only a pending account can be activated")
        self.status = AccountStatus.ACTIVE
        self.activated_at = activated_at


@dataclass
class VerificationToken:
    """A single-use, expiring email verification credential."""

    id: UUID
    user_id: UUID
    token_digest: str
    expires_at: datetime
    created_at: datetime
    consumed_at: datetime | None = None

    def consume(self, consumed_at: datetime) -> None:
        """Mark this token as irreversibly used."""
        if self.consumed_at is not None:
            raise ValueError("verification token has already been consumed")
        self.consumed_at = consumed_at
