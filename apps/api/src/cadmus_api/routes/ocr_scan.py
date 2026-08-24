"""Thin HTTP adapters for queuing OCR across every unscanned page of a
dictionary, creating draft lexemes directly (no manual accept step).
"""

from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import (
    LexemeAccessError,
    OcrSuggestionStatus,
    QueueDictionaryScanService,
)
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

SESSION_COOKIE_NAME = "cadmus_session"


class EnqueueDictionaryScanResponse(BaseModel):
    """AC: accepted response for a newly queued whole-dictionary OCR scan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: OcrSuggestionStatus = OcrSuggestionStatus.QUEUED


class DictionaryScanTaskResponse(BaseModel):
    """Poll response: how far the scan queue has gotten."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: OcrSuggestionStatus
    processed_pages: int
    total_pages: int
    created_lexemes: int
    error: str | None = None


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


UNAUTHORIZED_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "The browser has no valid session",
    }
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "The dictionary does not exist, or the caller does not own it",
    }
}


def create_ocr_scan_router(
    authentication_service: AuthenticationService,
    scan_service: QueueDictionaryScanService,
) -> APIRouter:
    """Create whole-dictionary OCR scan routes bound to their use case."""
    router = APIRouter(
        prefix="/dictionaries/{dictionary_id}/ocr-scan",
        tags=["ocr-scan"],
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

    def _not_found() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"code": "not_found", "message": "Словник не знайдено."},
        )

    @router.post(
        "",
        response_model=EnqueueDictionaryScanResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Queue OCR across every unscanned page of a dictionary",
    )
    def enqueue_scan(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> EnqueueDictionaryScanResponse | JSONResponse:
        try:
            task_id = scan_service.enqueue(dictionary_id, user.id)
        except LexemeAccessError:
            return _not_found()
        return EnqueueDictionaryScanResponse(task_id=task_id)

    @router.get(
        "/{task_id}",
        response_model=DictionaryScanTaskResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Poll a whole-dictionary OCR scan task's status and progress",
    )
    def get_scan_task(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        task_id: Annotated[str, Path(min_length=1, max_length=128)],
    ) -> DictionaryScanTaskResponse | JSONResponse:
        try:
            snapshot = scan_service.get_task(dictionary_id, user.id, task_id)
        except LexemeAccessError:
            return _not_found()
        return DictionaryScanTaskResponse(
            task_id=snapshot.task_id,
            status=snapshot.status,
            processed_pages=snapshot.processed_pages,
            total_pages=snapshot.total_pages,
            created_lexemes=snapshot.created_lexemes,
            error=snapshot.error,
        )

    return router
