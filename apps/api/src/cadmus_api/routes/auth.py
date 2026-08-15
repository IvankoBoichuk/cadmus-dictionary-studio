"""Thin HTTP adapters for registration and account activation."""

from typing import Any

from cadmus.identity import (
    AccountStatus,
    ActivationError,
    ActivationFailure,
    DuplicateEmailError,
    RegistrationService,
    RegistrationValidationError,
)
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


class RegistrationRequest(BaseModel):
    """Bounded registration input."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)
    password_confirmation: str = Field(min_length=1, max_length=1024)


class RegistrationResponse(BaseModel):
    """Safe account creation response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: AccountStatus
    message: str


class FieldErrorsResponse(BaseModel):
    """Validation errors addressable by form field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    errors: dict[str, str]


class VerificationResponse(BaseModel):
    """Public activation outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str


class VerificationRequest(BaseModel):
    """Verification token supplied in a body so access logs cannot capture it."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)


class VerificationErrorResponse(BaseModel):
    """Safe token error contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: ActivationFailure
    message: str


FIELD_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "model": FieldErrorsResponse,
        "description": "The normalized email is already registered",
    },
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": FieldErrorsResponse,
        "description": "Registration fields are invalid",
    },
}


def create_auth_router(registration: RegistrationService) -> APIRouter:
    """Create auth routes bound to application use cases."""
    router = APIRouter(prefix="/auth", tags=["identity"])

    @router.post(
        "/register",
        response_model=RegistrationResponse,
        status_code=status.HTTP_201_CREATED,
        responses=FIELD_ERROR_RESPONSES,
        summary="Register a pending user account",
    )
    def register(
        request: RegistrationRequest,
    ) -> RegistrationResponse | JSONResponse:
        try:
            user = registration.register(
                request.email,
                request.password,
                request.password_confirmation,
            )
        except RegistrationValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except DuplicateEmailError:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"errors": {"email": "Ця email-адреса вже зареєстрована."}},
            )
        return RegistrationResponse(
            status=user.status,
            message="Акаунт створено. Перевірте email, щоб активувати його.",
        )

    @router.post(
        "/verify-email",
        response_model=VerificationResponse,
        responses={
            status.HTTP_400_BAD_REQUEST: {
                "model": VerificationErrorResponse,
                "description": "The verification token is invalid, expired, or used",
            }
        },
        summary="Activate an account with a one-time email token",
    )
    def verify_email(
        request: VerificationRequest,
    ) -> VerificationResponse | JSONResponse:
        try:
            registration.activate(request.token)
        except ActivationError as error:
            messages = {
                ActivationFailure.INVALID: "Посилання для підтвердження недійсне.",
                ActivationFailure.EXPIRED: "Термін дії посилання минув.",
                ActivationFailure.USED: "Це посилання вже було використано.",
            }
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"code": error.reason, "message": messages[error.reason]},
            )
        return VerificationResponse(message="Email підтверджено. Акаунт активовано.")

    return router
