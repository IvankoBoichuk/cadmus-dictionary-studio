"""Identity domain and registration use cases."""

from cadmus.identity.application import (
    ActivationError,
    ActivationFailure,
    AuthenticationError,
    AuthenticationFailure,
    AuthenticationService,
    DuplicateEmailError,
    LoginResult,
    RegistrationService,
    RegistrationValidationError,
)
from cadmus.identity.domain import (
    AccountStatus,
    AuthenticatedSession,
    User,
    VerificationToken,
)
from cadmus.identity.ports import (
    EmailSender,
    IdentityRepository,
    IdentityUnitOfWork,
    IdentityUnitOfWorkFactory,
    PasswordHasher,
    SessionTokenProvider,
    VerificationTokenProvider,
)

__all__ = [
    "AccountStatus",
    "ActivationError",
    "ActivationFailure",
    "AuthenticatedSession",
    "AuthenticationError",
    "AuthenticationFailure",
    "AuthenticationService",
    "DuplicateEmailError",
    "EmailSender",
    "IdentityRepository",
    "IdentityUnitOfWork",
    "IdentityUnitOfWorkFactory",
    "LoginResult",
    "PasswordHasher",
    "RegistrationService",
    "RegistrationValidationError",
    "SessionTokenProvider",
    "User",
    "VerificationToken",
    "VerificationTokenProvider",
]
