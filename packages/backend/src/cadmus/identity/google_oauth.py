"""Google OAuth 2.0 / OIDC login use case."""

import base64
import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from cadmus.identity.application import (
    AuthenticationService,
    DuplicateEmailError,
    LoginResult,
)
from cadmus.identity.domain import AccountStatus, GoogleIdentity, User
from cadmus.identity.ports import (
    GoogleOAuthClient,
    GoogleOAuthError,
    IdentityUnitOfWorkFactory,
)


class GoogleAuthFailure(StrEnum):
    """Safe public reasons why a Google login failed."""

    INVALID_STATE = "invalid_state"
    PROVIDER_ERROR = "provider_error"
    TOKEN_EXCHANGE_FAILED = "token_exchange_failed"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    ACCOUNT_INACTIVE = "account_inactive"
    EMAIL_ALREADY_REGISTERED = "email_already_registered"


class GoogleAuthenticationError(ValueError):
    """A controlled Google login failure."""

    def __init__(self, reason: GoogleAuthFailure) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class GoogleLoginChallenge:
    """The Google authorization URL plus the values needed to verify its callback."""

    authorization_url: str
    state: str
    nonce: str
    code_verifier: str


def _generate_code_verifier() -> str:
    return secrets.token_urlsafe(64)[:128]


def _code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class GoogleAuthenticationService:
    """Coordinates Google sign-in through an explicit OAuth client port."""

    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        google_oauth_client: GoogleOAuthClient,
        authentication_service: AuthenticationService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._google_oauth_client = google_oauth_client
        self._authentication_service = authentication_service
        self._clock = clock

    def start_login(self) -> GoogleLoginChallenge:
        """Build a fresh authorization challenge for a login attempt."""
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        code_verifier = _generate_code_verifier()
        authorization_url = self._google_oauth_client.build_authorization_url(
            state=state,
            nonce=nonce,
            code_challenge=_code_challenge(code_verifier),
        )
        return GoogleLoginChallenge(
            authorization_url=authorization_url,
            state=state,
            nonce=nonce,
            code_verifier=code_verifier,
        )

    def complete_login(
        self,
        *,
        code: str,
        state: str,
        expected_state: str,
        expected_nonce: str,
        code_verifier: str,
    ) -> LoginResult:
        """Verify a Google callback and resolve it to an authenticated session."""
        if not secrets.compare_digest(state, expected_state):
            raise GoogleAuthenticationError(GoogleAuthFailure.INVALID_STATE)

        try:
            claims = self._google_oauth_client.exchange_code(
                code, code_verifier, expected_nonce
            )
        except GoogleOAuthError as error:
            raise GoogleAuthenticationError(
                GoogleAuthFailure.TOKEN_EXCHANGE_FAILED
            ) from error

        if not claims.email_verified:
            raise GoogleAuthenticationError(GoogleAuthFailure.EMAIL_NOT_VERIFIED)

        normalized_email = claims.email.strip().casefold()
        now = self._clock()

        with self._unit_of_work_factory() as unit_of_work:
            identity = unit_of_work.users.get_google_identity_by_subject(claims.subject)
            if identity is not None:
                user = unit_of_work.users.get_user(identity.user_id)
                if user is None or user.status is not AccountStatus.ACTIVE:
                    raise GoogleAuthenticationError(GoogleAuthFailure.ACCOUNT_INACTIVE)
            else:
                user = unit_of_work.users.get_user_by_email(normalized_email)
                if user is not None and user.status is not AccountStatus.ACTIVE:
                    raise GoogleAuthenticationError(GoogleAuthFailure.ACCOUNT_INACTIVE)
                if user is None:
                    user = User(
                        id=uuid4(),
                        email=normalized_email,
                        password_hash=None,
                        status=AccountStatus.ACTIVE,
                        created_at=now,
                        activated_at=now,
                    )
                    try:
                        unit_of_work.users.add_user(user)
                    except DuplicateEmailError as error:
                        raise GoogleAuthenticationError(
                            GoogleAuthFailure.EMAIL_ALREADY_REGISTERED
                        ) from error
                unit_of_work.users.add_google_identity(
                    GoogleIdentity(
                        id=uuid4(),
                        user_id=user.id,
                        subject=claims.subject,
                        email=normalized_email,
                        created_at=now,
                    )
                )
            unit_of_work.commit()

        return self._authentication_service.issue_session(user)
