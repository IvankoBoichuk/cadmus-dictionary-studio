"""Thin HTTP adapters for identity use cases."""

from datetime import datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from cadmus.identity import (
    AccountService,
    AccountStatus,
    ActivationError,
    ActivationFailure,
    AuthenticationError,
    AuthenticationFailure,
    AuthenticationService,
    DuplicateEmailError,
    EmailChangeError,
    EmailChangeFailure,
    EmailChangeValidationError,
    PasswordResetError,
    PasswordResetFailure,
    PasswordResetService,
    PasswordResetValidationError,
    ProfileValidationError,
    RegistrationService,
    RegistrationValidationError,
    SessionNotFoundError,
    User,
)
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Path,
    Request,
    Response,
    status,
)
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
    name: str | None = None


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


class AccountMessageResponse(BaseModel):
    """A neutral, non-sensitive account-action outcome."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str


class AccountErrorResponse(BaseModel):
    """A safe, generic account-action error contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class UpdateProfileRequest(BaseModel):
    """Editable profile fields for a signed-in user."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=200)


class ChangePasswordRequest(BaseModel):
    """Password change carried only in a POST body from an active session."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)
    new_password_confirmation: str = Field(min_length=1, max_length=1024)


class ChangeEmailRequest(BaseModel):
    """Request to move the account to a new, still-unconfirmed email address."""

    model_config = ConfigDict(extra="forbid")

    new_email: str = Field(min_length=1, max_length=254)
    current_password: str = Field(min_length=1, max_length=1024)


class ConfirmEmailChangeRequest(BaseModel):
    """Email-change token supplied in a body so access logs cannot capture it."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)


class EmailChangeErrorResponse(BaseModel):
    """Safe email-change-token error contract."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: EmailChangeFailure
    message: str


class SessionSummary(BaseModel):
    """A user-facing summary of one active server-side session."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    created_at: datetime
    expires_at: datetime
    user_agent: str | None
    current: bool


class SessionListResponse(BaseModel):
    """The signed-in user's active sessions, newest first."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sessions: list[SessionSummary]


