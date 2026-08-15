from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import TracebackType
from uuid import UUID

import pytest
from cadmus.identity import (
    AccountStatus,
    ActivationError,
    ActivationFailure,
    AuthenticatedSession,
    DuplicateEmailError,
    RegistrationService,
    RegistrationValidationError,
    User,
    VerificationToken,
)
from cadmus.infrastructure.security import (
    ScryptPasswordHasher,
    SecureVerificationTokenProvider,
)

NOW = datetime(2026, 8, 15, 10, 30, tzinfo=UTC)


@dataclass
class MemoryIdentityRepository:
    users: dict[UUID, User] = field(default_factory=dict)
    tokens: dict[str, VerificationToken] = field(default_factory=dict)
    sessions: dict[str, AuthenticatedSession] = field(default_factory=dict)

    def get_user_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_verification_token(self, token_digest: str) -> VerificationToken | None:
        return self.tokens.get(token_digest)

    def get_session(self, token_digest: str) -> AuthenticatedSession | None:
        return self.sessions.get(token_digest)

    def add_user(self, user: User) -> None:
        self.users[user.id] = user

    def add_verification_token(self, token: VerificationToken) -> None:
        self.tokens[token.token_digest] = token

    def add_session(self, session: AuthenticatedSession) -> None:
        self.sessions[session.token_digest] = session


class MemoryUnitOfWork:
    def __init__(self, repository: MemoryIdentityRepository) -> None:
        self.users = repository
        self.committed = False

    def __enter__(self) -> "MemoryUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.committed = True


class StubPasswordHasher:
    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str | None) -> bool:
        return password_hash == f"hashed:{password}"


class StubTokenProvider:
    def issue(self) -> tuple[str, str]:
        return "raw-token", "digest:raw-token"

    def digest(self, token: str) -> str:
        return f"digest:{token}"


@dataclass
class RecordingEmailSender:
    deliveries: list[tuple[str, str]] = field(default_factory=list)

    def send_verification(self, recipient: str, verification_url: str) -> None:
        self.deliveries.append((recipient, verification_url))


class FailingEmailSender:
    def send_verification(self, recipient: str, verification_url: str) -> None:
        raise ConnectionError("SMTP is unavailable")


def create_service(
    repository: MemoryIdentityRepository,
    email_sender: RecordingEmailSender,
    clock: datetime = NOW,
) -> RegistrationService:
    return RegistrationService(
        unit_of_work_factory=lambda: MemoryUnitOfWork(repository),
        password_hasher=StubPasswordHasher(),
        token_provider=StubTokenProvider(),
        email_sender=email_sender,
        public_web_url="https://cadmus.example",
        token_lifetime=timedelta(hours=24),
        clock=lambda: clock,
    )


def test_registration_creates_pending_account_and_sends_expiring_token() -> None:
    repository = MemoryIdentityRepository()
    email_sender = RecordingEmailSender()

    user = create_service(repository, email_sender).register(
        "  Researcher@Example.COM ",
        "long-enough-password",
        "long-enough-password",
    )

    assert user.email == "researcher@example.com"
    assert user.status is AccountStatus.PENDING_VERIFICATION
    assert user.password_hash == "hashed:long-enough-password"
    assert repository.users[user.id] is user
    token = repository.tokens["digest:raw-token"]
    assert token.expires_at == NOW + timedelta(hours=24)
    assert token.consumed_at is None
    assert email_sender.deliveries == [
        (
            "researcher@example.com",
            "https://cadmus.example/verify-email#token=raw-token",
        )
    ]


@pytest.mark.parametrize(
    ("email", "password", "confirmation", "field"),
    [
        ("not-an-email", "long-enough-password", "long-enough-password", "email"),
        ("valid@example.com", "short", "short", "password"),
        (
            "valid@example.com",
            "long-enough-password",
            "different-password",
            "password_confirmation",
        ),
    ],
)
def test_registration_rejects_field_addressable_invalid_input(
    email: str,
    password: str,
    confirmation: str,
    field: str,
) -> None:
    repository = MemoryIdentityRepository()

    with pytest.raises(RegistrationValidationError) as error:
        create_service(repository, RecordingEmailSender()).register(
            email,
            password,
            confirmation,
        )

    assert field in error.value.errors
    assert repository.users == {}


def test_registration_rejects_normalized_duplicate_email() -> None:
    repository = MemoryIdentityRepository()
    service = create_service(repository, RecordingEmailSender())
    service.register(
        "user@example.com",
        "long-enough-password",
        "long-enough-password",
    )

    with pytest.raises(DuplicateEmailError):
        service.register(
            "USER@example.com",
            "another-password",
            "another-password",
        )


def test_registration_does_not_commit_when_email_delivery_fails() -> None:
    repository = MemoryIdentityRepository()
    unit_of_work = MemoryUnitOfWork(repository)
    service = RegistrationService(
        unit_of_work_factory=lambda: unit_of_work,
        password_hasher=StubPasswordHasher(),
        token_provider=StubTokenProvider(),
        email_sender=FailingEmailSender(),
        public_web_url="https://cadmus.example",
        clock=lambda: NOW,
    )

    with pytest.raises(ConnectionError, match="SMTP is unavailable"):
        service.register(
            "user@example.com",
            "long-enough-password",
            "long-enough-password",
        )

    assert unit_of_work.committed is False


def test_verification_activates_account_once() -> None:
    repository = MemoryIdentityRepository()
    service = create_service(repository, RecordingEmailSender())
    user = service.register(
        "user@example.com",
        "long-enough-password",
        "long-enough-password",
    )

    activated = service.activate("raw-token")

    assert activated is user
    assert user.status is AccountStatus.ACTIVE
    assert user.activated_at == NOW
    assert repository.tokens["digest:raw-token"].consumed_at == NOW

    with pytest.raises(ActivationError) as error:
        service.activate("raw-token")
    assert error.value.reason is ActivationFailure.USED


def test_verification_rejects_expired_and_unknown_tokens() -> None:
    repository = MemoryIdentityRepository()
    sender = RecordingEmailSender()
    create_service(repository, sender, NOW - timedelta(hours=25)).register(
        "user@example.com",
        "long-enough-password",
        "long-enough-password",
    )
    service = create_service(repository, sender, NOW)

    with pytest.raises(ActivationError) as expired:
        service.activate("raw-token")
    assert expired.value.reason is ActivationFailure.EXPIRED

    with pytest.raises(ActivationError) as invalid:
        service.activate("unknown")
    assert invalid.value.reason is ActivationFailure.INVALID


def test_security_adapters_never_store_plaintext_credentials() -> None:
    password_hash = ScryptPasswordHasher().hash("long-enough-password")
    raw_token, digest = SecureVerificationTokenProvider().issue()

    assert "long-enough-password" not in password_hash
    assert password_hash.startswith("scrypt$32768$8$3$")
    assert raw_token not in digest
    assert len(digest) == 64
