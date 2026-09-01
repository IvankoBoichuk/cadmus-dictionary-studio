"""HTTP adapters for monitoring and retrying a dictionary's async jobs."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.access import Permission
from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.processing import (
    ProcessingTask,
    ProcessingTaskKind,
    ProcessingTaskKindNotRetryableError,
    ProcessingTaskNotFoundError,
    ProcessingTaskNotRetryableError,
    ProcessingTaskService,
    ProcessingTaskStatus,
)
from cadmus.sources import DictionaryAccessError
from cadmus.sources.application import GetDictionaryService
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

SESSION_COOKIE_NAME = "cadmus_session"


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class ProcessingTaskResponse(BaseModel):
    """One recorded background-job run for a dictionary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    dictionary_id: UUID
    kind: ProcessingTaskKind
    status: ProcessingTaskStatus
    target_id: UUID | None
    target_label: str | None
    error: str | None
    result: dict[str, object] | None
    retry_of_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


UNAUTHORIZED_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "The browser has no valid session",
    }
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "The dictionary or task does not exist for this caller",
    }
}


def _task_response(task: ProcessingTask) -> ProcessingTaskResponse:
    return ProcessingTaskResponse(
        id=task.id,
        dictionary_id=task.dictionary_id,
        kind=task.kind,
        status=task.status,
        target_id=task.target_id,
        target_label=task.target_label,
        error=task.error,
        result=task.result,
        retry_of_id=task.retry_of_id,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        updated_at=task.updated_at,
    )


def create_processing_tasks_router(
    authentication_service: AuthenticationService,
    get_dictionary_service: GetDictionaryService,
    processing_task_service: ProcessingTaskService,
) -> APIRouter:
    """Create the per-dictionary task monitor routes."""
    router = APIRouter(
        prefix="/dictionaries/{dictionary_id}/tasks", tags=["processing tasks"]
    )

    def current_user(
        session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    ) -> User:
        if session_token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "invalid_session", "message": "Потрібна авторизація."},
            )
        try:
            return authentication_service.authenticate(session_token)
        except AuthenticationError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": error.reason, "message": "Потрібна авторизація."},
            ) from error

    AuthenticatedUser = Annotated[User, Depends(current_user)]

    def _not_found(
        message: str = "Словник або задачу не знайдено.",  # noqa: RUF001
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"code": "not_found", "message": message},
        )

    @router.get(
        "",
        response_model=list[ProcessingTaskResponse],
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="List recorded async jobs for a dictionary, newest first",
    )
    def list_tasks(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        kind: Annotated[list[ProcessingTaskKind] | None, Query()] = None,
        task_status: Annotated[
            list[ProcessingTaskStatus] | None, Query(alias="status")
        ] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> list[ProcessingTaskResponse] | JSONResponse:
        try:
            get_dictionary_service.get(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found("Словник не знайдено.")
        tasks = processing_task_service.list_for_dictionary(
            dictionary_id, kinds=kind, statuses=task_status, limit=limit
        )
        return [_task_response(task) for task in tasks]

    @router.post(
        "/{task_id}/retry",
        response_model=ProcessingTaskResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": ErrorResponse,
                "description": "The task has not failed, or its kind cannot be retried",
            },
        },
        summary="Re-run a failed job as a new tracked task",
    )
    def retry_task(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        task_id: Annotated[UUID, Path()],
    ) -> ProcessingTaskResponse | JSONResponse:
        try:
            get_dictionary_service.get(
                dictionary_id, user.id, required_permission=Permission.EDIT
            )
        except DictionaryAccessError:
            return _not_found("Словник не знайдено.")
        try:
            existing = processing_task_service.get(task_id)
        except ProcessingTaskNotFoundError:
            return _not_found("Задачу не знайдено.")
        if existing.dictionary_id != dictionary_id:
            return _not_found("Задачу не знайдено.")
        try:
            created = processing_task_service.retry(task_id, actor_id=user.id)
        except ProcessingTaskNotRetryableError:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "code": "not_retryable",
                    "message": "Перезапустити можна лише невдалу задачу.",
                },
            )
        except ProcessingTaskKindNotRetryableError:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "code": "kind_not_retryable",
                    "message": "Цей тип задачі не підтримує перезапуск.",
                },
            )
        return _task_response(created)

    return router
