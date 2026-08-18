"""Thin HTTP adapter for the BH-58 finish-scanning-stage use case."""

from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import (
    DictionaryNotReadyToScanError,
    FinishScanningService,
    LexemeAccessError,
)
from cadmus.sources import DictionaryStatus
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

SESSION_COOKIE_NAME = "cadmus_session"


class FinishScanningResponse(BaseModel):
    """The dictionary's id and its status after finishing scanning (AC3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    status: DictionaryStatus


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
        "description": "The dictionary does not exist or is not owned by the caller",
    }
}


def create_finish_scanning_router(
    authentication_service: AuthenticationService,
    finish_scanning_service: FinishScanningService,
) -> APIRouter:
    """Create the BH-58 finish-scanning route bound to its application use case."""
    router = APIRouter(prefix="/dictionaries/{dictionary_id}", tags=["scan-progress"])

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

    @router.post(
        "/finish-scanning",
        response_model=FinishScanningResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": ErrorResponse,
                "description": "The dictionary has no lexemes yet",
            },
        },
        summary="Finish the scanning stage once at least one lexeme exists (AC1-AC3)",
    )
    def finish_scanning(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> FinishScanningResponse | JSONResponse:
        try:
            dictionary = finish_scanning_service.finish(dictionary_id, user.id)
        except LexemeAccessError:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"code": "not_found", "message": "Словник не знайдено."},
            )
        except DictionaryNotReadyToScanError:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={
                    "code": "no_lexemes",
                    "message": "Словник ще не має жодної виділеної лексеми.",
                },
            )
        return FinishScanningResponse(id=dictionary.id, status=dictionary.status)

    return router
