from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.identity import (
    AccountService,
    AccountStatus,
    AuthenticatedSession,
    AuthenticationError,
    AuthenticationFailure,
    EmailChangeError,
    EmailChangeFailure,
    EmailChangeToken,
    EmailChangeValidationError,
    GoogleIdentity,
    PasswordResetToken,
    PasswordResetValidationError,
    ProfileValidationError,
    SessionNotFoundError,
    User,
    VerificationToken,
)

NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


@dataclass
class MemoryIdentityRepository:
    users: dict[UUID, User] = field(default_factory=dict)
    sessions: dict[UUID, AuthenticatedSession] = field(default_factory=dict)
    email_change_tokens: dict[str, EmailChangeToken] = field(default_factory=dict)

    def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_user_by_email(self, email: str) -> User | None:
        return next((u for u in self.users.values() if u.email == email), None)

    def get_session_by_id(self, session_id: UUID) -> AuthenticatedSession | None:
        return self.sessions.get(session_id)

    def get_sessions_for_user(self, user_id: UUID) -> list[AuthenticatedSession]:
        return [s for s in self.sessions.values() if s.user_id == user_id]

    def get_email_change_token(self, token_digest: str) -> EmailChangeToken | None:
        return self.email_change_tokens.get(token_digest)

    def add_email_change_token(self, token: EmailChangeToken) -> None:
        self.email_change_tokens[token.token_digest] = token

    def delete_session_by_id(self, session_id: UUID) -> None:
        self.sessions.pop(session_id, None)

    def delete_sessions_for_user(self, user_id: UUID) -> None:
        for sid in [s.id for s in self.sessions.values() if s.user_id == user_id]:
            self.sessions.pop(sid, None)

    def delete_other_sessions_for_user(
        self, user_id: UUID, keep_token_digest: str
    ) -> None:
        for sid in [
            s.id
            for s in self.sessions.values()
            if s.user_id == user_id and s.token_digest != keep_token_digest
        ]:
            self.sessions.pop(sid, None)

    # --- unused by AccountService, present only to satisfy the port ---------

    def get_verification_token(self, token_digest: str) -> VerificationToken | None:
        raise AssertionError("not used by account service")

    def get_password_reset_token(self, token_digest: str) -> PasswordResetToken | None:
        raise AssertionError("not used by account service")

    def get_session(self, token_digest: str) -> AuthenticatedSession | None:
        raise AssertionError("not used by account service")

    def get_google_identity_by_subject(self, subject: str) -> GoogleIdentity | None:
        raise AssertionError("not used by account service")

    def add_user(self, user: User) -> None:
        raise AssertionError("not used by account service")

    def add_verification_token(self, token: VerificationToken) -> None:
        raise AssertionError("not used by account service")

    def add_password_reset_token(self, token: PasswordResetToken) -> None:
        raise AssertionError("not used by account service")

    def add_session(self, session: AuthenticatedSession) -> None:
        raise AssertionError("not used by account service")

    def add_google_identity(self, identity: GoogleIdentity) -> None:
        raise AssertionError("not used by account service")

    def delete_session(self, token_digest: str) -> None:
        raise AssertionError("not used by account service")


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
    email_changes: list[tuple[str, str]] = field(default_factory=list)

    def send_verification(self, recipient: str, verification_url: str) -> None:
        raise AssertionError("not used by account service")

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        raise AssertionError("not used by account service")

    def send_email_change(self, recipient: str, confirm_url: str) -> None:
        self.email_changes.append((recipient, confirm_url))


def active_user(email: str = "researcher@example.com") -> User:
    return User(
        id=uuid4(),
        email=email,
        password_hash="hashed:old-password",
        status=AccountStatus.ACTIVE,
        created_at=NOW - timedelta(days=1),
        activated_at=NOW - timedelta(hours=12),
    )


def session_for(
    user: User, raw_token: str, *, created_offset: timedelta = timedelta(hours=1)
) -> AuthenticatedSession:
    return AuthenticatedSession(
        id=uuid4(),
        user_id=user.id,
        token_digest=sha256(raw_token.encode()).hexdigest(),
        created_at=NOW - created_offset,
        expires_at=NOW + timedelta(hours=6),
        user_agent="Firefox",
    )


