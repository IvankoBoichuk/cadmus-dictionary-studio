"""Thin HTTP adapters for identity use cases."""

from datetime import timedelta
from typing import Any
from uuid import UUID

from cadmus.identity import (
    AccountStatus,
    ActivationError,
    ActivationFailure,
    AuthenticationError,
    AuthenticationFailure,
    AuthenticationService,
    DuplicateEmailError,
    PasswordResetError,
    PasswordResetFailure,
    PasswordResetService,
    PasswordResetValidationError,
    RegistrationService,
    RegistrationValidationError,
)
from fastapi import APIRouter, Cookie, Response, status
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


class LoginRequest(BaseModel):
    """Bounded login input carried only in a POST body."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class AuthenticatedUserResponse(BaseModel):
    """Non-sensitive identity details for an authenticated browser."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    email: str


class AuthenticationErrorResponse(BaseModel):
    """Safe authentication failure contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: AuthenticationFailure
    message: str


class LogoutResponse(BaseModel):
    """Non-sensitive idempotent logout outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str


class ForgotPasswordRequest(BaseModel):
    """Bounded password-reset request input carried only in a POST body."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254)


class ForgotPasswordResponse(BaseModel):
    """Neutral outcome that never discloses whether the email is registered."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str


class ResetPasswordRequest(BaseModel):
    """Password reset confirmation carried only in a POST body."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=1, max_length=1024)
    new_password_confirmation: str = Field(min_length=1, max_length=1024)


class ResetPasswordResponse(BaseModel):
    """Public password reset outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str


class PasswordResetErrorResponse(BaseModel):
    """Safe reset-token error contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: PasswordResetFailure
    message: str


SESSION_COOKIE_NAME = "cadmus_session"


def set_session_cookie(
    response: Response,
    session_token: str,
    session_lifetime: timedelta,
    secure_cookie: bool,
) -> None:
    """Set the authenticated-session cookie shared by all login flows."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=int(session_lifetime.total_seconds()),
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/",
    )


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


def create_auth_router(
    registration: RegistrationService,
    authentication: AuthenticationService,
    password_reset: PasswordResetService,
    session_lifetime: timedelta,
    secure_cookie: bool,
) -> APIRouter:
    """Create auth routes bound to application use cases."""
    router = APIRouter(prefix="/auth", tags=["identity"])

    @router.post(
        "/login",
        response_model=AuthenticatedUserResponse,
        responses={
            status.HTTP_401_UNAUTHORIZED: {
                "model": AuthenticationErrorResponse,
                "description": "The email or password is incorrect",
            },
            status.HTTP_403_FORBIDDEN: {
                "model": AuthenticationErrorResponse,
                "description": "The account has not been verified",
            },
        },
        summary="Create an authenticated browser session",
    )
    def login(
        request: LoginRequest,
        response: Response,
    ) -> AuthenticatedUserResponse | JSONResponse:
        try:
            result = authentication.login(request.email, request.password)
        except AuthenticationError as error:
            if error.reason is AuthenticationFailure.UNVERIFIED_ACCOUNT:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "code": error.reason,
                        "message": "Підтвердьте акаунт перед входом.",
                    },
                    headers={"Cache-Control": "no-store"},
                )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": AuthenticationFailure.INVALID_CREDENTIALS,
                    "message": "Неправильні облікові дані.",
                },
                headers={"Cache-Control": "no-store"},
            )

        set_session_cookie(
            response, result.session_token, session_lifetime, secure_cookie
        )
        response.headers["Cache-Control"] = "no-store"
        return AuthenticatedUserResponse(id=result.user.id, email=result.user.email)

    @router.get(
        "/session",
        response_model=AuthenticatedUserResponse,
        responses={
            status.HTTP_401_UNAUTHORIZED: {
                "model": AuthenticationErrorResponse,
                "description": "The browser has no valid session",
            }
        },
        summary="Resolve the current authenticated browser session",
    )
    def current_session(
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> AuthenticatedUserResponse | JSONResponse:
        try:
            if session_token is None:
                raise AuthenticationError(AuthenticationFailure.INVALID_SESSION)
            user = authentication.authenticate(session_token)
        except AuthenticationError:
            response = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": AuthenticationFailure.INVALID_SESSION,
                    "message": "Потрібна авторизація.",
                },
                headers={"Cache-Control": "no-store"},
            )
            response.delete_cookie(SESSION_COOKIE_NAME, path="/")
            return response
        return JSONResponse(
            content=AuthenticatedUserResponse(id=user.id, email=user.email).model_dump(
                mode="json"
            ),
            headers={"Cache-Control": "no-store"},
        )

    @router.post(
        "/logout",
        response_model=LogoutResponse,
        summary="Invalidate the current authenticated browser session",
    )
    def logout(
        response: Response,
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> LogoutResponse:
        if session_token is not None:
            authentication.logout(session_token)
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path="/",
            secure=secure_cookie,
            httponly=True,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"
        return LogoutResponse(message="Ви вийшли із системи.")

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

    @router.post(
        "/forgot-password",
        response_model=ForgotPasswordResponse,
        summary="Request a one-time password reset link",
    )
    def forgot_password(
        request: ForgotPasswordRequest,
    ) -> ForgotPasswordResponse:
        password_reset.request_reset(request.email)
        return ForgotPasswordResponse(
            message=(
                "Якщо такий email зареєстровано, ми надіслали інструкції "
                "для відновлення пароля."
            )
        )

    @router.post(
        "/reset-password",
        response_model=ResetPasswordResponse,
        responses={
            status.HTTP_400_BAD_REQUEST: {
                "model": PasswordResetErrorResponse,
                "description": "The reset token is invalid, expired, or used",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The new password is invalid",
            },
        },
        summary="Set a new password with a one-time reset token",
    )
    def reset_password(
        request: ResetPasswordRequest,
    ) -> ResetPasswordResponse | JSONResponse:
        try:
            password_reset.reset_password(
                request.token,
                request.new_password,
                request.new_password_confirmation,
            )
        except PasswordResetValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except PasswordResetError as error:
            messages = {
                PasswordResetFailure.INVALID: (
                    "Посилання для відновлення пароля недійсне."
                ),
                PasswordResetFailure.EXPIRED: "Термін дії посилання минув.",
                PasswordResetFailure.USED: "Це посилання вже було використано.",
            }
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"code": error.reason, "message": messages[error.reason]},
            )
        return ResetPasswordResponse(message="Пароль змінено. Тепер ви можете увійти.")

    return router
