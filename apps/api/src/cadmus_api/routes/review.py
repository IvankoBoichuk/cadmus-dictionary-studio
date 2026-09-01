"""Thin HTTP adapters for the cross-dictionary review-queue use cases."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import EntryAccessError, EntryStatus, EntryValidationError
from cadmus.review import (
    EntryNotAwaitingReviewError,
    ReviewAccessError,
    ReviewService,
)
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

SESSION_COOKIE_NAME = "cadmus_session"


class ReviewQueueItemResponse(BaseModel):
    """One entry awaiting review, across every dictionary the caller reviews."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: UUID
    dictionary_id: UUID
    dictionary_title: str | None
    headword: str
    status: EntryStatus
    field_count: int
    updated_at: datetime


class ReviewDecisionRequest(BaseModel):
    """An optional note the reviewer leaves with an approve / send-back."""

    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=2000)


class ReviewDecisionResponse(BaseModel):
    """The entry's new status after a reviewer decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: UUID
    status: EntryStatus


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class FieldErrorsResponse(BaseModel):
    """Validation errors addressable by form field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    errors: dict[str, str]


UNAUTHORIZED_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "The browser has no valid session",
    }
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "The entry does not exist or the caller may not review it",
    }
}


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"code": "not_found", "message": "Статтю не знайдено."},
    )


def create_review_router(
    authentication_service: AuthenticationService,
    review_service: ReviewService,
) -> APIRouter:
    """Create the ``/review`` queue routes bound to the review use cases."""
    router = APIRouter(prefix="/review", tags=["review"])

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

    @router.get(
        "/queue",
        response_model=list[ReviewQueueItemResponse],
        responses={**UNAUTHORIZED_RESPONSE},
        summary="List every entry awaiting review across the caller's dictionaries",
    )
    def list_queue(
        user: AuthenticatedUser,
    ) -> list[ReviewQueueItemResponse]:
        return [
            ReviewQueueItemResponse(
                entry_id=item.entry_id,
                dictionary_id=item.dictionary_id,
                dictionary_title=item.dictionary_title,
                headword=item.headword,
                status=item.status,
                field_count=item.field_count,
                updated_at=item.updated_at,
            )
            for item in review_service.list_queue(user.id)
        ]

    @router.post(
        "/entries/{entry_id}/approve",
        response_model=ReviewDecisionResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": ErrorResponse,
                "description": "The entry is not awaiting review",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The entry does not yet satisfy its article schema",
            },
        },
        summary="Approve an entry: ready_to_review -> complete",
    )
    def approve_entry(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
        request: ReviewDecisionRequest | None = None,
    ) -> ReviewDecisionResponse | JSONResponse:
        note = request.note if request is not None else None
        try:
            entry = review_service.approve(entry_id, user.id, note)
        except EntryValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except EntryNotAwaitingReviewError:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "code": "not_awaiting_review",
                    "message": "Статтю вже переглянуто чи ще не подано на перевірку.",
                },
            )
        except (ReviewAccessError, EntryAccessError):
            return _not_found()
        return ReviewDecisionResponse(entry_id=entry.id, status=entry.status)

    @router.post(
        "/entries/{entry_id}/send-back",
        response_model=ReviewDecisionResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": ErrorResponse,
                "description": "The entry is not awaiting review",
            },
        },
        summary="Send an entry back to its editor: ready_to_review -> draft",
    )
    def send_back_entry(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
        request: ReviewDecisionRequest | None = None,
    ) -> ReviewDecisionResponse | JSONResponse:
        note = request.note if request is not None else None
        try:
            entry = review_service.send_back(entry_id, user.id, note)
        except EntryNotAwaitingReviewError:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "code": "not_awaiting_review",
                    "message": "Статтю вже переглянуто чи ще не подано на перевірку.",
                },
            )
        except (ReviewAccessError, EntryAccessError):
            return _not_found()
        return ReviewDecisionResponse(entry_id=entry.id, status=entry.status)

    return router
