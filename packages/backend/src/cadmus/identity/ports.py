"""Application-owned ports for identity infrastructure."""

from collections.abc import Callable
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.identity.domain import User, VerificationToken


class IdentityRepository(Protocol):
    """Persistence operations needed by registration and verification."""

    def get_user_by_email(self, email: str) -> User | None: ...

    def get_user(self, user_id: UUID) -> User | None: ...

    def get_verification_token(self, token_digest: str) -> VerificationToken | None: ...

    def add_user(self, user: User) -> None: ...

    def add_verification_token(self, token: VerificationToken) -> None: ...


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


class VerificationTokenProvider(Protocol):
    """Secure token generation and digesting boundary."""

    def issue(self) -> tuple[str, str]: ...

    def digest(self, token: str) -> str: ...


class EmailSender(Protocol):
    """Delivery boundary for identity emails."""

    def send_verification(self, recipient: str, verification_url: str) -> None: ...
