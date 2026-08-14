"""Application contract for the infrastructure-only test task."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

TEST_TASK_NAME = "cadmus.processing.test"


class TaskStatus(StrEnum):
    """Transport-neutral task states exposed to API clients."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    """Current observable state of a background task."""

    task_id: str
    status: TaskStatus
    result: dict[str, str] | None = None
    error: str | None = None


class TaskQueueUnavailableError(RuntimeError):
    """Raised when the queue infrastructure cannot be reached."""


class TaskQueue(Protocol):
    """Port used by the API to submit and observe the test task."""

    def enqueue_test_task(self, value: str) -> str: ...

    def get_task(self, task_id: str) -> TaskSnapshot: ...


def execute_test_task(value: str) -> dict[str, str]:
    """Return a deterministic result without external side effects."""
    return {"echo": value}
