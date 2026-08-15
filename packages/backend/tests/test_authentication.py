from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.identity import (
    AccountStatus,
    AuthenticatedSession,
    AuthenticationError,
    AuthenticationFailure,
    AuthenticationService,
    User,
    VerificationToken,
)
from cadmus.infrastructure.security import ScryptPasswordHasher

NOW = datetime(2026, 8, 15, 14, 0, tzinfo=UTC)


@dataclass
class MemoryIdentityRepository:
    users: dict[UUID, User] = field(default_factory=dict)
    sessions: dict[str, AuthenticatedSession] = field(default_factory=dict)

    def get_user_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_verification_token(self, token_digest: str) -> VerificationToken | None:
        return None

    def get_session(self, token_digest: str) -> AuthenticatedSession | None:
        return self.sessions.get(token_digest)

    def add_user(self, user: User) -> None:
        self.users[user.id] = user

    def add_verification_token(self, token: VerificationToken) -> None:
        raise AssertionError("not used by authentication")

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


@dataclass
class StubPasswordHasher:
    verified: list[tuple[str, str | None]] = field(default_factory=list)

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str | None) -> bool:
        self.verified.append((password, password_hash))
        return password_hash == f"hashed:{password}"


class StubSessionTokenProvider:
    def issue(self) -> tuple[str, str]:
        return "raw-session-token", self.digest("raw-session-token")

    def digest(self, token: str) -> str:
        return sha256(token.encode()).hexdigest()


def active_user(password: str = "correct-password") -> User:
    return User(
        id=uuid4(),
        email="researcher@example.com",
        password_hash=f"hashed:{password}",
        status=AccountStatus.ACTIVE,
        created_at=NOW - timedelta(days=1),
        activated_at=NOW - timedelta(hours=12),
    )


def create_service(
    repository: MemoryIdentityRepository,
    password_hasher: StubPasswordHasher | None = None,
) -> AuthenticationService:
    return AuthenticationService(
        unit_of_work_factory=lambda: MemoryUnitOfWork(repository),
        password_hasher=password_hasher or StubPasswordHasher(),
        session_token_provider=StubSessionTokenProvider(),
        session_lifetime=timedelta(hours=8),
        clock=lambda: NOW,
    )


def test_login_normalizes_email_and_creates_only_a_digest_backed_session() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})

    result = create_service(repository).login(
        "  Researcher@Example.COM ", "correct-password"
    )

    assert result.user is user
    assert result.session_token == "raw-session-token"
    session = repository.sessions[sha256(b"raw-session-token").hexdigest()]
    assert session.user_id == user.id
    assert session.created_at == NOW
    assert session.expires_at == NOW + timedelta(hours=8)
    assert "raw-session-token" not in session.token_digest


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("researcher@example.com", "wrong-password"),
        ("missing@example.com", "wrong-password"),
    ],
)
def test_login_returns_one_safe_error_for_wrong_email_or_password(
    email: str, password: str
) -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})
    verifier = StubPasswordHasher()

    with pytest.raises(AuthenticationError) as error:
        create_service(repository, verifier).login(email, password)

    assert error.value.reason is AuthenticationFailure.INVALID_CREDENTIALS
    assert repository.sessions == {}
    assert verifier.verified[0][0] == password


def test_login_rejects_unverified_account_only_after_password_matches() -> None:
    user = active_user()
    user.status = AccountStatus.PENDING_VERIFICATION
    user.activated_at = None
    repository = MemoryIdentityRepository(users={user.id: user})
    service = create_service(repository)

    with pytest.raises(AuthenticationError) as unverified:
        service.login(user.email, "correct-password")
    assert unverified.value.reason is AuthenticationFailure.UNVERIFIED_ACCOUNT

    with pytest.raises(AuthenticationError) as wrong_password:
        service.login(user.email, "wrong-password")
    assert wrong_password.value.reason is AuthenticationFailure.INVALID_CREDENTIALS
    assert repository.sessions == {}


def test_authenticate_resolves_valid_session_and_rejects_expired_session() -> None:
    user = active_user()
    valid_session = AuthenticatedSession(
        id=uuid4(),
        user_id=user.id,
        token_digest=sha256(b"valid").hexdigest(),
        created_at=NOW - timedelta(hours=1),
        expires_at=NOW + timedelta(hours=1),
    )
    expired_session = AuthenticatedSession(
        id=uuid4(),
        user_id=user.id,
        token_digest=sha256(b"expired").hexdigest(),
        created_at=NOW - timedelta(hours=2),
        expires_at=NOW,
    )
    repository = MemoryIdentityRepository(
        users={user.id: user},
        sessions={
            valid_session.token_digest: valid_session,
            expired_session.token_digest: expired_session,
        },
    )
    service = create_service(repository)

    assert service.authenticate("valid") is user
    with pytest.raises(AuthenticationError) as error:
        service.authenticate("expired")
    assert error.value.reason is AuthenticationFailure.INVALID_SESSION


def test_scrypt_verifier_accepts_only_the_original_password() -> None:
    password_hasher = ScryptPasswordHasher()
    password_hash = password_hasher.hash("correct-password")

    assert password_hasher.verify("correct-password", password_hash) is True
    assert password_hasher.verify("wrong-password", password_hash) is False
    assert password_hasher.verify("wrong-password", None) is False
