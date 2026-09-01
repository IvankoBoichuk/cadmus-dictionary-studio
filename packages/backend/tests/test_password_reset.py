from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.identity import (
    AccountStatus,
    AuthenticatedSession,
    EmailChangeToken,
    GoogleIdentity,
    PasswordResetError,
    PasswordResetFailure,
    PasswordResetService,
    PasswordResetToken,
    PasswordResetValidationError,
    User,
    VerificationToken,
)

NOW = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)


@dataclass
class MemoryIdentityRepository:
    users: dict[UUID, User] = field(default_factory=dict)
    reset_tokens: dict[str, PasswordResetToken] = field(default_factory=dict)
    sessions: dict[str, AuthenticatedSession] = field(default_factory=dict)

    def get_user_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_verification_token(self, token_digest: str) -> VerificationToken | None:
        raise AssertionError("not used by password reset")

    def get_password_reset_token(self, token_digest: str) -> PasswordResetToken | None:
        return self.reset_tokens.get(token_digest)

    def get_session(self, token_digest: str) -> AuthenticatedSession | None:
        return self.sessions.get(token_digest)

    def get_google_identity_by_subject(self, subject: str) -> GoogleIdentity | None:
        return None

    def add_user(self, user: User) -> None:
        self.users[user.id] = user

    def add_verification_token(self, token: VerificationToken) -> None:
        raise AssertionError("not used by password reset")

    def add_password_reset_token(self, token: PasswordResetToken) -> None:
        self.reset_tokens[token.token_digest] = token

    def add_session(self, session: AuthenticatedSession) -> None:
        self.sessions[session.token_digest] = session

    def add_google_identity(self, identity: GoogleIdentity) -> None:
        raise AssertionError("not used by password reset")

    def delete_session(self, token_digest: str) -> None:
        self.sessions.pop(token_digest, None)

    def delete_sessions_for_user(self, user_id: UUID) -> None:
        for token_digest in [
            digest
            for digest, session in self.sessions.items()
            if session.user_id == user_id
        ]:
            self.sessions.pop(token_digest, None)

    def get_session_by_id(self, session_id: UUID) -> AuthenticatedSession | None:
        raise AssertionError("not used by password reset")

    def get_sessions_for_user(self, user_id: UUID) -> list[AuthenticatedSession]:
        raise AssertionError("not used by password reset")

    def get_email_change_token(self, token_digest: str) -> EmailChangeToken | None:
        return None

    def add_email_change_token(self, token: EmailChangeToken) -> None:
        raise AssertionError("not used by password reset")

    def delete_session_by_id(self, session_id: UUID) -> None:
        raise AssertionError("not used by password reset")

    def delete_other_sessions_for_user(
        self, user_id: UUID, keep_token_digest: str
    ) -> None:
        raise AssertionError("not used by password reset")


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
        return "raw-token", self.digest("raw-token")

    def digest(self, token: str) -> str:
        return sha256(token.encode()).hexdigest()


@dataclass
class RecordingEmailSender:
    deliveries: list[tuple[str, str]] = field(default_factory=list)

    def send_verification(self, recipient: str, verification_url: str) -> None:
        raise AssertionError("not used by password reset")

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        self.deliveries.append((recipient, reset_url))

    def send_email_change(self, recipient: str, confirm_url: str) -> None:
        raise AssertionError("not used by password reset")


def active_user(email: str = "researcher@example.com") -> User:
    return User(
        id=uuid4(),
        email=email,
        password_hash="hashed:old-password",
        status=AccountStatus.ACTIVE,
        created_at=NOW - timedelta(days=1),
        activated_at=NOW - timedelta(hours=12),
    )


def create_service(
    repository: MemoryIdentityRepository,
    email_sender: RecordingEmailSender,
    clock: datetime = NOW,
) -> PasswordResetService:
    return PasswordResetService(
        unit_of_work_factory=lambda: MemoryUnitOfWork(repository),
        password_hasher=StubPasswordHasher(),
        token_provider=StubTokenProvider(),
        email_sender=email_sender,
        public_web_url="https://cadmus.example",
        token_lifetime=timedelta(hours=1),
        clock=lambda: clock,
    )


