from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.identity import (
    AccountStatus,
    AuthenticatedSession,
    AuthenticationService,
    EmailChangeToken,
    GoogleAuthenticationError,
    GoogleAuthenticationService,
    GoogleAuthFailure,
    GoogleIdentity,
    GoogleIdentityClaims,
    GoogleOAuthError,
    PasswordResetToken,
    User,
    VerificationToken,
)

NOW = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)


@dataclass
class MemoryIdentityRepository:
    users: dict[UUID, User] = field(default_factory=dict)
    sessions: dict[str, AuthenticatedSession] = field(default_factory=dict)
    google_identities: dict[str, GoogleIdentity] = field(default_factory=dict)

    def get_user_by_email(self, email: str) -> User | None:
        return next((user for user in self.users.values() if user.email == email), None)

    def get_user(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    def get_verification_token(self, token_digest: str) -> VerificationToken | None:
        return None

    def get_password_reset_token(self, token_digest: str) -> PasswordResetToken | None:
        return None

    def get_session(self, token_digest: str) -> AuthenticatedSession | None:
        return self.sessions.get(token_digest)

    def get_google_identity_by_subject(self, subject: str) -> GoogleIdentity | None:
        return self.google_identities.get(subject)

    def add_user(self, user: User) -> None:
        self.users[user.id] = user

    def add_verification_token(self, token: VerificationToken) -> None:
        raise AssertionError("not used by google oauth")

    def add_password_reset_token(self, token: PasswordResetToken) -> None:
        raise AssertionError("not used by google oauth")

    def add_session(self, session: AuthenticatedSession) -> None:
        self.sessions[session.token_digest] = session

    def add_google_identity(self, identity: GoogleIdentity) -> None:
        self.google_identities[identity.subject] = identity

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
        raise AssertionError("not used by google oauth")

    def get_sessions_for_user(self, user_id: UUID) -> list[AuthenticatedSession]:
        raise AssertionError("not used by google oauth")

    def get_email_change_token(self, token_digest: str) -> EmailChangeToken | None:
        return None

    def add_email_change_token(self, token: EmailChangeToken) -> None:
        raise AssertionError("not used by google oauth")

    def delete_session_by_id(self, session_id: UUID) -> None:
        raise AssertionError("not used by google oauth")

    def delete_other_sessions_for_user(
        self, user_id: UUID, keep_token_digest: str
    ) -> None:
        raise AssertionError("not used by google oauth")


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


class StubSessionTokenProvider:
    def issue(self) -> tuple[str, str]:
        return "raw-session-token", self.digest("raw-session-token")

    def digest(self, token: str) -> str:
        return sha256(token.encode()).hexdigest()


@dataclass
class StubGoogleOAuthClient:
    claims: GoogleIdentityClaims | None = None
    error: Exception | None = None
    authorization_url: str = "https://accounts.google.com/o/oauth2/v2/auth?mock=1"
    received_code_verifier: str | None = None
    received_nonce: str | None = None

    def build_authorization_url(
        self, state: str, nonce: str, code_challenge: str
    ) -> str:
        return self.authorization_url

    def exchange_code(
        self, code: str, code_verifier: str, expected_nonce: str
    ) -> GoogleIdentityClaims:
        self.received_code_verifier = code_verifier
        self.received_nonce = expected_nonce
        if self.error is not None:
            raise self.error
        assert self.claims is not None
        return self.claims


def active_user(email: str = "researcher@example.com") -> User:
    return User(
        id=uuid4(),
        email=email,
        password_hash="hashed:correct-password",
        status=AccountStatus.ACTIVE,
        created_at=NOW - timedelta(days=1),
        activated_at=NOW - timedelta(hours=12),
    )


def create_google_service(
    repository: MemoryIdentityRepository,
    google_client: StubGoogleOAuthClient,
) -> GoogleAuthenticationService:
    authentication_service = AuthenticationService(
        unit_of_work_factory=lambda: MemoryUnitOfWork(repository),
        password_hasher=StubPasswordHasher(),
        session_token_provider=StubSessionTokenProvider(),
        session_lifetime=timedelta(hours=8),
        clock=lambda: NOW,
    )
    return GoogleAuthenticationService(
        unit_of_work_factory=lambda: MemoryUnitOfWork(repository),
        google_oauth_client=google_client,
        authentication_service=authentication_service,
        clock=lambda: NOW,
    )


def test_start_login_builds_a_fresh_state_nonce_and_pkce_pair() -> None:
    service = create_google_service(MemoryIdentityRepository(), StubGoogleOAuthClient())

    first = service.start_login()
    second = service.start_login()

    assert (
        first.authorization_url == "https://accounts.google.com/o/oauth2/v2/auth?mock=1"
    )
    assert first.state != second.state
    assert first.nonce != second.nonce
    assert first.code_verifier != second.code_verifier
    assert 43 <= len(first.code_verifier) <= 128


def test_complete_login_creates_a_new_active_user_without_a_password() -> None:
    google_client = StubGoogleOAuthClient(
        claims=GoogleIdentityClaims(
            subject="google-subject-1",
            email="New.User@Example.com",
            email_verified=True,
        )
    )
    repository = MemoryIdentityRepository()
    service = create_google_service(repository, google_client)

    result = service.complete_login(
        code="auth-code",
        state="state-1",
        expected_state="state-1",
        expected_nonce="nonce-1",
        code_verifier="verifier-1",
    )

    assert result.session_token == "raw-session-token"
    user = result.user
    assert user.email == "new.user@example.com"
    assert user.password_hash is None
    assert user.status is AccountStatus.ACTIVE
    assert repository.google_identities["google-subject-1"].user_id == user.id
    assert google_client.received_code_verifier == "verifier-1"
    assert google_client.received_nonce == "nonce-1"


def test_complete_login_repeat_sign_in_reuses_the_linked_user() -> None:
    user = active_user()
    identity = GoogleIdentity(
        id=uuid4(),
        user_id=user.id,
        subject="google-subject-2",
        email=user.email,
        created_at=NOW - timedelta(days=10),
    )
    repository = MemoryIdentityRepository(
        users={user.id: user}, google_identities={identity.subject: identity}
    )
    google_client = StubGoogleOAuthClient(
        claims=GoogleIdentityClaims(
            subject="google-subject-2", email=user.email, email_verified=True
        )
    )
    service = create_google_service(repository, google_client)

    result = service.complete_login(
        code="auth-code",
        state="state-1",
        expected_state="state-1",
        expected_nonce="nonce-1",
        code_verifier="verifier-1",
    )

    assert result.user is user
    assert len(repository.google_identities) == 1


def test_complete_login_links_an_existing_password_account_without_duplicating_it() -> (
    None
):
    user = active_user()
    repository = MemoryIdentityRepository(users={user.id: user})
    google_client = StubGoogleOAuthClient(
        claims=GoogleIdentityClaims(
            subject="google-subject-3", email=user.email, email_verified=True
        )
    )
    service = create_google_service(repository, google_client)

    result = service.complete_login(
        code="auth-code",
        state="state-1",
        expected_state="state-1",
        expected_nonce="nonce-1",
        code_verifier="verifier-1",
    )

    assert result.user is user
    assert len(repository.users) == 1
    assert repository.google_identities["google-subject-3"].user_id == user.id


def test_complete_login_rejects_an_unverified_google_email() -> None:
    repository = MemoryIdentityRepository()
    google_client = StubGoogleOAuthClient(
        claims=GoogleIdentityClaims(
            subject="google-subject-4",
            email="unverified@example.com",
            email_verified=False,
        )
    )
    service = create_google_service(repository, google_client)

    with pytest.raises(GoogleAuthenticationError) as error:
        service.complete_login(
            code="auth-code",
            state="state-1",
            expected_state="state-1",
            expected_nonce="nonce-1",
            code_verifier="verifier-1",
        )

    assert error.value.reason is GoogleAuthFailure.EMAIL_NOT_VERIFIED
    assert repository.users == {}


def test_complete_login_rejects_a_mismatched_state_without_calling_google() -> None:
    google_client = StubGoogleOAuthClient(
        claims=GoogleIdentityClaims(
            subject="google-subject-5", email="user@example.com", email_verified=True
        )
    )
    service = create_google_service(MemoryIdentityRepository(), google_client)

    with pytest.raises(GoogleAuthenticationError) as error:
        service.complete_login(
            code="auth-code",
            state="attacker-state",
            expected_state="state-1",
            expected_nonce="nonce-1",
            code_verifier="verifier-1",
        )

    assert error.value.reason is GoogleAuthFailure.INVALID_STATE
    assert google_client.received_code_verifier is None


def test_complete_login_wraps_a_token_exchange_failure() -> None:
    google_client = StubGoogleOAuthClient(error=GoogleOAuthError("boom"))
    service = create_google_service(MemoryIdentityRepository(), google_client)

    with pytest.raises(GoogleAuthenticationError) as error:
        service.complete_login(
            code="auth-code",
            state="state-1",
            expected_state="state-1",
            expected_nonce="nonce-1",
            code_verifier="verifier-1",
        )

    assert error.value.reason is GoogleAuthFailure.TOKEN_EXCHANGE_FAILED


def test_complete_login_rejects_a_pending_account_resolved_by_email() -> None:
    user = active_user()
    user.status = AccountStatus.PENDING_VERIFICATION
    user.activated_at = None
    repository = MemoryIdentityRepository(users={user.id: user})
    google_client = StubGoogleOAuthClient(
        claims=GoogleIdentityClaims(
            subject="google-subject-6", email=user.email, email_verified=True
        )
    )
    service = create_google_service(repository, google_client)

    with pytest.raises(GoogleAuthenticationError) as error:
        service.complete_login(
            code="auth-code",
            state="state-1",
            expected_state="state-1",
            expected_nonce="nonce-1",
            code_verifier="verifier-1",
        )

    assert error.value.reason is GoogleAuthFailure.ACCOUNT_INACTIVE
    assert repository.google_identities == {}
