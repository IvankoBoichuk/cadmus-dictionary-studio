"""Application-owned ports for the processing-task registry."""

from collections.abc import Callable, Sequence
from types import TracebackType
from typing import Protocol, Self
from uuid import UUID

from cadmus.processing.domain import (
    ProcessingTask,
    ProcessingTaskKind,
    ProcessingTaskStatus,
)


class ProcessingTaskRepository(Protocol):
    """Persistence for recorded background-job runs."""

    def add(self, task: ProcessingTask) -> None: ...

    def get(self, task_id: UUID) -> ProcessingTask | None: ...

    def get_by_celery_id(self, celery_task_id: str) -> ProcessingTask | None: ...

    def list_for_dictionary(
        self,
        dictionary_id: UUID,
        *,
        kinds: Sequence[ProcessingTaskKind] | None = None,
        statuses: Sequence[ProcessingTaskStatus] | None = None,
        limit: int = 100,
    ) -> list[ProcessingTask]: ...

    def update(self, task: ProcessingTask) -> None: ...

    def prune_dictionary(self, dictionary_id: UUID, *, keep: int) -> None:
        """Delete all but the ``keep`` newest rows for one dictionary."""
        ...


class ProcessingTaskUnitOfWork(Protocol):
    """Transaction boundary owned by one processing-task use case."""

    @property
    def processing_tasks(self) -> ProcessingTaskRepository: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...


type ProcessingTaskUnitOfWorkFactory = Callable[[], ProcessingTaskUnitOfWork]

# Given a failed task and the id of the user asking for the retry, put the
# same logical operation back on its queue and return the new Celery id.
type TaskReenqueuer = Callable[[ProcessingTask, UUID], str]
