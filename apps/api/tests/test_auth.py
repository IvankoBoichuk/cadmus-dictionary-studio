from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.config import Environment, Settings
from cadmus.identity import (
    AccountStatus,
    ActivationError,
    ActivationFailure,
    AuthenticationError,
    AuthenticationFailure,
    AuthenticationService,
    DuplicateEmailError,
    LoginResult,
    RegistrationService,
    RegistrationValidationError,
    User,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine


@dataclass
class StubRegistrationService:
    register_error: Exception | None = None
    activation_error: ActivationError | None = None
    registered_input: tuple[str, str, str] | None = None
    activated_token: str | None = None

    def register(self, email: str, password: str, confirmation: str) -> User:
        self.registered_input = (email, password, confirmation)
        if self.register_error is not None:
            raise self.register_error
        return User(
            id=uuid4(),
            email=email,
            password_hash="not-returned",
            status=AccountStatus.PENDING_VERIFICATION,
            created_at=datetime.now(UTC),
        )

    def activate(self, token: str) -> User:
        self.activated_token = token
        if self.activation_error is not None:
            raise self.activation_error
        return User(
            id=uuid4(),
            email="user@example.com",
            password_hash="not-returned",
            status=AccountStatus.ACTIVE,
            created_at=datetime.now(UTC),
        )


@dataclass
class StubAuthenticationService:
    login_error: AuthenticationError | None = None
    session_error: AuthenticationError | None = None
    login_input: tuple[str, str] | None = None
    authenticated_token: str | None = None
    logout_tokens: list[str] | None = None

    def login(
        self, email: str, password: str, user_agent: str | None = None
    ) -> LoginResult:
        self.login_input = (email, password)
        if self.login_error is not None:
            raise self.login_error
        return LoginResult(user=self._user(), session_token="raw-session-token")

    def authenticate(self, token: str) -> User:
        self.authenticated_token = token
        if self.session_error is not None:
            raise self.session_error
        return self._user()

    def logout(self, token: str) -> None:
        if self.logout_tokens is None:
            self.logout_tokens = []
        self.logout_tokens.append(token)

    @staticmethod
    def _user() -> User:
        return User(
            id=UUID("8158fd82-2d50-4f4f-af31-e969bab77163"),
            email="user@example.com",
            password_hash="not-returned",
            status=AccountStatus.ACTIVE,
            created_at=datetime.now(UTC),
            activated_at=datetime.now(UTC),
        )


def client_for(
    service: StubRegistrationService,
    authentication: StubAuthenticationService | None = None,
    settings: Settings | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            settings=settings,
            database_engine=engine,
            registration_service=cast(RegistrationService, service),
            authentication_service=cast(
                AuthenticationService,
                authentication or StubAuthenticationService(),
            ),
        )
    )


def test_registration_endpoint_returns_pending_status_without_credentials() -> None:
    service = StubRegistrationService()

    with client_for(service) as client:
        response = client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "long-enough-password",
                "password_confirmation": "long-enough-password",
            },
        )

    assert response.status_code == 201
    assert response.json() == {
        "status": "pending_verification",
        "message": "Акаунт створено. Перевірте email, щоб активувати його.",
    }
    assert service.registered_input == (
        "user@example.com",
        "long-enough-password",
        "long-enough-password",
    )


def test_registration_endpoint_returns_field_validation_errors() -> None:
    service = StubRegistrationService(
        register_error=RegistrationValidationError({"password": "Too short"})
    )

    with client_for(service) as client:
        response = client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "short",
                "password_confirmation": "short",
            },
        )

    assert response.status_code == 422
    assert response.json() == {"errors": {"password": "Too short"}}


def test_registration_endpoint_returns_duplicate_email_at_email_field() -> None:
    service = StubRegistrationService(register_error=DuplicateEmailError())

    with client_for(service) as client:
        response = client.post(
            "/auth/register",
            json={
                "email": "user@example.com",
                "password": "long-enough-password",
                "password_confirmation": "long-enough-password",
            },
        )

    assert response.status_code == 409
    assert response.json() == {
        "errors": {"email": "Ця email-адреса вже зареєстрована."}
    }


def test_verification_endpoint_reports_success_and_controlled_failure() -> None:
    service = StubRegistrationService()
    with client_for(service) as client:
        success = client.post("/auth/verify-email", json={"token": "one-time"})
    assert success.status_code == 200
    assert success.json() == {"message": "Email підтверджено. Акаунт активовано."}
    assert service.activated_token == "one-time"

    service.activation_error = ActivationError(ActivationFailure.USED)
    with client_for(service) as client:
        failure = client.post("/auth/verify-email", json={"token": "one-time"})
    assert failure.status_code == 400
    assert failure.json() == {
        "code": "used",
        "message": "Це посилання вже було використано.",
    }


