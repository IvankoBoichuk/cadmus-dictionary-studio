from dataclasses import dataclass
from typing import cast

import pytest
from cadmus.identity import (
    AuthenticationService,
    PasswordResetError,
    PasswordResetFailure,
    PasswordResetService,
    PasswordResetValidationError,
    RegistrationService,
    User,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

NEUTRAL_MESSAGE = (
    "Якщо такий email зареєстровано, ми надіслали інструкції для відновлення пароля."
)


@dataclass
class StubRegistrationService:
    def register(self, email: str, password: str, confirmation: str) -> User:
        raise AssertionError("not used by password reset tests")

    def activate(self, token: str) -> User:
        raise AssertionError("not used by password reset tests")


@dataclass
class StubAuthenticationService:
    def login(self, email: str, password: str) -> object:
        raise AssertionError("not used by password reset tests")

    def authenticate(self, token: str) -> User:
        raise AssertionError("not used by password reset tests")

    def logout(self, token: str) -> None:
        raise AssertionError("not used by password reset tests")


@dataclass
class StubPasswordResetService:
    reset_error: PasswordResetError | PasswordResetValidationError | None = None
    requested_email: str | None = None
    reset_input: tuple[str, str, str] | None = None

    def request_reset(self, email: str) -> None:
        self.requested_email = email

    def reset_password(
        self,
        token: str,
        new_password: str,
        new_password_confirmation: str,
    ) -> None:
        self.reset_input = (token, new_password, new_password_confirmation)
        if self.reset_error is not None:
            raise self.reset_error


def client_for(
    password_reset: StubPasswordResetService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            registration_service=cast(RegistrationService, StubRegistrationService()),
            authentication_service=cast(
                AuthenticationService, StubAuthenticationService()
            ),
            password_reset_service=cast(
                PasswordResetService, password_reset or StubPasswordResetService()
            ),
        )
    )


def test_forgot_password_always_returns_neutral_message() -> None:
    service = StubPasswordResetService()
    with client_for(service) as client:
        response = client.post(
            "/auth/forgot-password", json={"email": "user@example.com"}
        )

    assert response.status_code == 200
    assert response.json() == {"message": NEUTRAL_MESSAGE}
    assert service.requested_email == "user@example.com"


def test_forgot_password_returns_same_message_for_unknown_email() -> None:
    with client_for() as client:
        response = client.post(
            "/auth/forgot-password", json={"email": "unknown@example.com"}
        )

    assert response.status_code == 200
    assert response.json() == {"message": NEUTRAL_MESSAGE}


def test_forgot_password_rejects_missing_email_before_calling_use_case() -> None:
    service = StubPasswordResetService()
    with client_for(service) as client:
        response = client.post("/auth/forgot-password", json={"email": ""})

    assert response.status_code == 422
    assert service.requested_email is None


def test_reset_password_succeeds_and_never_echoes_credentials() -> None:
    service = StubPasswordResetService()
    with client_for(service) as client:
        response = client.post(
            "/auth/reset-password",
            json={
                "token": "one-time-token",
                "new_password": "new-long-password",
                "new_password_confirmation": "new-long-password",
            },
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Пароль змінено. Тепер ви можете увійти."}
    assert service.reset_input == (
        "one-time-token",
        "new-long-password",
        "new-long-password",
    )
    assert "one-time-token" not in str(response.request.url)
    assert "new-long-password" not in str(response.request.url)


def test_reset_password_rejects_weak_password_with_field_errors() -> None:
    service = StubPasswordResetService(
        reset_error=PasswordResetValidationError({"password": "Too short"})
    )
    with client_for(service) as client:
        response = client.post(
            "/auth/reset-password",
            json={
                "token": "one-time-token",
                "new_password": "short",
                "new_password_confirmation": "short",
            },
        )

    assert response.status_code == 422
    assert response.json() == {"errors": {"password": "Too short"}}


@pytest.mark.parametrize(
    ("reason", "expected_message"),
    [
        (PasswordResetFailure.INVALID, "Посилання для відновлення пароля недійсне."),
        (PasswordResetFailure.EXPIRED, "Термін дії посилання минув."),
        (PasswordResetFailure.USED, "Це посилання вже було використано."),
    ],
)
def test_reset_password_returns_controlled_token_failures(
    reason: PasswordResetFailure, expected_message: str
) -> None:
    service = StubPasswordResetService(reset_error=PasswordResetError(reason))
    with client_for(service) as client:
        response = client.post(
            "/auth/reset-password",
            json={
                "token": "one-time-token",
                "new_password": "new-long-password",
                "new_password_confirmation": "new-long-password",
            },
        )

    assert response.status_code == 400
    assert response.json() == {"code": reason, "message": expected_message}


def test_openapi_documents_password_reset_contracts() -> None:
    with client_for() as client:
        schema = client.get("/openapi.json").json()

    assert set(schema["paths"]["/auth/forgot-password"]["post"]["responses"]) >= {
        "200",
        "422",
    }
    assert set(schema["paths"]["/auth/reset-password"]["post"]["responses"]) >= {
        "200",
        "400",
        "422",
    }
