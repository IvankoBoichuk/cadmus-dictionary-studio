"""Thin Celery entrypoints calling processing application functions."""

import json
import logging

from cadmus.processing import TEST_TASK_NAME, execute_test_task
from celery import Task

from cadmus_worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _log_task_event(event: str, task_id: str) -> None:
    logger.info(json.dumps({"event": event, "task_id": task_id}, sort_keys=True))


@celery_app.task(bind=True, name=TEST_TASK_NAME)  # type: ignore[untyped-decorator]
def run_test_task(task: Task, value: str) -> dict[str, str]:
    """Run the deterministic infrastructure smoke task."""
    task_id = str(task.request.id)
    _log_task_event("test_task_started", task_id)
    result = execute_test_task(value)
    _log_task_event("test_task_succeeded", task_id)
    return result
