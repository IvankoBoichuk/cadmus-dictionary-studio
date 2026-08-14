"""Celery implementation of the processing task queue port."""

from typing import Final

from celery import Celery, states
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from cadmus.config import Settings
from cadmus.processing import (
    TEST_TASK_NAME,
    TaskQueueUnavailableError,
    TaskSnapshot,
    TaskStatus,
)

_QUEUE_ERRORS: Final = (OperationalError, RedisError, OSError)


def create_celery_client(settings: Settings) -> Celery:
    """Create a Celery client configured for Redis transport and results."""
    app = Celery(
        "cadmus-api",
        broker=settings.celery_broker_url(),
        backend=settings.celery_result_backend_url(),
    )
    app.conf.update(
        broker_connection_retry_on_startup=True,
        broker_transport_options={"socket_connect_timeout": 2},
        result_backend_transport_options={"socket_connect_timeout": 2},
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
    )
    return app


class CeleryTaskQueue:
    """Submit and inspect the test task through Celery."""

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def enqueue_test_task(self, value: str) -> str:
        try:
            result = self._celery_app.send_task(
                TEST_TASK_NAME,
                args=[value],
                retry=False,
            )
        except _QUEUE_ERRORS as error:
            raise TaskQueueUnavailableError("Task queue is unavailable") from error
        return str(result.id)

    def get_task(self, task_id: str) -> TaskSnapshot:
        try:
            result = self._celery_app.AsyncResult(task_id)
            state = result.state
            value = result.result if state == states.SUCCESS else None
        except _QUEUE_ERRORS as error:
            raise TaskQueueUnavailableError("Task queue is unavailable") from error

        if state == states.SUCCESS:
            payload = value if isinstance(value, dict) else None
            return TaskSnapshot(
                task_id=task_id,
                status=TaskStatus.SUCCEEDED,
                result=payload,
            )
        if state in {states.FAILURE, states.REVOKED}:
            return TaskSnapshot(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error="Task execution failed",
            )
        if state in {states.STARTED, states.RETRY}:
            return TaskSnapshot(task_id=task_id, status=TaskStatus.RUNNING)
        return TaskSnapshot(task_id=task_id, status=TaskStatus.QUEUED)
