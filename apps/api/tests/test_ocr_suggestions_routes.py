"""HTTP adapter tests for the OCR word-suggestion routes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.lexicography import (
    LexemeAccessError,
    LexemePageNotFoundError,
    LexemeSuggestion,
    OcrSuggestionStatus,
    OcrSuggestionTaskSnapshot,
    SuggestLexemesService,
)
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


@dataclass
class StubSuggestLexemesService:
    task_id: str = "task-abc"
    enqueue_error: Exception | None = None
    snapshot: OcrSuggestionTaskSnapshot | None = None
    get_task_error: Exception | None = None

    def enqueue(self, dictionary_id: UUID, actor_id: UUID, page_number: int) -> str:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        return self.task_id

    def get_task(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        page_number: int,
        task_id: str,
    ) -> OcrSuggestionTaskSnapshot:
        if self.get_task_error is not None:
            raise self.get_task_error
        assert self.snapshot is not None
        return self.snapshot


def client_for(
    suggest_service: StubSuggestLexemesService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            suggest_lexemes_service=cast(
                SuggestLexemesService, suggest_service or StubSuggestLexemesService()
            ),
        )
    )


def test_enqueue_suggestions_requires_authentication() -> None:
    with client_for() as client:
        response = client.post(f"/dictionaries/{uuid4()}/pages/1/ocr-suggestions")
    assert response.status_code == 401


def test_enqueue_suggestions_returns_202_with_task_id() -> None:
    service = StubSuggestLexemesService(task_id="task-xyz")

    with client_for(suggest_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/pages/1/ocr-suggestions")

    assert response.status_code == 202
    body = response.json()
    assert body["task_id"] == "task-xyz"
    assert body["status"] == "queued"


def test_enqueue_suggestions_not_owned_or_page_missing_returns_404() -> None:
    for error in (LexemeAccessError(uuid4()), LexemePageNotFoundError(uuid4(), 1)):
        service = StubSuggestLexemesService(enqueue_error=error)
        with client_for(suggest_service=service) as client:
            client.cookies.set("cadmus_session", "token")
            response = client.post(f"/dictionaries/{uuid4()}/pages/1/ocr-suggestions")
        assert response.status_code == 404


def test_get_suggestions_task_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(f"/dictionaries/{uuid4()}/pages/1/ocr-suggestions/task-1")
    assert response.status_code == 401


def test_get_suggestions_task_returns_queued_status_without_suggestions() -> None:
    service = StubSuggestLexemesService(
        snapshot=OcrSuggestionTaskSnapshot(
            task_id="task-1", status=OcrSuggestionStatus.QUEUED
        )
    )

    with client_for(suggest_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/1/ocr-suggestions/task-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert "suggestions" not in body


def test_get_suggestions_task_returns_succeeded_suggestions() -> None:
    service = StubSuggestLexemesService(
        snapshot=OcrSuggestionTaskSnapshot(
            task_id="task-1",
            status=OcrSuggestionStatus.SUCCEEDED,
            suggestions=(
                LexemeSuggestion(
                    source_text="слово",
                    x=10,
                    y=20,
                    width=100,
                    height=40,
                    confidence=0.9,
                ),
            ),
        )
    )

    with client_for(suggest_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/1/ocr-suggestions/task-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["suggestions"] == [
        {
            "source_text": "слово",
            "x": 10.0,
            "y": 20.0,
            "width": 100.0,
            "height": 40.0,
            "confidence": 0.9,
        }
    ]


def test_get_suggestions_task_returns_failure_message() -> None:
    service = StubSuggestLexemesService(
        snapshot=OcrSuggestionTaskSnapshot(
            task_id="task-1",
            status=OcrSuggestionStatus.FAILED,
            error="tesseract failed",
        )
    )

    with client_for(suggest_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/pages/1/ocr-suggestions/task-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == "tesseract failed"


def test_get_suggestions_task_not_owned_or_page_missing_returns_404() -> None:
    for error in (LexemeAccessError(uuid4()), LexemePageNotFoundError(uuid4(), 1)):
        service = StubSuggestLexemesService(get_task_error=error)
        with client_for(suggest_service=service) as client:
            client.cookies.set("cadmus_session", "token")
            response = client.get(
                f"/dictionaries/{uuid4()}/pages/1/ocr-suggestions/task-1"
            )
        assert response.status_code == 404