def test_openapi_documents_registration_and_verification_contracts() -> None:
    with client_for(StubRegistrationService()) as client:
        schema = client.get("/openapi.json").json()

    assert set(schema["paths"]["/auth/register"]["post"]["responses"]) >= {
        "201",
        "409",
        "422",
    }
    assert set(schema["paths"]["/auth/verify-email"]["post"]["responses"]) >= {
        "200",
        "400",
        "422",
    }
    assert set(schema["paths"]["/auth/login"]["post"]["responses"]) >= {
        "200",
        "401",
        "403",
        "422",
    }
    assert set(schema["paths"]["/auth/session"]["get"]["responses"]) >= {
        "200",
        "401",
    }
    assert set(schema["paths"]["/auth/logout"]["post"]["responses"]) >= {
        "200",
    }


def test_login_sets_protected_session_cookie_without_returning_credentials() -> None:
    authentication = StubAuthenticationService()
    with client_for(StubRegistrationService(), authentication) as client:
        response = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "secret-password"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "id": "8158fd82-2d50-4f4f-af31-e969bab77163",
        "email": "user@example.com",
        "name": None,
    }
    assert authentication.login_input == ("user@example.com", "secret-password")
    assert "secret-password" not in str(response.request.url)
    assert "raw-session-token" not in response.text
    cookie = response.headers["set-cookie"]
    assert "cadmus_session=raw-session-token" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert response.headers["cache-control"] == "no-store"


def test_login_uses_secure_cookie_in_production() -> None:
    with client_for(
        StubRegistrationService(),
        StubAuthenticationService(),
        Settings(environment=Environment.PRODUCTION),
    ) as client:
        response = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "secret-password"},
        )

    assert "Secure" in response.headers["set-cookie"]


def test_login_rejects_missing_fields_before_calling_use_case() -> None:
    authentication = StubAuthenticationService()
    with client_for(StubRegistrationService(), authentication) as client:
        response = client.post("/auth/login", json={"email": "", "password": ""})

    assert response.status_code == 422
    assert authentication.login_input is None


@pytest.mark.parametrize(
    ("reason", "expected_status", "expected_message"),
    [
        (
            AuthenticationFailure.INVALID_CREDENTIALS,
            401,
            "Неправильні облікові дані.",
        ),
        (
            AuthenticationFailure.UNVERIFIED_ACCOUNT,
            403,
            "Підтвердьте акаунт перед входом.",
        ),
    ],
)
def test_login_returns_controlled_authentication_failures(
    reason: AuthenticationFailure,
    expected_status: int,
    expected_message: str,
) -> None:
    authentication = StubAuthenticationService(login_error=AuthenticationError(reason))
    with client_for(StubRegistrationService(), authentication) as client:
        response = client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "not-logged"},
        )

    assert response.status_code == expected_status
    assert response.json() == {"code": reason, "message": expected_message}
    assert "not-logged" not in response.text


def test_session_endpoint_requires_and_resolves_cookie() -> None:
    authentication = StubAuthenticationService()
    with client_for(StubRegistrationService(), authentication) as client:
        unauthorized = client.get("/auth/session")
        client.cookies.set("cadmus_session", "browser-session-token")
        authorized = client.get("/auth/session")

    assert unauthorized.status_code == 401
    assert unauthorized.json() == {
        "code": "invalid_session",
        "message": "Потрібна авторизація.",
    }
    assert authorized.status_code == 200
    assert authorized.json()["email"] == "user@example.com"
    assert authentication.authenticated_token == "browser-session-token"


def test_logout_invalidates_session_and_expires_cookie() -> None:
    authentication = StubAuthenticationService()
    with client_for(StubRegistrationService(), authentication) as client:
        client.cookies.set("cadmus_session", "browser-session-token")
        response = client.post("/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"message": "Ви вийшли із системи."}
    assert authentication.logout_tokens == ["browser-session-token"]
    cookie = response.headers["set-cookie"]
    assert "cadmus_session=" in cookie
    assert "Max-Age=0" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert response.headers["cache-control"] == "no-store"


def test_logout_without_session_is_idempotent_and_does_not_call_use_case() -> None:
    authentication = StubAuthenticationService()
    with client_for(StubRegistrationService(), authentication) as client:
        first = client.post("/auth/logout")
        second = client.post("/auth/logout")

    assert first.status_code == 200
    assert second.status_code == 200
    assert authentication.logout_tokens is None
