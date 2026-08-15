from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from cadmus.identity import (
    AccountStatus,
    ActivationError,
    ActivationFailure,
    DuplicateEmailError,
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


def client_for(service: StubRegistrationService) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            registration_service=cast(RegistrationService, service),
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