def test_request_reset_issues_expiring_token_and_emails_active_user() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})
    email_sender = RecordingEmailSender()

    create_service(repository, email_sender).request_reset("  Researcher@Example.COM ")

    token = repository.reset_tokens[sha256(b"raw-token").hexdigest()]
    assert token.user_id == user.id
    assert token.expires_at == NOW + timedelta(hours=1)
    assert token.consumed_at is None
    assert email_sender.deliveries == [
        (
            "researcher@example.com",
            "https://cadmus.example/reset-password#token=raw-token",
        )
    ]


def test_request_reset_is_silent_no_op_for_missing_email() -> None:
    repository = MemoryIdentityRepository()
    email_sender = RecordingEmailSender()

    create_service(repository, email_sender).request_reset("missing@example.com")

    assert repository.reset_tokens == {}
    assert email_sender.deliveries == []


def test_request_reset_is_silent_no_op_for_unverified_account() -> None:
    user = active_user()
    user.status = AccountStatus.PENDING_VERIFICATION
    user.activated_at = None
    repository = MemoryIdentityRepository(users={user.id: user})
    email_sender = RecordingEmailSender()

    create_service(repository, email_sender).request_reset(user.email)

    assert repository.reset_tokens == {}
    assert email_sender.deliveries == []


def test_reset_password_updates_hash_consumes_token_and_ends_all_sessions() -> None:
    user = active_user()
    other_user = active_user(email="other@example.com")
    own_session = AuthenticatedSession(
        id=uuid4(),
        user_id=user.id,
        token_digest=sha256(b"own-session").hexdigest(),
        created_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=1),
    )
    other_session = AuthenticatedSession(
        id=uuid4(),
        user_id=other_user.id,
        token_digest=sha256(b"other-session").hexdigest(),
        created_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=1),
    )
    repository = MemoryIdentityRepository(
        users={user.id: user, other_user.id: other_user},
        sessions={
            own_session.token_digest: own_session,
            other_session.token_digest: other_session,
        },
    )
    email_sender = RecordingEmailSender()
    service = create_service(repository, email_sender)
    service.request_reset(user.email)

    service.reset_password("raw-token", "new-long-password", "new-long-password")

    assert user.password_hash == "hashed:new-long-password"
    token = repository.reset_tokens[sha256(b"raw-token").hexdigest()]
    assert token.consumed_at == NOW
    assert own_session.token_digest not in repository.sessions
    assert other_session.token_digest in repository.sessions


def test_reset_password_rejects_used_token() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})
    service = create_service(repository, RecordingEmailSender())
    service.request_reset(user.email)
    service.reset_password("raw-token", "new-long-password", "new-long-password")

    with pytest.raises(PasswordResetError) as error:
        service.reset_password("raw-token", "another-password", "another-password")

    assert error.value.reason is PasswordResetFailure.USED
    assert user.password_hash == "hashed:new-long-password"


def test_reset_password_rejects_expired_token() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})
    email_sender = RecordingEmailSender()
    create_service(repository, email_sender, NOW - timedelta(hours=2)).request_reset(
        user.email
    )
    service = create_service(repository, email_sender, NOW)

    with pytest.raises(PasswordResetError) as error:
        service.reset_password("raw-token", "new-long-password", "new-long-password")

    assert error.value.reason is PasswordResetFailure.EXPIRED
    assert user.password_hash == "hashed:old-password"


def test_reset_password_rejects_unknown_token() -> None:
    repository = MemoryIdentityRepository()
    service = create_service(repository, RecordingEmailSender())

    with pytest.raises(PasswordResetError) as error:
        service.reset_password("unknown", "new-long-password", "new-long-password")

    assert error.value.reason is PasswordResetFailure.INVALID


@pytest.mark.parametrize(
    ("password", "confirmation", "field"),
    [
        ("short", "short", "password"),
        ("long-enough-password", "different-password", "password_confirmation"),
    ],
)
def test_reset_password_rejects_field_addressable_invalid_input(
    password: str, confirmation: str, field: str
) -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})
    service = create_service(repository, RecordingEmailSender())
    service.request_reset(user.email)

    with pytest.raises(PasswordResetValidationError) as error:
        service.reset_password("raw-token", password, confirmation)

    assert field in error.value.errors
    assert user.password_hash == "hashed:old-password"
    token = repository.reset_tokens[sha256(b"raw-token").hexdigest()]
    assert token.consumed_at is None
