"""HTTP adapter tests for the per-dictionary task monitor routes."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.identity import AccountStatus, AuthenticationService, User
from cadmus.processing import (
    ProcessingTask,
    ProcessingTaskKind,
    ProcessingTaskKindNotRetryableError,
    ProcessingTaskNotFoundError,
    ProcessingTaskNotRetryableError,
    ProcessingTaskService,
    ProcessingTaskStatus,
)
from cadmus.sources import DictionaryAccessError
from cadmus.sources.application import GetDictionaryService
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

OWNER_ID = UUID("8158fd82-2d50-4f4f-af31-e969bab77163")
DICTIONARY_ID = UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


@dataclass
class StubAuthenticationService:
    def authenticate(self, token: str) -> User:
        return User(
            id=OWNER_ID,
            email="owner@example.com",
            password_hash="x",
            status=AccountStatus.ACTIVE,
            created_at=NOW,
            activated_at=NOW,
        )

    def login(self, email: str, password: str) -> None:  # pragma: no cover
        raise AssertionError("not used")

    def logout(self, token: str) -> None:  # pragma: no cover
        raise AssertionError("not used")


@dataclass
class StubGetDictionaryService:
    deny: bool = False

    def get(self, dictionary_id: UUID, actor_id: UUID, **_: object) -> object:
        if self.deny:
            raise DictionaryAccessError(dictionary_id)
        return object()


@dataclass
class StubProcessingTaskService:
    listed: list[ProcessingTask] = field(default_factory=list)
    stored: dict[UUID, ProcessingTask] = field(default_factory=dict)
    retry_result: ProcessingTask | None = None
    retry_error: Exception | None = None
    last_kinds: Sequence[ProcessingTaskKind] | None = None
    last_statuses: Sequence[ProcessingTaskStatus] | None = None
    last_limit: int | None = None
    retry_calls: list[tuple[UUID, UUID]] = field(default_factory=list)

    def list_for_dictionary(
        self,
        dictionary_id: UUID,
        *,
        kinds: Sequence[ProcessingTaskKind] | None = None,
        statuses: Sequence[ProcessingTaskStatus] | None = None,
        limit: int = 100,
    ) -> list[ProcessingTask]:
        self.last_kinds = kinds
        self.last_statuses = statuses
        self.last_limit = limit
        return self.listed

    def get(self, task_id: UUID) -> ProcessingTask:
        if task_id not in self.stored:
            raise ProcessingTaskNotFoundError(task_id)
        return self.stored[task_id]

    def retry(self, task_id: UUID, *, actor_id: UUID) -> ProcessingTask:
        self.retry_calls.append((task_id, actor_id))
        if self.retry_error is not None:
            raise self.retry_error
        assert self.retry_result is not None
        return self.retry_result


def _task(
    *,
    status: ProcessingTaskStatus = ProcessingTaskStatus.SUCCEEDED,
    kind: ProcessingTaskKind = ProcessingTaskKind.DICTIONARY_SCAN,
    task_id: UUID | None = None,
    dictionary_id: UUID = DICTIONARY_ID,
) -> ProcessingTask:
    return ProcessingTask(
        id=task_id or uuid4(),
        dictionary_id=dictionary_id,
        kind=kind,
        celery_task_id=f"celery-{uuid4()}",
        status=status,
        enqueued_by=OWNER_ID,
        created_at=NOW,
        updated_at=NOW,
    )


def client_for(
    processing_task_service: StubProcessingTaskService,
    *,
    deny: bool = False,
    authed: bool = True,
) -> TestClient:
    client = TestClient(
        create_app(
            database_engine=create_engine("sqlite+pysqlite:///:memory:"),
            authentication_service=cast(
                AuthenticationService, StubAuthenticationService()
            ),
            get_dictionary_service=cast(
                GetDictionaryService, StubGetDictionaryService(deny=deny)
            ),
            processing_task_service=cast(
                ProcessingTaskService, processing_task_service
            ),
        )
    )
    if authed:
        client.cookies.set("cadmus_session", "token")
    return client


def test_list_returns_recorded_tasks() -> None:
    service = StubProcessingTaskService(
        listed=[_task(status=ProcessingTaskStatus.RUNNING)]
    )
    client = client_for(service)

    response = client.get(f"/dictionaries/{DICTIONARY_ID}/tasks")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["status"] == "running"
    assert body[0]["kind"] == "dictionary_scan"


def test_list_forwards_kind_and_status_filters() -> None:
    service = StubProcessingTaskService(listed=[])
    client = client_for(service)

    client.get(
        f"/dictionaries/{DICTIONARY_ID}/tasks",
        params={"kind": "entry_extraction", "status": "failed", "limit": 10},
    )

    assert list(service.last_kinds or []) == [ProcessingTaskKind.ENTRY_EXTRACTION]
    assert list(service.last_statuses or []) == [ProcessingTaskStatus.FAILED]
    assert service.last_limit == 10


def test_list_requires_a_session() -> None:
    client = client_for(StubProcessingTaskService(), authed=False)
    assert client.get(f"/dictionaries/{DICTIONARY_ID}/tasks").status_code == 401


def test_list_is_404_when_the_dictionary_is_not_visible() -> None:
    client = client_for(StubProcessingTaskService(), deny=True)
    response = client.get(f"/dictionaries/{DICTIONARY_ID}/tasks")
    assert response.status_code == 404


def test_retry_returns_the_new_task() -> None:
    failed = _task(status=ProcessingTaskStatus.FAILED)
    created = _task(status=ProcessingTaskStatus.QUEUED)
    service = StubProcessingTaskService(
        stored={failed.id: failed}, retry_result=created
    )
    client = client_for(service)

    response = client.post(f"/dictionaries/{DICTIONARY_ID}/tasks/{failed.id}/retry")

    assert response.status_code == 202
    assert response.json()["id"] == str(created.id)
    assert service.retry_calls == [(failed.id, OWNER_ID)]


def test_retry_is_404_for_an_unknown_task() -> None:
    client = client_for(StubProcessingTaskService())
    response = client.post(f"/dictionaries/{DICTIONARY_ID}/tasks/{uuid4()}/retry")
    assert response.status_code == 404


def test_retry_is_404_when_the_task_belongs_to_another_dictionary() -> None:
    other = _task(
        status=ProcessingTaskStatus.FAILED,
        dictionary_id=UUID("99999999-9999-9999-9999-999999999999"),
    )
    service = StubProcessingTaskService(stored={other.id: other})
    client = client_for(service)

    response = client.post(f"/dictionaries/{DICTIONARY_ID}/tasks/{other.id}/retry")
    assert response.status_code == 404
    assert service.retry_calls == []


@pytest.mark.parametrize(
    "error",
    [
        ProcessingTaskNotRetryableError(uuid4(), ProcessingTaskStatus.RUNNING),
        ProcessingTaskKindNotRetryableError(ProcessingTaskKind.OCR_SUGGESTIONS),
    ],
)
def test_retry_is_409_when_the_task_cannot_be_retried(error: Exception) -> None:
    failed = _task(status=ProcessingTaskStatus.FAILED)
    service = StubProcessingTaskService(stored={failed.id: failed}, retry_error=error)
    client = client_for(service)

    response = client.post(f"/dictionaries/{DICTIONARY_ID}/tasks/{failed.id}/retry")
    assert response.status_code == 409


def test_retry_requires_a_session() -> None:
    client = client_for(StubProcessingTaskService(), authed=False)
    assert (
        client.post(f"/dictionaries/{DICTIONARY_ID}/tasks/{uuid4()}/retry").status_code
        == 401
    )
