"""Use cases over the processing-task registry."""

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from cadmus.processing.domain import (
    ProcessingTask,
    ProcessingTaskKind,
    ProcessingTaskKindNotRetryableError,
    ProcessingTaskNotFoundError,
    ProcessingTaskNotRetryableError,
    ProcessingTaskStatus,
)
from cadmus.processing.ports import (
    ProcessingTaskUnitOfWorkFactory,
    TaskReenqueuer,
)

# Newest rows kept per dictionary; older completed runs are pruned on insert
# so the registry cannot grow without bound.
_HISTORY_PER_DICTIONARY = 200


class ProcessingTaskService:
    """Record, list and retry tracked background jobs for a dictionary."""

    def __init__(
        self,
        unit_of_work_factory: ProcessingTaskUnitOfWorkFactory,
        *,
        reenqueuers: Mapping[ProcessingTaskKind, TaskReenqueuer] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        history_per_dictionary: int = _HISTORY_PER_DICTIONARY,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._reenqueuers = dict(reenqueuers or {})
        self._clock = clock
        self._history_per_dictionary = history_per_dictionary

    def record_enqueued(
        self,
        *,
        dictionary_id: UUID,
        kind: ProcessingTaskKind,
        celery_task_id: str,
        enqueued_by: UUID,
        target_id: UUID | None = None,
        target_label: str | None = None,
        rerun_params: Mapping[str, object] | None = None,
        retry_of_id: UUID | None = None,
    ) -> ProcessingTask:
        """Persist a freshly queued job. Never raises for a bad recorder
        call -- monitoring must not be able to break the operation it
        tracks -- callers that need the row inspect the return value."""
        now = self._clock()
        task = ProcessingTask(
            id=uuid4(),
            dictionary_id=dictionary_id,
            kind=kind,
            celery_task_id=celery_task_id,
            status=ProcessingTaskStatus.QUEUED,
            enqueued_by=enqueued_by,
            created_at=now,
            updated_at=now,
            target_id=target_id,
            target_label=target_label,
            rerun_params=dict(rerun_params or {}),
            retry_of_id=retry_of_id,
        )
        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.processing_tasks.add(task)
            unit_of_work.processing_tasks.prune_dictionary(
                dictionary_id, keep=self._history_per_dictionary
            )
            unit_of_work.commit()
        return task

    def list_for_dictionary(
        self,
        dictionary_id: UUID,
        *,
        kinds: Sequence[ProcessingTaskKind] | None = None,
        statuses: Sequence[ProcessingTaskStatus] | None = None,
        limit: int = 100,
    ) -> list[ProcessingTask]:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.processing_tasks.list_for_dictionary(
                dictionary_id, kinds=kinds, statuses=statuses, limit=limit
            )

    def get(self, task_id: UUID) -> ProcessingTask:
        with self._unit_of_work_factory() as unit_of_work:
            task = unit_of_work.processing_tasks.get(task_id)
        if task is None:
            raise ProcessingTaskNotFoundError(task_id)
        return task

    def retry(self, task_id: UUID, *, actor_id: UUID) -> ProcessingTask:
        """Re-run a failed task's operation as a new tracked run linked
        back to the original through ``retry_of_id``."""
        task = self.get(task_id)
        if not task.is_retryable:
            raise ProcessingTaskNotRetryableError(task_id, task.status)
        reenqueue = self._reenqueuers.get(task.kind)
        if reenqueue is None:
            raise ProcessingTaskKindNotRetryableError(task.kind)

        new_celery_id = reenqueue(task, actor_id)
        return self.record_enqueued(
            dictionary_id=task.dictionary_id,
            kind=task.kind,
            celery_task_id=new_celery_id,
            enqueued_by=actor_id,
            target_id=task.target_id,
            target_label=task.target_label,
            rerun_params=task.rerun_params,
            retry_of_id=task.id,
        )


class ProcessingTaskStatusRecorder:
    """Applies Celery-signal lifecycle transitions to recorded tasks.

    Used by the worker's signal handlers. Every method is a no-op when no
    row matches the Celery id (untracked tasks: the infra test task,
    geography sync, the VESUM import CLI), so it is always safe to call.
    """

    def __init__(
        self,
        unit_of_work_factory: ProcessingTaskUnitOfWorkFactory,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    def mark_running(self, celery_task_id: str) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            task = unit_of_work.processing_tasks.get_by_celery_id(celery_task_id)
            if task is None or task.status is not ProcessingTaskStatus.QUEUED:
                return
            now = self._clock()
            task.status = ProcessingTaskStatus.RUNNING
            task.started_at = now
            task.updated_at = now
            unit_of_work.processing_tasks.update(task)
            unit_of_work.commit()

    def mark_succeeded(
        self, celery_task_id: str, result: Mapping[str, object] | None = None
    ) -> None:
        self._finish(
            celery_task_id,
            ProcessingTaskStatus.SUCCEEDED,
            result=dict(result) if result is not None else None,
        )

    def mark_failed(self, celery_task_id: str, error: str | None) -> None:
        self._finish(
            celery_task_id,
            ProcessingTaskStatus.FAILED,
            error=(error or "Задача завершилася помилкою.")[:2000],
        )

    def _finish(
        self,
        celery_task_id: str,
        status: ProcessingTaskStatus,
        *,
        result: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        with self._unit_of_work_factory() as unit_of_work:
            task = unit_of_work.processing_tasks.get_by_celery_id(celery_task_id)
            if task is None or task.status not in {
                ProcessingTaskStatus.QUEUED,
                ProcessingTaskStatus.RUNNING,
            }:
                return
            now = self._clock()
            task.status = status
            task.result = result
            task.error = error
            task.finished_at = now
            task.updated_at = now
            unit_of_work.processing_tasks.update(task)
            unit_of_work.commit()
