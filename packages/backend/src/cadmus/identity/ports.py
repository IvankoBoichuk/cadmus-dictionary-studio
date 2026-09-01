"""Application-owned ports for identity infrastructure."""

from collections.abc import Callable
from dataclasses import dataclass
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.identity.domain import (
    AuthenticatedSession,
    EmailChangeToken,
    GoogleIdentity,
    PasswordResetToken,
    User,
    VerificationToken,
)


class IdentityRepository(Protocol):
    """Persistence operations needed by registration and verification."""

    def get_user_by_email(self, email: str) -> User | None: ...

    def get_user(self, user_id: UUID) -> User | None: ...

    def get_verification_token(self, token_digest: str) -> VerificationToken | None: ...

    def get_password_reset_token(
        self, token_digest: str
    ) -> PasswordResetToken | None: ...

    def get_session(self, token_digest: str) -> AuthenticatedSession | None: ...

    def get_session_by_id(self, session_id: UUID) -> AuthenticatedSession | None: ...

    def get_sessions_for_user(self, user_id: UUID) -> list[AuthenticatedSession]: ...

    def get_google_identity_by_subject(self, subject: str) -> GoogleIdentity | None: ...

    def get_email_change_token(self, token_digest: str) -> EmailChangeToken | None: ...

    def add_user(self, user: User) -> None: ...

    def add_verification_token(self, token: VerificationToken) -> None: ...

    def add_password_reset_token(self, token: PasswordResetToken) -> None: ...

    def add_email_change_token(self, token: EmailChangeToken) -> None: ...

    def add_session(self, session: AuthenticatedSession) -> None: ...

    def add_google_identity(self, identity: GoogleIdentity) -> None: ...

    def delete_session(self, token_digest: str) -> None: ...

    def delete_session_by_id(self, session_id: UUID) -> None: ...

    def delete_sessions_for_user(self, user_id: UUID) -> None: ...

    def delete_other_sessions_for_user(
        self, user_id: UUID, keep_token_digest: str
    ) -> None: ...


class IdentityUnitOfWork(Protocol):
    """Transaction boundary controlled by an identity use case."""

    @property
    def users(self) -> IdentityRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type IdentityUnitOfWorkFactory = Callable[[], IdentityUnitOfWork]


class PasswordHasher(Protocol):
    """One-way password hashing boundary."""

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str | None) -> bool: ...


class VerificationTokenProvider(Protocol):
    """Secure token generation and digesting boundary."""

    def issue(self) -> tuple[str, str]: ...

    def digest(self, token: str) -> str: ...


class SessionTokenProvider(Protocol):
    """Secure session-token generation and digesting boundary."""

    def issue(self) -> tuple[str, str]: ...

    def digest(self, token: str) -> str: ...


class PasswordResetTokenProvider(Protocol):
    """Secure password-reset-token generation and digesting boundary."""

    def issue(self) -> tuple[str, str]: ...

    def digest(self, token: str) -> str: ...


class EmailSender(Protocol):
    """Delivery boundary for identity emails."""

    def send_verification(self, recipient: str, verification_url: str) -> None: ...

    def send_password_reset(self, recipient: str, reset_url: str) -> None: ...

    def send_email_change(self, recipient: str, confirm_url: str) -> None: ...


class GoogleOAuthError(Exception):
    """A Google authorization-code exchange or ID-token verification failure."""


@dataclass(frozen=True)
class GoogleIdentityClaims:
    """Verified identity claims extracted from a Google ID token."""

    subject: str
    email: str
    email_verified: bool


class GoogleOAuthClient(Protocol):
    """Boundary for the Google OAuth 2.0 / OIDC authorization-code exchange."""

    def build_authorization_url(
        self, state: str, nonce: str, code_challenge: str
    ) -> str: ...

    def exchange_code(
        self, code: str, code_verifier: str, expected_nonce: str
    ) -> GoogleIdentityClaims: ...
