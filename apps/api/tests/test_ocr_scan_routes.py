"""HTTP adapter tests for the whole-dictionary OCR scan routes."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.lexicography import (
    DictionaryScanSnapshot,
    LexemeAccessError,
    OcrSuggestionStatus,
    QueueDictionaryScanService,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


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
class StubQueueDictionaryScanService:
    task_id: str = "scan-task-abc"
    enqueue_error: Exception | None = None
    snapshot: DictionaryScanSnapshot | None = None
    get_task_error: Exception | None = None

    def enqueue(self, dictionary_id: UUID, actor_id: UUID) -> str:
        if self.enqueue_error is not None:
            raise self.enqueue_error
        return self.task_id

    def get_task(
        self, dictionary_id: UUID, actor_id: UUID, task_id: str
    ) -> DictionaryScanSnapshot:
        if self.get_task_error is not None:
            raise self.get_task_error
        assert self.snapshot is not None
        return self.snapshot


def client_for(
    scan_service: StubQueueDictionaryScanService | None = None,
    authentication: StubAuthenticationService | None = None,
) -> TestClient:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    return TestClient(
        create_app(
            database_engine=engine,
            authentication_service=cast(
                AuthenticationService, authentication or StubAuthenticationService()
            ),
            queue_dictionary_scan_service=cast(
                QueueDictionaryScanService,
                scan_service or StubQueueDictionaryScanService(),
            ),
        )
    )


def test_enqueue_scan_requires_authentication() -> None:
    with client_for() as client:
        response = client.post(f"/dictionaries/{uuid4()}/ocr-scan")
    assert response.status_code == 401


def test_enqueue_scan_returns_202_with_task_id() -> None:
    service = StubQueueDictionaryScanService(task_id="scan-task-xyz")

    with client_for(scan_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/ocr-scan")

    assert response.status_code == 202
    body = response.json()
    assert body["task_id"] == "scan-task-xyz"
    assert body["status"] == "queued"


def test_enqueue_scan_not_owned_returns_404() -> None:
    service = StubQueueDictionaryScanService(enqueue_error=LexemeAccessError(uuid4()))

    with client_for(scan_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.post(f"/dictionaries/{uuid4()}/ocr-scan")

    assert response.status_code == 404


def test_get_scan_task_requires_authentication() -> None:
    with client_for() as client:
        response = client.get(f"/dictionaries/{uuid4()}/ocr-scan/task-1")
    assert response.status_code == 401


def test_get_scan_task_returns_running_progress() -> None:
    service = StubQueueDictionaryScanService(
        snapshot=DictionaryScanSnapshot(
            task_id="task-1",
            status=OcrSuggestionStatus.RUNNING,
            processed_pages=4,
            total_pages=12,
            created_lexemes=9,
        )
    )

    with client_for(scan_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/ocr-scan/task-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["processed_pages"] == 4
    assert body["total_pages"] == 12
    assert body["created_lexemes"] == 9


def test_get_scan_task_returns_failure_message() -> None:
    service = StubQueueDictionaryScanService(
        snapshot=DictionaryScanSnapshot(
            task_id="task-1",
            status=OcrSuggestionStatus.FAILED,
            error="OCR queue unavailable",
        )
    )

    with client_for(scan_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/ocr-scan/task-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == "OCR queue unavailable"


def test_get_scan_task_not_owned_returns_404() -> None:
    service = StubQueueDictionaryScanService(get_task_error=LexemeAccessError(uuid4()))

    with client_for(scan_service=service) as client:
        client.cookies.set("cadmus_session", "token")
        response = client.get(f"/dictionaries/{uuid4()}/ocr-scan/task-1")

    assert response.status_code == 404
