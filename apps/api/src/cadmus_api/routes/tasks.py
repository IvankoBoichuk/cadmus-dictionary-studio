"""HTTP adapter for the infrastructure test task."""

from typing import Annotated, Any

from cadmus.processing import (
    TaskQueue,
    TaskQueueUnavailableError,
    TaskStatus,
)
from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field


class TestTaskRequest(BaseModel):
    """Bounded input for the deterministic test task."""

    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=200)


class EnqueuedTaskResponse(BaseModel):
    """Stable response returned after a task is accepted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: TaskStatus


class TaskStatusResponse(BaseModel):
    """Stable response for task progress and result polling."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: TaskStatus
    result: dict[str, str] | None = None
    error: str | None = None


class QueueUnavailableResponse(BaseModel):
    """Stable response when Redis cannot serve queue operations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detail: str


QUEUE_UNAVAILABLE_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": QueueUnavailableResponse,
        "description": "The Redis task queue is unavailable",
    }
}


def create_tasks_router(task_queue: TaskQueue) -> APIRouter:
    """Create task routes bound to an application-owned queue port."""
    router = APIRouter(prefix="/tasks", tags=["tasks"])

    @router.post(
        "/test",
        response_model=EnqueuedTaskResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=QUEUE_UNAVAILABLE_RESPONSE,
        summary="Enqueue the infrastructure test task",
    )
    async def enqueue_test_task(request: TestTaskRequest) -> EnqueuedTaskResponse:
        try:
            task_id = task_queue.enqueue_test_task(request.value)
        except TaskQueueUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Task queue is unavailable",
            ) from error
        return EnqueuedTaskResponse(task_id=task_id, status=TaskStatus.QUEUED)

    @router.get(
        "/test/{task_id}",
        response_model=TaskStatusResponse,
        response_model_exclude_none=True,
        responses=QUEUE_UNAVAILABLE_RESPONSE,
        summary="Read test task status and result",
    )
    async def get_test_task(
        task_id: Annotated[str, Path(min_length=1, max_length=128)],
    ) -> TaskStatusResponse:
        try:
            snapshot = task_queue.get_task(task_id)
        except TaskQueueUnavailableError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Task queue is unavailable",
            ) from error
        return TaskStatusResponse(
            task_id=snapshot.task_id,
            status=snapshot.status,
            result=snapshot.result,
            error=snapshot.error,
        )

    return router
