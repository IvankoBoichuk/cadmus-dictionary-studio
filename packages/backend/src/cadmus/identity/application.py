"""Registration and email verification application use cases."""

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from urllib.parse import urlencode
from uuid import uuid4

from cadmus.identity.domain import AccountStatus, User, VerificationToken
from cadmus.identity.ports import (
    EmailSender,
    IdentityUnitOfWorkFactory,
    PasswordHasher,
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
    if len(password) < MINIMUM_PASSWORD_LENGTH:
        errors["password"] = (
            f"Пароль має містити щонайменше {MINIMUM_PASSWORD_LENGTH} символів."
        )
    if password_confirmation != password:
        errors["password_confirmation"] = "Паролі не збігаються."
    return errors
