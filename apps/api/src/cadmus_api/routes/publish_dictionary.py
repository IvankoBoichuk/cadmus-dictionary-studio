"""Thin HTTP adapter for releasing a fully processed dictionary."""

from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.sources import (
    DictionaryAccessError,
    DictionaryNotProcessedError,
    DictionaryStatus,
    PublishDictionaryService,
)
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

SESSION_COOKIE_NAME = "cadmus_session"


class PublishDictionaryResponse(BaseModel):
    """The dictionary's id and its status after publishing."""

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


def create_publish_dictionary_router(
    authentication_service: AuthenticationService,
    publish_dictionary_service: PublishDictionaryService,
) -> APIRouter:
    """Create the publish route bound to its application use case."""
    router = APIRouter(prefix="/dictionaries/{dictionary_id}", tags=["dictionaries"])

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
        "/publish",
        response_model=PublishDictionaryResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": ErrorResponse,
                "description": "The dictionary is not fully processed yet",
            },
        },
        summary="Publish a dictionary once every lexeme and entry is complete",
    )
    def publish_dictionary(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> PublishDictionaryResponse | JSONResponse:
        try:
            dictionary = publish_dictionary_service.publish(dictionary_id, user.id)
        except DictionaryAccessError:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"code": "not_found", "message": "Словник не знайдено."},
            )
        except DictionaryNotProcessedError:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={
                    "code": "not_processed",
                    "message": "Спершу завершіть опрацювання всіх лексем та статей.",
                },
            )
        return PublishDictionaryResponse(id=dictionary.id, status=dictionary.status)

    return router
