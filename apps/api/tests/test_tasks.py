from collections.abc import Iterator
from dataclasses import dataclass, field

import pytest
from cadmus.processing import (
    TaskQueueUnavailableError,
    TaskSnapshot,
    TaskStatus,
)
from cadmus_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine


@dataclass
class FakeTaskQueue:
    task_id: str = "task-123"
    snapshot: TaskSnapshot = field(
        default_factory=lambda: TaskSnapshot(
            task_id="task-123",
            status=TaskStatus.SUCCEEDED,
            result={"echo": "hello"},
        )
    )
    unavailable: bool = False
    submitted_values: list[str] = field(default_factory=list)

    def enqueue_test_task(self, value: str) -> str:
        if self.unavailable:
            raise TaskQueueUnavailableError
        self.submitted_values.append(value)
        return self.task_id

    def get_task(self, task_id: str) -> TaskSnapshot:
        if self.unavailable:
            raise TaskQueueUnavailableError
        assert task_id == self.task_id
        return self.snapshot


@pytest.fixture
def database_engine() -> Iterator[Engine]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        yield engine
    finally:
        engine.dispose()


def test_api_enqueues_test_task_and_returns_accepted(database_engine: Engine) -> None:
    queue = FakeTaskQueue()

    with TestClient(
        create_app(database_engine=database_engine, task_queue=queue)
    ) as client:
        response = client.post("/tasks/test", json={"value": "hello"})

    assert response.status_code == 202
    assert response.json() == {"task_id": "task-123", "status": "queued"}
    assert queue.submitted_values == ["hello"]


def test_api_returns_completed_task_result(database_engine: Engine) -> None:
    queue = FakeTaskQueue()

    with TestClient(
        create_app(database_engine=database_engine, task_queue=queue)
    ) as client:
        response = client.get("/tasks/test/task-123")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "task-123",
        "status": "succeeded",
        "result": {"echo": "hello"},
    }


def test_openapi_documents_task_success_and_unavailable_contracts(
    database_engine: Engine,
) -> None:
    with TestClient(
        create_app(database_engine=database_engine, task_queue=FakeTaskQueue())
    ) as client:
        schema = client.get("/openapi.json").json()

    enqueue_responses = schema["paths"]["/tasks/test"]["post"]["responses"]
    result_responses = schema["paths"]["/tasks/test/{task_id}"]["get"]["responses"]
    assert set(enqueue_responses) >= {"202", "422", "503"}
    assert set(result_responses) >= {"200", "422", "503"}
    unavailable_schema = schema["components"]["schemas"]["QueueUnavailableResponse"]
    assert unavailable_schema["additionalProperties"] is False


@pytest.mark.parametrize("method", ["post", "get"])
def test_api_returns_controlled_error_when_queue_is_unavailable(
    method: str,
    database_engine: Engine,
) -> None:
    queue = FakeTaskQueue(unavailable=True)

    with TestClient(
        create_app(database_engine=database_engine, task_queue=queue)
    ) as client:
        if method == "post":
            response = client.post("/tasks/test", json={"value": "hello"})
        else:
            response = client.get("/tasks/test/task-123")

    assert response.status_code == 503
    assert response.json() == {"detail": "Task queue is unavailable"}


@pytest.mark.parametrize(
    "body",
    [{}, {"value": ""}, {"value": "x", "unexpected": True}],
)
def test_api_rejects_invalid_task_input(
    body: dict[str, object],
    database_engine: Engine,
) -> None:
    queue = FakeTaskQueue()

    with TestClient(
        create_app(database_engine=database_engine, task_queue=queue)
    ) as client:
        response = client.post("/tasks/test", json=body)

    assert response.status_code == 422
    assert queue.submitted_values == []


def test_api_rejects_oversized_task_identifier(database_engine: Engine) -> None:
    with TestClient(
        create_app(database_engine=database_engine, task_queue=FakeTaskQueue())
    ) as client:
        response = client.get(f"/tasks/test/{'x' * 129}")

    assert response.status_code == 422
