"""BH-58: HTTP adapter tests for the finish-scanning-stage route."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.lexicography import (
    DictionaryNotReadyToScanError,
    FinishScanningService,
    LexemeAccessError,
)
from cadmus.sources import Dictionary, DictionaryStatus
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@dataclass
class StubAuthenticationService:
    def login(self, email: str, password: str) -> None:
        raise AssertionError("not used")

    def authenticate(self, token: str) -> User:
        return User(
            id=OWNER_ID,
            email="owner@example.com",
            password_hash="not-returned",
            status=AccountStatus.ACTIVE,
            created_at=NOW,
            activated_at=NOW,
        )

    def logout(self, token: str) -> None:
        raise AssertionError("not used")


def _dictionary(**overrides: object) -> Dictionary:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "owner_id": OWNER_ID,
        "status": DictionaryStatus.SCANNED,
        "created_at": NOW,
        "updated_at": NOW,
        "updated_by": OWNER_ID,
    }
    defaults.update(overrides)
    return Dictionary(**defaults)  # type: ignore[arg-type]


@dataclass
class StubFinishScanningService:
    dictionary: Dictionary | None = None
    error: Exception | None = None

    def finish(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        if self.error is not None:
            raise self.error
        assert self.dictionary is not None
        return self.dictionary


def client_for(
    finish_scanning_service: StubFinishScanningService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            finish_scanning_service=cast(
                FinishScanningService,
                finish_scanning_service or StubFinishScanningService(),
            ),
        )
    )


def test_finish_scanning_requires_authentication() -> None:
    with client_for() as client:
        response = client.post(f"/dictionaries/{uuid4()}/finish-scanning")
    assert response.status_code == 401


def test_finish_scanning_returns_the_new_status() -> None:
    dictionary = _dictionary(status=DictionaryStatus.SCANNED)
    service = StubFinishScanningService(dictionary=dictionary)

    with client_for(finish_scanning_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{dictionary.id}/finish-scanning")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(dictionary.id)
    assert body["status"] == "scanned"


def test_finish_scanning_not_owned_returns_404() -> None:
    service = StubFinishScanningService(error=LexemeAccessError(uuid4()))

    with client_for(finish_scanning_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/finish-scanning")

    assert response.status_code == 404


def test_finish_scanning_without_lexemes_returns_422() -> None:
    service = StubFinishScanningService(error=DictionaryNotReadyToScanError(uuid4()))

    with client_for(finish_scanning_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/finish-scanning")

    assert response.status_code == 422
    assert response.json()["code"] == "no_lexemes"
