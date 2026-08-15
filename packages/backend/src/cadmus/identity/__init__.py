"""Identity domain and registration use cases."""

from cadmus.identity.application import (
    ActivationError,
    ActivationFailure,
    DuplicateEmailError,
    RegistrationService,
    RegistrationValidationError,
)
from cadmus.identity.domain import AccountStatus, User, VerificationToken
from cadmus.identity.ports import (
    EmailSender,
    IdentityRepository,
    IdentityUnitOfWork,
    IdentityUnitOfWorkFactory,
    PasswordHasher,
    VerificationTokenProvider,
)

__all__ = [
    "AccountStatus",
    "ActivationError",
    "ActivationFailure",
    "DuplicateEmailError",
    "EmailSender",
    "IdentityRepository",
    "IdentityUnitOfWork",
    "IdentityUnitOfWorkFactory",
    "PasswordHasher",
    "RegistrationService",
    "RegistrationValidationError",
    "User",
    "VerificationToken",
    "VerificationTokenProvider",
]