def create_service(
    repository: MemoryIdentityRepository,
    email_sender: RecordingEmailSender | None = None,
) -> AccountService:
    return AccountService(
        unit_of_work_factory=lambda: MemoryUnitOfWork(repository),
        password_hasher=StubPasswordHasher(),
        session_token_provider=StubTokenProvider(),
        email_change_token_provider=StubTokenProvider(),
        email_sender=email_sender or RecordingEmailSender(),
        public_web_url="https://cadmus.example",
        token_lifetime=timedelta(hours=24),
        clock=lambda: NOW,
    )


# --- update_profile ---------------------------------------------------------


def test_update_profile_sets_and_trims_name() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})

    updated = create_service(repository).update_profile(user.id, "  Ada Lovelace  ")

    assert updated.name == "Ada Lovelace"
    assert user.name == "Ada Lovelace"


def test_update_profile_clears_name_when_blank() -> None:
    user = active_user()
    user.name = "Ada"
    repository = MemoryIdentityRepository(users={user.id: user})

    create_service(repository).update_profile(user.id, "   ")

    assert user.name is None


def test_update_profile_rejects_overlong_name() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})

    with pytest.raises(ProfileValidationError) as error:
        create_service(repository).update_profile(user.id, "x" * 201)

    assert "name" in error.value.errors


# --- change_password ------------------------------------------------------


def test_change_password_updates_hash_and_keeps_only_current_session() -> None:
    user = active_user()
    current = session_for(user, "current-token")
    other = session_for(user, "other-token")
    repository = MemoryIdentityRepository(
        users={user.id: user},
        sessions={current.id: current, other.id: other},
    )

    create_service(repository).change_password(
        user_id=user.id,
        current_raw_token="current-token",
        current_password="old-password",
        new_password="a-brand-new-password",
        new_password_confirmation="a-brand-new-password",
    )

    assert user.password_hash == "hashed:a-brand-new-password"
    assert set(repository.sessions) == {current.id}


def test_change_password_rejects_wrong_current_password() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})

    with pytest.raises(AuthenticationError) as error:
        create_service(repository).change_password(
            user_id=user.id,
            current_raw_token="current-token",
            current_password="not-the-password",
            new_password="a-brand-new-password",
            new_password_confirmation="a-brand-new-password",
        )

    assert error.value.reason is AuthenticationFailure.INVALID_CREDENTIALS
    assert user.password_hash == "hashed:old-password"


def test_change_password_rejects_weak_new_password() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})

    with pytest.raises(PasswordResetValidationError):
        create_service(repository).change_password(
            user_id=user.id,
            current_raw_token="current-token",
            current_password="old-password",
            new_password="short",
            new_password_confirmation="short",
        )


# --- request_email_change ------------------------------------------------


def test_request_email_change_stores_token_and_emails_new_address() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})
    email_sender = RecordingEmailSender()

    create_service(repository, email_sender).request_email_change(
        user.id, "  New.Address@Example.COM ", "old-password"
    )

    token = repository.email_change_tokens[sha256(b"raw-token").hexdigest()]
    assert token.new_email == "new.address@example.com"
    assert token.expires_at == NOW + timedelta(hours=24)
    assert email_sender.email_changes == [
        (
            "new.address@example.com",
            "https://cadmus.example/confirm-email-change#token=raw-token",
        )
    ]


def test_request_email_change_rejects_wrong_password() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})

    with pytest.raises(AuthenticationError):
        create_service(repository).request_email_change(
            user.id, "new@example.com", "wrong"
        )

    assert repository.email_change_tokens == {}


def test_request_email_change_rejects_already_registered_email() -> None:
    user = active_user()
    taken = active_user(email="taken@example.com")
    repository = MemoryIdentityRepository(users={user.id: user, taken.id: taken})

    with pytest.raises(EmailChangeValidationError) as error:
        create_service(repository).request_email_change(
            user.id, "taken@example.com", "old-password"
        )

    assert "new_email" in error.value.errors


def test_request_email_change_rejects_malformed_email() -> None:
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})

    with pytest.raises(EmailChangeValidationError):
        create_service(repository).request_email_change(
            user.id, "not-an-email", "old-password"
        )


# --- confirm_email_change ----------------------------------------------


def _pending_token(user: User, new_email: str = "new@example.com") -> EmailChangeToken:
    return EmailChangeToken(
        id=uuid4(),
        user_id=user.id,
        new_email=new_email,
        token_digest=sha256(b"raw-token").hexdigest(),
        created_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=1),
    )


