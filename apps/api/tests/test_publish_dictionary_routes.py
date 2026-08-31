"""HTTP adapter tests for the publish-dictionary route."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.sources import (
    Dictionary,
    DictionaryAccessError,
    DictionaryNotProcessedError,
    DictionaryStatus,
    PublishDictionaryService,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


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


@dataclass
class StubPublishDictionaryService:
    dictionary: Dictionary | None = None
    error: Exception | None = None

    def publish(self, dictionary_id: UUID, actor_id: UUID) -> Dictionary:
        if self.error is not None:
            raise self.error
        assert self.dictionary is not None
        return self.dictionary


def client_for(
    publish_dictionary_service: StubPublishDictionaryService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, StubAuthenticationService()
            ),
            publish_dictionary_service=cast(
                PublishDictionaryService,
                publish_dictionary_service or StubPublishDictionaryService(),
            ),
        )
    )


def _dictionary(status: DictionaryStatus) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=OWNER_ID,
        status=status,
        created_at=NOW,
        updated_at=NOW,
        updated_by=OWNER_ID,
    )


def test_publish_requires_authentication() -> None:
    with client_for() as client:
        response = client.post(f"/dictionaries/{uuid4()}/publish")
    assert response.status_code == 401


def test_publish_returns_the_published_status() -> None:
    dictionary = _dictionary(DictionaryStatus.PUBLISHED)
    service = StubPublishDictionaryService(dictionary=dictionary)

    with client_for(service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{dictionary.id}/publish")

    assert response.status_code == 200
    assert response.json() == {"id": str(dictionary.id), "status": "published"}


def test_publish_unknown_dictionary_returns_404() -> None:
    service = StubPublishDictionaryService(error=DictionaryAccessError(uuid4()))

    with client_for(service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/publish")

    assert response.status_code == 404


def test_publish_not_processed_returns_422() -> None:
    service = StubPublishDictionaryService(error=DictionaryNotProcessedError(uuid4()))

    with client_for(service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/publish")

    assert response.status_code == 422
    assert response.json()["code"] == "not_processed"
