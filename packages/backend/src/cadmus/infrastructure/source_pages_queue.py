"""Celery implementation of the sources page-split queue port."""

from typing import Final
from uuid import UUID

from celery import Celery
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from cadmus.sources.ports import (
    SPLIT_PAGES_TASK_NAME,
    SourcePagesQueueUnavailableError,
)

_QUEUE_ERRORS: Final = (OperationalError, RedisError, OSError)


class CeleryPagesQueue:
    """Hand PDF page rendering off to the worker through Celery."""

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def enqueue_split(self, source_file_id: UUID) -> None:
        try:
            self._celery_app.send_task(
                SPLIT_PAGES_TASK_NAME,
                args=[str(source_file_id)],
                retry=False,
            )
        except _QUEUE_ERRORS as error:
            raise SourcePagesQueueUnavailableError(
                "Page split queue is unavailable"
            ) from error