def test_confirm_email_change_moves_email_and_ends_all_sessions() -> None:
    user = active_user()
    token = _pending_token(user)
    session = session_for(user, "current-token")
    repository = MemoryIdentityRepository(
        users={user.id: user},
        sessions={session.id: session},
        email_change_tokens={token.token_digest: token},
    )

    create_service(repository).confirm_email_change("raw-token")

    assert user.email == "new@example.com"
    assert token.consumed_at == NOW
    assert repository.sessions == {}


def test_confirm_email_change_rejects_unknown_token() -> None:
    repository = MemoryIdentityRepository()

    with pytest.raises(EmailChangeError) as error:
        create_service(repository).confirm_email_change("raw-token")

    assert error.value.reason is EmailChangeFailure.INVALID


def test_confirm_email_change_rejects_expired_token() -> None:
    user = active_user()
    token = _pending_token(user)
    token.expires_at = NOW - timedelta(minutes=1)
    repository = MemoryIdentityRepository(
        users={user.id: user},
        email_change_tokens={token.token_digest: token},
    )

    with pytest.raises(EmailChangeError) as error:
        create_service(repository).confirm_email_change("raw-token")

    assert error.value.reason is EmailChangeFailure.EXPIRED


def test_confirm_email_change_rejects_used_token() -> None:
    user = active_user()
    token = _pending_token(user)
    token.consumed_at = NOW - timedelta(minutes=1)
    repository = MemoryIdentityRepository(
        users={user.id: user},
        email_change_tokens={token.token_digest: token},
    )

    with pytest.raises(EmailChangeError) as error:
        create_service(repository).confirm_email_change("raw-token")

    assert error.value.reason is EmailChangeFailure.USED


def test_confirm_email_change_rejects_email_taken_since_request() -> None:
    user = active_user()
    other = active_user(email="new@example.com")
    token = _pending_token(user)
    repository = MemoryIdentityRepository(
        users={user.id: user, other.id: other},
        email_change_tokens={token.token_digest: token},
    )

    with pytest.raises(EmailChangeError):
        create_service(repository).confirm_email_change("raw-token")

    assert user.email == "researcher@example.com"


# --- sessions ----------------------------------------------------------


def test_list_sessions_marks_current_and_hides_expired() -> None:
    user = active_user()
    current = session_for(user, "current-token", created_offset=timedelta(minutes=10))
    older = session_for(user, "old-token", created_offset=timedelta(days=1))
    expired = session_for(user, "dead-token")
    expired.expires_at = NOW - timedelta(hours=1)
    repository = MemoryIdentityRepository(
        users={user.id: user},
        sessions={s.id: s for s in (current, older, expired)},
    )

    views = create_service(repository).list_sessions(user.id, "current-token")

    assert [v.id for v in views] == [current.id, older.id]
    assert [v.is_current for v in views] == [True, False]
    assert views[0].user_agent == "Firefox"


def test_revoke_session_deletes_own_session() -> None:
    user = active_user()
    target = session_for(user, "target-token")
    repository = MemoryIdentityRepository(
        users={user.id: user}, sessions={target.id: target}
    )

    create_service(repository).revoke_session(user.id, target.id)

    assert repository.sessions == {}


def test_revoke_session_rejects_other_users_session() -> None:
    user = active_user()
    other = active_user(email="other@example.com")
    foreign = session_for(other, "foreign-token")
    repository = MemoryIdentityRepository(
        users={user.id: user, other.id: other},
        sessions={foreign.id: foreign},
    )

    with pytest.raises(SessionNotFoundError):
        create_service(repository).revoke_session(user.id, foreign.id)

    assert foreign.id in repository.sessions


def test_revoke_other_sessions_keeps_current_and_reports_count() -> None:
    user = active_user()
    current = session_for(user, "current-token")
    other_a = session_for(user, "a-token")
    other_b = session_for(user, "b-token")
    repository = MemoryIdentityRepository(
        users={user.id: user},
        sessions={s.id: s for s in (current, other_a, other_b)},
    )

    revoked = create_service(repository).revoke_other_sessions(user.id, "current-token")

    assert revoked == 2
    assert set(repository.sessions) == {current.id}