class RevokeOtherSessionsResponse(BaseModel):
    """Count of sessions ended by a "sign out everywhere else" request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    revoked: int


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
    account: AccountService,
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
        http_request: Request,
    ) -> AuthenticatedUserResponse | JSONResponse:
        try:
            result = authentication.login(
                request.email,
                request.password,
                user_agent=http_request.headers.get("user-agent"),
            )
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
        return AuthenticatedUserResponse(
            id=result.user.id, email=result.user.email, name=result.user.name
        )

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
            content=AuthenticatedUserResponse(
                id=user.id, email=user.email, name=user.name
            ).model_dump(mode="json"),
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

    unauthorized_response: dict[int | str, dict[str, Any]] = {
        status.HTTP_401_UNAUTHORIZED: {
            "model": AuthenticationErrorResponse,
            "description": "The browser has no valid session",
        }
    }

    def current_identity(
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> tuple[User, str]:
        if session_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": AuthenticationFailure.INVALID_SESSION,
                    "message": "Потрібна авторизація.",
                },
            )
        try:
            user = authentication.authenticate(session_token)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": error.reason, "message": "Потрібна авторизація."},
            ) from error
        return user, session_token

    Identity = Annotated[tuple[User, str], Depends(current_identity)]

    def _wrong_password() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "code": AuthenticationFailure.INVALID_CREDENTIALS,
                "message": "Поточний пароль неправильний.",
            },
            headers={"Cache-Control": "no-store"},
        )

    @router.get(
        "/account",
        response_model=AuthenticatedUserResponse,
        responses=unauthorized_response,
        summary="Resolve the signed-in user's editable account details",
    )
    def get_account(identity: Identity) -> AuthenticatedUserResponse:
        user, _ = identity
        return AuthenticatedUserResponse(id=user.id, email=user.email, name=user.name)

    @router.patch(
        "/account",
        response_model=AuthenticatedUserResponse,
        responses={
            **unauthorized_response,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The profile fields are invalid",
            },
        },
        summary="Update the signed-in user's profile",
    )
    def update_account(
        request: UpdateProfileRequest, identity: Identity
    ) -> AuthenticatedUserResponse | JSONResponse:
        user, _ = identity
        try:
            updated = account.update_profile(user.id, request.name)
        except ProfileValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        return AuthenticatedUserResponse(
            id=updated.id, email=updated.email, name=updated.name
        )

    @router.post(
        "/account/change-password",
        response_model=AccountMessageResponse,
        responses={
            **unauthorized_response,
            status.HTTP_403_FORBIDDEN: {
                "model": AuthenticationErrorResponse,
                "description": "The current password is incorrect",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The new password is invalid",
            },
        },
        summary="Change the password from within an active session",
    )
    def change_password(
        request: ChangePasswordRequest, identity: Identity
    ) -> AccountMessageResponse | JSONResponse:
        user, raw_token = identity
        try:
            account.change_password(
                user_id=user.id,
                current_raw_token=raw_token,
                current_password=request.current_password,
                new_password=request.new_password,
                new_password_confirmation=request.new_password_confirmation,
            )
        except PasswordResetValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except AuthenticationError:
            return _wrong_password()
        return AccountMessageResponse(
            message="Пароль змінено. Інші пристрої вийшли із системи."
        )

    @router.post(
        "/account/change-email",
        response_model=AccountMessageResponse,
        responses={
            **unauthorized_response,
            status.HTTP_403_FORBIDDEN: {
                "model": AuthenticationErrorResponse,
                "description": "The current password is incorrect",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The new email is invalid or already registered",
            },
        },
        summary="Request a confirmed move to a new email address",
    )
    def change_email(
        request: ChangeEmailRequest, identity: Identity
    ) -> AccountMessageResponse | JSONResponse:
        user, _ = identity
        try:
            account.request_email_change(
                user.id, request.new_email, request.current_password
            )
        except EmailChangeValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except AuthenticationError:
            return _wrong_password()
        return AccountMessageResponse(
            message=(
                "Ми надіслали лист на нову адресу — відкрийте посилання з нього, "
                "щоб підтвердити зміну."
            )
        )

    @router.post(
        "/confirm-email-change",
        response_model=AccountMessageResponse,
        responses={
            status.HTTP_400_BAD_REQUEST: {
                "model": EmailChangeErrorResponse,
                "description": "The token is invalid, expired, or used",
            }
        },
        summary="Confirm a pending email change with a one-time token",
    )
    def confirm_email_change(
        request: ConfirmEmailChangeRequest,
    ) -> AccountMessageResponse | JSONResponse:
        try:
            account.confirm_email_change(request.token)
        except EmailChangeError as error:
            messages = {
                EmailChangeFailure.INVALID: "Посилання для зміни email недійсне.",
                EmailChangeFailure.EXPIRED: "Термін дії посилання минув.",
                EmailChangeFailure.USED: "Це посилання вже було використано.",
            }
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"code": error.reason, "message": messages[error.reason]},
            )
        return AccountMessageResponse(
            message="Email оновлено. Тепер увійдіть з новою адресою."
        )

    @router.get(
        "/sessions",
        response_model=SessionListResponse,
        responses=unauthorized_response,
        summary="List the signed-in user's active sessions",
    )
    def list_account_sessions(identity: Identity) -> SessionListResponse:
        user, raw_token = identity
        return SessionListResponse(
            sessions=[
                SessionSummary(
                    id=view.id,
                    created_at=view.created_at,
                    expires_at=view.expires_at,
                    user_agent=view.user_agent,
                    current=view.is_current,
                )
                for view in account.list_sessions(user.id, raw_token)
            ]
        )

    @router.delete(
        "/sessions/{session_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={
            **unauthorized_response,
            status.HTTP_404_NOT_FOUND: {
                "model": AccountErrorResponse,
                "description": "No such session for this user",
            },
        },
        summary="Revoke one of the signed-in user's sessions",
    )
    def revoke_account_session(
        identity: Identity,
        session_id: Annotated[UUID, Path()],
    ) -> Response:
        user, _ = identity
        try:
            account.revoke_session(user.id, session_id)
        except SessionNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "not_found", "message": "Сесію не знайдено."},
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/sessions/revoke-others",
        response_model=RevokeOtherSessionsResponse,
        responses=unauthorized_response,
        summary="Revoke every session except the caller's own",
    )
    def revoke_other_account_sessions(
        identity: Identity,
    ) -> RevokeOtherSessionsResponse:
        user, raw_token = identity
        return RevokeOtherSessionsResponse(
            revoked=account.revoke_other_sessions(user.id, raw_token)
        )

    return router
