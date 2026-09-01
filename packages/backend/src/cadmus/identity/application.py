"""Identity application use cases."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from urllib.parse import urlencode
from uuid import UUID, uuid4

from cadmus.identity.domain import (
    AccountStatus,
    AuthenticatedSession,
    EmailChangeToken,
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
MAXIMUM_NAME_LENGTH = 200
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

    def login(
        self, email: str, password: str, user_agent: str | None = None
    ) -> LoginResult:
        """Create a session only for valid credentials on an active account."""
        normalized_email = email.strip().casefold()

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

        return self.issue_session(user, user_agent=user_agent)

    def issue_session(self, user: User, user_agent: str | None = None) -> LoginResult:
        """Create a new server-side session for an already-authenticated user."""
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            raw_token, token_digest = self._session_token_provider.issue()
            session = AuthenticatedSession(
                id=uuid4(),
                user_id=user.id,
                token_digest=token_digest,
                created_at=now,
                expires_at=now + self._session_lifetime,
                user_agent=(user_agent or None),
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


class ProfileValidationError(ValueError):
    """Field-addressable profile input errors."""

    def __init__(self, errors: Mapping[str, str]) -> None:
        super().__init__("profile data is invalid")
        self.errors = dict(errors)


class EmailChangeValidationError(ValueError):
    """Field-addressable email-change request errors."""

    def __init__(self, errors: Mapping[str, str]) -> None:
        super().__init__("email change data is invalid")
        self.errors = dict(errors)


class EmailChangeFailure(StrEnum):
    """Safe public reasons why confirming an email change failed."""

    INVALID = "invalid"
    EXPIRED = "expired"
    USED = "used"


class EmailChangeError(ValueError):
    """A controlled email-change-token failure."""

    def __init__(self, reason: EmailChangeFailure) -> None:
        super().__init__(reason.value)
        self.reason = reason


class SessionNotFoundError(LookupError):
    """Raised when a session to revoke is missing or owned by another user."""


@dataclass(frozen=True)
class SessionView:
    """A user-facing summary of one active server-side session."""

    id: UUID
    created_at: datetime
    expires_at: datetime
    user_agent: str | None
    is_current: bool


class AccountService:
    """Self-service profile, credential, and session management for a signed-in user."""

    def __init__(
        self,
        unit_of_work_factory: IdentityUnitOfWorkFactory,
        password_hasher: PasswordHasher,
        session_token_provider: SessionTokenProvider,
        email_change_token_provider: VerificationTokenProvider,
        email_sender: EmailSender,
        public_web_url: str,
        token_lifetime: timedelta = timedelta(hours=24),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._password_hasher = password_hasher
        self._session_token_provider = session_token_provider
        self._email_change_token_provider = email_change_token_provider
        self._email_sender = email_sender
        self._public_web_url = public_web_url.rstrip("/")
        self._token_lifetime = token_lifetime
        self._clock = clock

    def update_profile(self, user_id: UUID, name: str | None) -> User:
        """Set or clear the user's display name."""
        cleaned = (name or "").strip()
        if len(cleaned) > MAXIMUM_NAME_LENGTH:
            raise ProfileValidationError(
                {
                    "name": (
                        f"Ім'я не може бути довшим за {MAXIMUM_NAME_LENGTH} символів."
                    )
                }
            )
        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.users.get_user(user_id)
            if user is None:
                raise AuthenticationError(AuthenticationFailure.INVALID_SESSION)
            user.name = cleaned or None
            unit_of_work.commit()
        return user

    def change_password(
        self,
        user_id: UUID,
        current_raw_token: str,
        current_password: str,
        new_password: str,
        new_password_confirmation: str,
    ) -> None:
        """Verify the current password, set a new one, drop every other session."""
        errors = _validate_new_password(new_password, new_password_confirmation)
        if errors:
            raise PasswordResetValidationError(errors)

        keep_digest = self._session_token_provider.digest(current_raw_token)
        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.users.get_user(user_id)
            if user is None:
                raise AuthenticationError(AuthenticationFailure.INVALID_SESSION)
            if not self._password_hasher.verify(current_password, user.password_hash):
                raise AuthenticationError(AuthenticationFailure.INVALID_CREDENTIALS)
            user.password_hash = self._password_hasher.hash(new_password)
            unit_of_work.users.delete_other_sessions_for_user(user_id, keep_digest)
            unit_of_work.commit()

    def request_email_change(
        self, user_id: UUID, new_email: str, current_password: str
    ) -> None:
        """Verify the password and mail a one-time confirmation link to `new_email`."""
        normalized_email = new_email.strip().casefold()
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            user = unit_of_work.users.get_user(user_id)
            if user is None:
                raise AuthenticationError(AuthenticationFailure.INVALID_SESSION)
            if not self._password_hasher.verify(current_password, user.password_hash):
                raise AuthenticationError(AuthenticationFailure.INVALID_CREDENTIALS)
            if not _email_is_valid(normalized_email):
                raise EmailChangeValidationError(
                    {"new_email": "Введіть коректну email-адресу."}
                )
            if normalized_email == user.email:
                raise EmailChangeValidationError(
                    {"new_email": "Це вже ваша поточна адреса."}
                )
            if unit_of_work.users.get_user_by_email(normalized_email) is not None:
                raise EmailChangeValidationError(
                    {"new_email": "Ця email-адреса вже зареєстрована."}
                )
            raw_token, token_digest = self._email_change_token_provider.issue()
            token = EmailChangeToken(
                id=uuid4(),
                user_id=user.id,
                new_email=normalized_email,
                token_digest=token_digest,
                created_at=now,
                expires_at=now + self._token_lifetime,
            )
            # A URL fragment keeps the credential out of web-server access logs; the
            # browser forwards it to the API in a POST body.
            confirm_query = urlencode({"token": raw_token})
            confirm_url = f"{self._public_web_url}/confirm-email-change#{confirm_query}"
            unit_of_work.users.add_email_change_token(token)
            self._email_sender.send_email_change(normalized_email, confirm_url)
            unit_of_work.commit()

    def confirm_email_change(self, raw_token: str) -> None:
        """Consume a valid token, move the account to its new email, end sessions."""
        token_digest = self._email_change_token_provider.digest(raw_token)
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            token = unit_of_work.users.get_email_change_token(token_digest)
            if token is None:
                raise EmailChangeError(EmailChangeFailure.INVALID)
            if token.consumed_at is not None:
                raise EmailChangeError(EmailChangeFailure.USED)
            if token.expires_at <= now:
                raise EmailChangeError(EmailChangeFailure.EXPIRED)
            user = unit_of_work.users.get_user(token.user_id)
            if user is None:
                raise EmailChangeError(EmailChangeFailure.INVALID)
            existing = unit_of_work.users.get_user_by_email(token.new_email)
            if existing is not None and existing.id != user.id:
                raise EmailChangeError(EmailChangeFailure.INVALID)
            user.email = token.new_email
            token.consume(now)
            unit_of_work.users.delete_sessions_for_user(user.id)
            unit_of_work.commit()

    def list_sessions(self, user_id: UUID, current_raw_token: str) -> list[SessionView]:
        """Return the user's unexpired sessions, newest first."""
        current_digest = self._session_token_provider.digest(current_raw_token)
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            sessions = unit_of_work.users.get_sessions_for_user(user_id)
        return [
            SessionView(
                id=session.id,
                created_at=session.created_at,
                expires_at=session.expires_at,
                user_agent=session.user_agent,
                is_current=session.token_digest == current_digest,
            )
            for session in sorted(
                (s for s in sessions if s.expires_at > now),
                key=lambda s: s.created_at,
                reverse=True,
            )
        ]

    def revoke_session(self, user_id: UUID, session_id: UUID) -> None:
        """Delete one of the user's own sessions."""
        with self._unit_of_work_factory() as unit_of_work:
            session = unit_of_work.users.get_session_by_id(session_id)
            if session is None or session.user_id != user_id:
                raise SessionNotFoundError
            unit_of_work.users.delete_session_by_id(session_id)
            unit_of_work.commit()

    def revoke_other_sessions(self, user_id: UUID, current_raw_token: str) -> int:
        """Delete every session for the user except the caller's own."""
        current_digest = self._session_token_provider.digest(current_raw_token)
        now = self._clock()
        with self._unit_of_work_factory() as unit_of_work:
            sessions = unit_of_work.users.get_sessions_for_user(user_id)
            revoked = sum(
                1
                for s in sessions
                if s.token_digest != current_digest and s.expires_at > now
            )
            unit_of_work.users.delete_other_sessions_for_user(user_id, current_digest)
            unit_of_work.commit()
        return revoked


def _validate_new_password(password: str, password_confirmation: str) -> dict[str, str]:
    errors: dict[str, str] = {}
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        errors["password"] = (
            f"Пароль має містити щонайменше {MINIMUM_PASSWORD_LENGTH} символів."
        )
    if password_confirmation != password:
        errors["password_confirmation"] = "Паролі не збігаються."
    return errors


def _email_is_valid(email: str) -> bool:
    local_part = email.partition("@")[0]
    return not (
        len(email) > 254
        or EMAIL_PATTERN.fullmatch(email) is None
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
    )


def _validate_registration(
    email: str,
    password: str,
    password_confirmation: str,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not _email_is_valid(email):
        errors["email"] = "Введіть коректну email-адресу."
    errors.update(_validate_new_password(password, password_confirmation))
    return errors
