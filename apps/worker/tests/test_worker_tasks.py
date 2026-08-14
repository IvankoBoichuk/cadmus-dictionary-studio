import json
import logging

import pytest
from cadmus.config import Environment, Settings
from cadmus_worker.celery_app import create_celery_app, suppress_task_result_logging
from cadmus_worker.tasks import run_test_task


def test_worker_task_returns_result_and_logs_task_id(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="cadmus_worker.tasks")

    execution = run_test_task.apply(args=["hello"], task_id="task-123")

    assert execution.get() == {"echo": "hello"}
    events = [json.loads(record.message) for record in caplog.records]
    assert events == [
        {"event": "test_task_started", "task_id": "task-123"},
        {"event": "test_task_succeeded", "task_id": "task-123"},
    ]


def test_worker_suppresses_celery_success_result_logging() -> None:
    trace_logger = logging.getLogger("celery.app.trace")
    previous_level = trace_logger.level
    try:
        trace_logger.setLevel(logging.INFO)

        suppress_task_result_logging()

        assert trace_logger.level == logging.WARNING
    finally:
        trace_logger.setLevel(previous_level)


def test_worker_task_is_idempotent_for_identical_input() -> None:
    first = run_test_task.apply(args=["hello"], task_id="task-first")
    second = run_test_task.apply(args=["hello"], task_id="task-retry")

    assert first.get() == second.get() == {"echo": "hello"}


def test_worker_configures_retry_timeout_and_json_only_messages() -> None:
    app = create_celery_app(Settings(environment=Environment.TEST))

    assert app.conf.broker_connection_retry is True
    assert app.conf.broker_connection_retry_on_startup is True
    assert app.conf.task_soft_time_limit == 30
    assert app.conf.task_time_limit == 60
    assert app.conf.accept_content == ["json"]
    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"
