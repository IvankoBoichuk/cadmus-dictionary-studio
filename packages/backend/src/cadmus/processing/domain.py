"""Framework-free model for the async processing-task registry.

Every long-running Cadmus job (bulk OCR scan, per-page OCR suggestions,
article-schema generation, entry field extraction) is fire-and-forget on a
Celery queue whose result backend expires after an hour. This module gives
those jobs a durable record so an editor can see what is running, what
failed and why, and re-run a failed job.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ProcessingTaskKind(StrEnum):
    """The async capability a tracked task belongs to."""

    DICTIONARY_SCAN = "dictionary_scan"
    ENTRY_EXTRACTION = "entry_extraction"
    ARTICLE_SCHEMA_GENERATION = "article_schema_generation"
    OCR_SUGGESTIONS = "ocr_suggestions"


class ProcessingTaskStatus(StrEnum):
    """Transport-neutral lifecycle state, derived from Celery signals."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


ACTIVE_STATUSES: frozenset[ProcessingTaskStatus] = frozenset(
    {ProcessingTaskStatus.QUEUED, ProcessingTaskStatus.RUNNING}
)


@dataclass
class ProcessingTask:
    """One recorded run of a background job for a single dictionary."""

    id: UUID
    dictionary_id: UUID
    kind: ProcessingTaskKind
    celery_task_id: str
    status: ProcessingTaskStatus
    enqueued_by: UUID
    created_at: datetime
    updated_at: datetime
    target_id: UUID | None = None
    target_label: str | None = None
    rerun_params: dict[str, object] = field(default_factory=dict)
    error: str | None = None
    result: dict[str, object] | None = None
    retry_of_id: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def is_retryable(self) -> bool:
        return self.status is ProcessingTaskStatus.FAILED


class ProcessingTaskNotFoundError(Exception):
    """No processing task exists for the given id."""

    def __init__(self, task_id: UUID) -> None:
        super().__init__(f"processing task {task_id} was not found")
        self.task_id = task_id


class ProcessingTaskNotRetryableError(Exception):
    """A retry was requested for a task that has not failed."""

    def __init__(self, task_id: UUID, status: ProcessingTaskStatus) -> None:
        super().__init__(
            f"processing task {task_id} is {status}, only failed tasks can be retried"
        )
        self.task_id = task_id
        self.status = status


class ProcessingTaskKindNotRetryableError(Exception):
    """No re-enqueue path is configured for a task's kind."""

    def __init__(self, kind: ProcessingTaskKind) -> None:
        super().__init__(f"processing task kind {kind} cannot be retried")
        self.kind = kind
