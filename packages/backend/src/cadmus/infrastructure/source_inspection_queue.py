"""Celery implementation of the sources inspection-queue port."""

from typing import Final
from uuid import UUID

from celery import Celery
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from cadmus.sources.ports import (
    INSPECT_SOURCE_TASK_NAME,
    SourceInspectionQueueUnavailableError,
)

_QUEUE_ERRORS: Final = (OperationalError, RedisError, OSError)


class CeleryInspectionQueue:
    """Hand PDF structural inspection off to the worker through Celery."""

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def enqueue_inspection(self, source_file_id: UUID) -> None:
        try:
            self._celery_app.send_task(
                INSPECT_SOURCE_TASK_NAME,
                args=[str(source_file_id)],
                retry=False,
            )
        except _QUEUE_ERRORS as error:
            raise SourceInspectionQueueUnavailableError(
                "Source inspection queue is unavailable"
            ) from error
