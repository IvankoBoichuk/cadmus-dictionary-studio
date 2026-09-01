"""Use-case tests for the processing-task registry (monitor + retry)."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.processing import (
    ProcessingTask,
    ProcessingTaskKind,
    ProcessingTaskKindNotRetryableError,
    ProcessingTaskNotFoundError,
    ProcessingTaskNotRetryableError,
    ProcessingTaskService,
    ProcessingTaskStatus,
)
from cadmus.processing.application import ProcessingTaskStatusRecorder
from cadmus.processing.ports import (
    ProcessingTaskRepository,
    ProcessingTaskUnitOfWorkFactory,
    TaskReenqueuer,
)

DICTIONARY_ID = UUID("11111111-1111-1111-1111-111111111111")
ACTOR_ID = UUID("22222222-2222-2222-2222-222222222222")
OTHER_ACTOR_ID = UUID("33333333-3333-3333-3333-333333333333")

_CLOCK = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


class MemoryProcessingTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[UUID, ProcessingTask] = {}
        self.pruned: list[tuple[UUID, int]] = []

    def add(self, task: ProcessingTask) -> None:
        self.tasks[task.id] = task

    def get(self, task_id: UUID) -> ProcessingTask | None:
        return self.tasks.get(task_id)

    def get_by_celery_id(self, celery_task_id: str) -> ProcessingTask | None:
        for task in self.tasks.values():
            if task.celery_task_id == celery_task_id:
                return task
        return None

    def list_for_dictionary(
        self,
        dictionary_id: UUID,
        *,
        kinds: Sequence[ProcessingTaskKind] | None = None,
        statuses: Sequence[ProcessingTaskStatus] | None = None,
        limit: int = 100,
    ) -> list[ProcessingTask]:
        rows = [
            task
            for task in self.tasks.values()
            if task.dictionary_id == dictionary_id
            and (kinds is None or task.kind in kinds)
            and (statuses is None or task.status in statuses)
        ]
        rows.sort(key=lambda task: task.created_at, reverse=True)
        return rows[:limit]

    def update(self, task: ProcessingTask) -> None:
        self.tasks[task.id] = task

    def prune_dictionary(self, dictionary_id: UUID, *, keep: int) -> None:
        self.pruned.append((dictionary_id, keep))


class MemoryUnitOfWork:
    def __init__(self, repository: MemoryProcessingTaskRepository) -> None:
        self.processing_tasks = cast(ProcessingTaskRepository, repository)
        self.committed = 0

    def __enter__(self) -> "MemoryUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.committed += 1


def _factory(
    repository: MemoryProcessingTaskRepository,
) -> ProcessingTaskUnitOfWorkFactory:
    return lambda: MemoryUnitOfWork(repository)


def _service(
    repository: MemoryProcessingTaskRepository,
    *,
    reenqueuers: Mapping[ProcessingTaskKind, TaskReenqueuer] | None = None,
) -> ProcessingTaskService:
    return ProcessingTaskService(
        _factory(repository),
        reenqueuers=reenqueuers,
        clock=lambda: _CLOCK,
    )


def test_record_enqueued_persists_a_queued_task_and_prunes() -> None:
    repository = MemoryProcessingTaskRepository()
    service = _service(repository)

    task = service.record_enqueued(
        dictionary_id=DICTIONARY_ID,
        kind=ProcessingTaskKind.DICTIONARY_SCAN,
        celery_task_id="celery-1",
        enqueued_by=ACTOR_ID,
    )

    assert task.status is ProcessingTaskStatus.QUEUED
    assert repository.tasks[task.id].celery_task_id == "celery-1"
    assert repository.pruned == [(DICTIONARY_ID, 200)]


def test_list_for_dictionary_is_newest_first() -> None:
    repository = MemoryProcessingTaskRepository()
    service = _service(repository)
    for index in range(3):
        repository.add(
            ProcessingTask(
                id=uuid4(),
                dictionary_id=DICTIONARY_ID,
                kind=ProcessingTaskKind.ENTRY_EXTRACTION,
                celery_task_id=f"celery-{index}",
                status=ProcessingTaskStatus.SUCCEEDED,
                enqueued_by=ACTOR_ID,
                created_at=datetime(2026, 9, 1, 10, index, tzinfo=UTC),
                updated_at=_CLOCK,
            )
        )

    rows = service.list_for_dictionary(DICTIONARY_ID)

    assert [row.celery_task_id for row in rows] == [
        "celery-2",
        "celery-1",
        "celery-0",
    ]


def test_get_unknown_task_raises() -> None:
    service = _service(MemoryProcessingTaskRepository())
    with pytest.raises(ProcessingTaskNotFoundError):
        service.get(uuid4())


def test_retry_reenqueues_and_links_back_to_the_original() -> None:
    repository = MemoryProcessingTaskRepository()
    failed = ProcessingTask(
        id=uuid4(),
        dictionary_id=DICTIONARY_ID,
        kind=ProcessingTaskKind.ARTICLE_SCHEMA_GENERATION,
        celery_task_id="celery-old",
        status=ProcessingTaskStatus.FAILED,
        enqueued_by=ACTOR_ID,
        created_at=_CLOCK,
        updated_at=_CLOCK,
        error="boom",
    )
    repository.add(failed)
    seen: list[tuple[UUID, UUID]] = []

    def reenqueue(task: ProcessingTask, actor_id: UUID) -> str:
        seen.append((task.id, actor_id))
        return "celery-new"

    service = _service(
        repository,
        reenqueuers={ProcessingTaskKind.ARTICLE_SCHEMA_GENERATION: reenqueue},
    )

    created = service.retry(failed.id, actor_id=OTHER_ACTOR_ID)

    assert seen == [(failed.id, OTHER_ACTOR_ID)]
    assert created.celery_task_id == "celery-new"
    assert created.retry_of_id == failed.id
    assert created.enqueued_by == OTHER_ACTOR_ID
    assert created.status is ProcessingTaskStatus.QUEUED


def test_retry_rejects_a_task_that_has_not_failed() -> None:
    repository = MemoryProcessingTaskRepository()
    running = ProcessingTask(
        id=uuid4(),
        dictionary_id=DICTIONARY_ID,
        kind=ProcessingTaskKind.DICTIONARY_SCAN,
        celery_task_id="celery-run",
        status=ProcessingTaskStatus.RUNNING,
        enqueued_by=ACTOR_ID,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    repository.add(running)
    service = _service(
        repository,
        reenqueuers={ProcessingTaskKind.DICTIONARY_SCAN: lambda task, actor: "x"},
    )

    with pytest.raises(ProcessingTaskNotRetryableError):
        service.retry(running.id, actor_id=ACTOR_ID)


def test_retry_rejects_a_kind_without_a_reenqueuer() -> None:
    repository = MemoryProcessingTaskRepository()
    failed = ProcessingTask(
        id=uuid4(),
        dictionary_id=DICTIONARY_ID,
        kind=ProcessingTaskKind.OCR_SUGGESTIONS,
        celery_task_id="celery-x",
        status=ProcessingTaskStatus.FAILED,
        enqueued_by=ACTOR_ID,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    repository.add(failed)
    service = _service(repository, reenqueuers={})

    with pytest.raises(ProcessingTaskKindNotRetryableError):
        service.retry(failed.id, actor_id=ACTOR_ID)


def _tracked(status: ProcessingTaskStatus) -> ProcessingTask:
    return ProcessingTask(
        id=uuid4(),
        dictionary_id=DICTIONARY_ID,
        kind=ProcessingTaskKind.DICTIONARY_SCAN,
        celery_task_id="celery-live",
        status=status,
        enqueued_by=ACTOR_ID,
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _recorder(
    repository: MemoryProcessingTaskRepository,
) -> ProcessingTaskStatusRecorder:
    return ProcessingTaskStatusRecorder(_factory(repository), clock=lambda: _CLOCK)


def test_status_recorder_marks_running_then_succeeded() -> None:
    repository = MemoryProcessingTaskRepository()
    task = _tracked(ProcessingTaskStatus.QUEUED)
    repository.add(task)
    recorder = _recorder(repository)

    recorder.mark_running("celery-live")
    assert repository.tasks[task.id].status is ProcessingTaskStatus.RUNNING
    assert repository.tasks[task.id].started_at == _CLOCK

    recorder.mark_succeeded("celery-live", {"created_lexemes": 4})
    stored = repository.tasks[task.id]
    assert stored.status is ProcessingTaskStatus.SUCCEEDED
    assert stored.result == {"created_lexemes": 4}
    assert stored.finished_at == _CLOCK


def test_status_recorder_marks_failed_with_a_trimmed_message() -> None:
    repository = MemoryProcessingTaskRepository()
    task = _tracked(ProcessingTaskStatus.RUNNING)
    repository.add(task)

    _recorder(repository).mark_failed("celery-live", "x" * 5000)

    stored = repository.tasks[task.id]
    assert stored.status is ProcessingTaskStatus.FAILED
    assert stored.error is not None and len(stored.error) == 2000


def test_status_recorder_ignores_unknown_and_terminal_tasks() -> None:
    repository = MemoryProcessingTaskRepository()
    done = _tracked(ProcessingTaskStatus.SUCCEEDED)
    repository.add(done)
    recorder = _recorder(repository)

    recorder.mark_running("no-such-task")  # untracked -> no-op
    recorder.mark_failed("celery-live", "late failure")  # already terminal -> no-op

    assert repository.tasks[done.id].status is ProcessingTaskStatus.SUCCEEDED
