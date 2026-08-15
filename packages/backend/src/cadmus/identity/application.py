"""Identity application use cases."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from urllib.parse import urlencode
from uuid import uuid4

from cadmus.identity.domain import (
    AccountStatus,
    AuthenticatedSession,
    PasswordResetToken,
    User,
    VerificationToken,
)
from cadmus.identity.ports import (
    EmailSender,
    IdentityUnitOfWorkFactory,
    PasswordHasher,
    PasswordResetTokenProvider,
    SessionTokenProvider,
    VerificationTokenProvider,
)

MINIMUM_PASSWORD_LENGTH = 12
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)


class RegistrationValidationError(ValueError):
    """Field-addressable registration input errors."""

    def __init__(self, errors: Mapping[str, str]) -> None:
        super().__init__("registration data is invalid")
        self.errors = dict(errors)


class DuplicateEmailError(ValueError):
    """Raised when normalized email uniqueness would be violated."""


class ActivationFailure(StrEnum):
    """Safe public reasons why account activation failed."""

    INVALID = "invalid"
    EXPIRED = "expired"
    USED = "used"


class ActivationError(ValueError):
    """A controlled verification-token failure."""

    def __init__(self, reason: ActivationFailure) -> None:
        super().__init__(reason.value)
        self.reason = reason


class PasswordResetValidationError(ValueError):
    """Field-addressable password reset input errors."""

    def __init__(self, errors: Mapping[str, str]) -> None:
        super().__init__("password reset data is invalid")
        self.errors = dict(errors)


class PasswordResetFailure(StrEnum):
    """Safe public reasons why a password reset failed."""

    INVALID = "invalid"
    EXPIRED = "expired"
    USED = "used"


class PasswordResetError(ValueError):
    """A controlled password-reset-token failure."""

    def __init__(self, reason: PasswordResetFailure) -> None:
        super().__init__(reason.value)
        self.reason = reason


class AuthenticationFailure(StrEnum):
    """Safe public reasons why login or session authentication failed."""

    INVALID_CREDENTIALS = "invalid_credentials"
    UNVERIFIED_ACCOUNT = "unverified_account"
    INVALID_SESSION = "invalid_session"


class AuthenticationError(ValueError):
    """A controlled login or session failure."""

    def __init__(self, reason: AuthenticationFailure) -> None:
        super().__init__(reason.value)
        self.reason = reason


@dataclass(frozen=True)
class LoginResult:
    """Authenticated user plus the raw token delivered only to HTTP transport."""

    user: User
    session_token: str


class AuthenticationService:
    """Authenticate credentials and resolve server-side sessions."""

    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        password_hasher: PasswordHasher,
        session_token_provider: SessionTokenProvider,
        session_lifetime: timedelta = timedelta(hours=12),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_hasher = password_hasher
        self._session_token_provider = session_token_provider
        self._session_lifetime = session_lifetime
        self._clock = clock

    def login(self, email: str, password: str) -> LoginResult:
        """Create a session only for valid credentials on an active account."""
        normalized_email = email.strip().casefold()
        now = self._clock()

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.users.get_user_by_email(normalized_email)
            password_matches = self._password_hasher.verify(
                password,
                user.password_hash if user is not None else None,
            )
            if user is None or not password_matches:
                raise AuthenticationError(AuthenticationFailure.INVALID_CREDENTIALS)
            if user.status is not AccountStatus.ACTIVE:
                raise AuthenticationError(AuthenticationFailure.UNVERIFIED_ACCOUNT)

            raw_token, token_digest = self._session_token_provider.issue()
            session = AuthenticatedSession(
                id=uuid4(),
                user_id=user.id,
                token_digest=token_digest,
                created_at=now,
                expires_at=now + self._session_lifetime,
            )
            unit_of_work.users.add_session(session)
            unit_of_work.commit()

        return LoginResult(user=user, session_token=raw_token)

    def authenticate(self, raw_token: str) -> User:
        """Resolve an unexpired session token to its active account."""
        token_digest = self._session_token_provider.digest(raw_token)
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            session = unit_of_work.users.get_session(token_digest)
            if session is None or session.expires_at <= now:
                raise AuthenticationError(AuthenticationFailure.INVALID_SESSION)
            user = unit_of_work.users.get_user(session.user_id)
            if user is None or user.status is not AccountStatus.ACTIVE:
                raise AuthenticationError(AuthenticationFailure.INVALID_SESSION)
        return user

    def logout(self, raw_token: str) -> None:
        """Invalidate the current session without revealing whether it existed."""
        token_digest = self._session_token_provider.digest(raw_token)
        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.users.delete_session(token_digest)
            unit_of_work.commit()


class RegistrationService:
    """Coordinates registration and activation through explicit ports."""

    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        password_hasher: PasswordHasher,
        token_provider: VerificationTokenProvider,
        email_sender: EmailSender,
        public_web_url: str,
        token_lifetime: timedelta = timedelta(hours=24),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_hasher = password_hasher
        self._token_provider = token_provider
        self._email_sender = email_sender
        self._public_web_url = public_web_url.rstrip("/")
        self._token_lifetime = token_lifetime
        self._clock = clock

    def register(
        self,
        email: str,
        password: str,
        password_confirmation: str,
    ) -> User:
        """Create a pending account and deliver its one-time verification link."""
        normalized_email = email.strip().casefold()
        errors = _validate_registration(
            normalized_email,
            password,
            password_confirmation,
        )
        if errors:
            raise RegistrationValidationError(errors)

        now = self._clock()
        user = User(
            id=uuid4(),
            email=normalized_email,
            password_hash=self._password_hasher.hash(password),
            status=AccountStatus.PENDING_VERIFICATION,
            created_at=now,
        )
        raw_token, token_digest = self._token_provider.issue()
        verification_token = VerificationToken(
            id=uuid4(),
            user_id=user.id,
            token_digest=token_digest,
            created_at=now,
            expires_at=now + self._token_lifetime,
        )
        # A URL fragment is intentionally used so web-server access logs never
        # receive the credential. The browser passes it to the API in a POST body.
        verification_url = (
            f"{self._public_web_url}/verify-email#{urlencode({'token': raw_token})}"
        )

        with self._unit_of_work_factory() as unit_of_work:
            if unit_of_work.users.get_user_by_email(normalized_email) is not None:
                raise DuplicateEmailError
            unit_of_work.users.add_user(user)
            unit_of_work.users.add_verification_token(verification_token)
            self._email_sender.send_verification(normalized_email, verification_url)
            unit_of_work.commit()

        return user

    def activate(self, raw_token: str) -> User:
        """Consume a valid verification token and activate its account."""
        token_digest = self._token_provider.digest(raw_token)
        now = self._clock()

        with self._unit_of_work_factory() as unit_of_work:
            token = unit_of_work.users.get_verification_token(token_digest)
            if token is None:
                raise ActivationError(ActivationFailure.INVALID)
            if token.consumed_at is not None:
                raise ActivationError(ActivationFailure.USED)
            if token.expires_at <= now:
                raise ActivationError(ActivationFailure.EXPIRED)
            user = unit_of_work.users.get_user(token.user_id)
            if user is None:
                raise ActivationError(ActivationFailure.INVALID)
            user.activate(now)
            token.consume(now)
            unit_of_work.commit()

        return user


class PasswordResetService:
    """Coordinates password-reset requests and confirmations through explicit ports."""

    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        password_hasher: PasswordHasher,
        token_provider: PasswordResetTokenProvider,
        email_sender: EmailSender,
        public_web_url: str,
        token_lifetime: timedelta = timedelta(hours=1),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_hasher = password_hasher
        self._token_provider = token_provider
        self._email_sender = email_sender
        self._public_web_url = public_web_url.rstrip("/")
        self._token_lifetime = token_lifetime
        self._clock = clock

    def request_reset(self, email: str) -> None:
        """Deliver a one-time reset link only for an existing active account.

        Silently returns for a missing or non-active account so the caller's
        response never discloses whether the email is registered.
        """
        normalized_email = email.strip().casefold()
        now = self._clock()

        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.users.get_user_by_email(normalized_email)
            if user is None or user.status is not AccountStatus.ACTIVE:
                return

            raw_token, token_digest = self._token_provider.issue()
            reset_token = PasswordResetToken(
                id=uuid4(),
                user_id=user.id,
                token_digest=token_digest,
                created_at=now,
                expires_at=now + self._token_lifetime,
            )
            # A URL fragment is intentionally used so web-server access logs never
            # receive the credential. The browser passes it to the API in a POST body.
            reset_query = urlencode({"token": raw_token})
            reset_url = f"{self._public_web_url}/reset-password#{reset_query}"
            unit_of_work.users.add_password_reset_token(reset_token)
            self._email_sender.send_password_reset(normalized_email, reset_url)
            unit_of_work.commit()

    def reset_password(
        self,
        raw_token: str,
        new_password: str,
        new_password_confirmation: str,
    ) -> None:
        """Consume a valid reset token, set the new password, and end all sessions."""
        errors = _validate_new_password(new_password, new_password_confirmation)
        if errors:
            raise PasswordResetValidationError(errors)

        token_digest = self._token_provider.digest(raw_token)
        now = self._clock()

        with self._unit_of_work_factory() as unit_of_work:
            token = unit_of_work.users.get_password_reset_token(token_digest)
            if token is None:
                raise PasswordResetError(PasswordResetFailure.INVALID)
            if token.consumed_at is not None:
                raise PasswordResetError(PasswordResetFailure.USED)
            if token.expires_at <= now:
                raise PasswordResetError(PasswordResetFailure.EXPIRED)
            user = unit_of_work.users.get_user(token.user_id)
            if user is None:
                raise PasswordResetError(PasswordResetFailure.INVALID)

            user.password_hash = self._password_hasher.hash(new_password)
            token.consume(now)
            unit_of_work.users.delete_sessions_for_user(user.id)
            unit_of_work.commit()


def _validate_new_password(password: str, password_confirmation: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        errors["password"] = (
            f"Пароль має містити щонайменше {MINIMUM_PASSWORD_LENGTH} символів."
        )
    if password_confirmation != password:
        errors["password_confirmation"] = "Паролі не збігаються."
    return errors


def _validate_registration(
    email: str,
    password: str,
    password_confirmation: str,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    local_part = email.partition("@")[0]
    if (
        len(email) > 254
        or EMAIL_PATTERN.fullmatch(email) is None
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
    ):
        errors["email"] = "Введіть коректну email-адресу."
    errors.update(_validate_new_password(password, password_confirmation))
    return errors
