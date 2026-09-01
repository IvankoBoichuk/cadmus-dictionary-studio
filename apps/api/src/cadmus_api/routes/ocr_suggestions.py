"""Thin HTTP adapters for OCR (ALTO) word-suggestion use cases."""

from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import (
    LexemeAccessError,
    LexemePageNotFoundError,
    OcrSuggestionStatus,
    SuggestLexemesService,
)
from cadmus.processing import ProcessingTaskKind, ProcessingTaskService
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from cadmus_api.processing_recording import record_enqueued_task

SESSION_COOKIE_NAME = "cadmus_session"


class EnqueueSuggestionsResponse(BaseModel):
    """AC: accepted response for a newly queued OCR suggestion job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: OcrSuggestionStatus = OcrSuggestionStatus.QUEUED


class LexemeSuggestionResponse(BaseModel):
    """One OCR word candidate, not yet a lexeme."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float


class SuggestionsTaskResponse(BaseModel):
    """Poll response: task status plus suggestions once succeeded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: OcrSuggestionStatus
    suggestions: list[LexemeSuggestionResponse] | None = None
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
        "description": (
            "The dictionary, or the requested page within it, does not exist"
        ),
    }
}


def create_ocr_suggestions_router(
    authentication_service: AuthenticationService,
    suggest_service: SuggestLexemesService,
    processing_task_service: ProcessingTaskService | None = None,
) -> APIRouter:
    """Create OCR word-suggestion routes bound to their application use case."""
    router = APIRouter(
        prefix="/dictionaries/{dictionary_id}/pages/{page_number}/ocr-suggestions",
        tags=["ocr-suggestions"],
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
            content={"code": "not_found", "message": "Сторінку не знайдено."},
        )

    @router.post(
        "",
        response_model=EnqueueSuggestionsResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Enqueue OCR word suggestions for one page",
    )
    def enqueue_suggestions(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        page_number: Annotated[int, Path(ge=1)],
    ) -> EnqueueSuggestionsResponse | JSONResponse:
        try:
            task_id = suggest_service.enqueue(dictionary_id, user.id, page_number)
        except (LexemeAccessError, LexemePageNotFoundError):
            return _not_found()
        record_enqueued_task(
            processing_task_service,
            dictionary_id=dictionary_id,
            kind=ProcessingTaskKind.OCR_SUGGESTIONS,
            celery_task_id=task_id,
            enqueued_by=user.id,
            target_label=f"Сторінка {page_number}",
            rerun_params={"page_number": page_number},
        )
        return EnqueueSuggestionsResponse(task_id=task_id)

    @router.get(
        "/{task_id}",
        response_model=SuggestionsTaskResponse,
        response_model_exclude_none=True,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Poll an OCR suggestion task's status and result",
    )
    def get_suggestions_task(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        page_number: Annotated[int, Path(ge=1)],
        task_id: Annotated[str, Path(min_length=1, max_length=128)],
    ) -> SuggestionsTaskResponse | JSONResponse:
        try:
            snapshot = suggest_service.get_task(
                dictionary_id, user.id, page_number, task_id
            )
        except (LexemeAccessError, LexemePageNotFoundError):
            return _not_found()
        return SuggestionsTaskResponse(
            task_id=snapshot.task_id,
            status=snapshot.status,
            suggestions=(
                [
                    LexemeSuggestionResponse(
                        source_text=s.source_text,
                        x=s.x,
                        y=s.y,
                        width=s.width,
                        height=s.height,
                        confidence=s.confidence,
                    )
                    for s in snapshot.suggestions
                ]
                if snapshot.suggestions is not None
                else None
            ),
            error=snapshot.error,
        )

    return router
