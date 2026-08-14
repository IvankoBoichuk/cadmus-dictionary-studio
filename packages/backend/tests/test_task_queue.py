from unittest.mock import Mock

import pytest
from cadmus.infrastructure.task_queue import CeleryTaskQueue
from cadmus.processing import TaskQueueUnavailableError, TaskStatus
from celery import Celery, states
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError


def test_celery_queue_sends_named_test_task_without_retry() -> None:
    celery_app = Mock(spec=Celery)
    celery_app.send_task.return_value.id = "task-123"
    queue = CeleryTaskQueue(celery_app)

    task_id = queue.enqueue_test_task("hello")

    assert task_id == "task-123"
    celery_app.send_task.assert_called_once_with(
        "cadmus.processing.test",
        args=["hello"],
        retry=False,
    )


def test_celery_queue_maps_successful_result() -> None:
    celery_app = Mock(spec=Celery)
    celery_app.AsyncResult.return_value.state = states.SUCCESS
    celery_app.AsyncResult.return_value.result = {"echo": "hello"}
    queue = CeleryTaskQueue(celery_app)

    snapshot = queue.get_task("task-123")

    assert snapshot.task_id == "task-123"
    assert snapshot.status is TaskStatus.SUCCEEDED
    assert snapshot.result == {"echo": "hello"}


def test_celery_queue_maps_broker_failure_to_controlled_error() -> None:
    celery_app = Mock(spec=Celery)
    celery_app.send_task.side_effect = OperationalError("connection refused")
    queue = CeleryTaskQueue(celery_app)

    with pytest.raises(TaskQueueUnavailableError, match="unavailable"):
        queue.enqueue_test_task("hello")


def test_celery_queue_maps_result_backend_failure_to_controlled_error() -> None:
    celery_app = Mock(spec=Celery)
    celery_app.AsyncResult.side_effect = RedisError("connection refused")
    queue = CeleryTaskQueue(celery_app)

    with pytest.raises(TaskQueueUnavailableError, match="unavailable"):
        queue.get_task("task-123")
