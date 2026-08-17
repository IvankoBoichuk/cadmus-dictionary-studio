"""Thin HTTP adapters for the BH-28 dictionary page-range use cases."""

from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.sources import (
    DictionaryAccessError,
    DictionaryPageRange,
    GetDictionaryService,
    PageRangeInput,
    PageRangesUnavailableError,
    PageRangeValidationError,
    SavePageRangesService,
)
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

SESSION_COOKIE_NAME = "cadmus_session"


class PageRangeRequest(BaseModel):
    """One BH-28 page range as submitted by the client (AC2)."""

    model_config = ConfigDict(extra="forbid")

    start_page: int = Field(ge=1)
    end_page: int = Field(ge=1)


class SavePageRangesRequest(BaseModel):
    """The full replacement set of page ranges for a dictionary (AC3, AC7)."""

    model_config = ConfigDict(extra="forbid")

    ranges: list[PageRangeRequest] = Field(default_factory=list, max_length=200)


class PageRangeResponse(BaseModel):
    """One persisted, normalized BH-28 page range."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_page: int
    end_page: int


class PageRangesResponse(BaseModel):
    """The dictionary's page ranges alongside the PDF's total page count (AC1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_count: int | None
    ranges: list[PageRangeResponse]
    merged: bool = False


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class FieldErrorsResponse(BaseModel):
    """Validation errors addressable by ``ranges.<index>.<field>`` (AC4, AC5)."""

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
        "description": "The dictionary does not exist or is not owned by the caller",
    }
}


def _page_ranges_response(
    page_count: int | None,
    ranges: list[DictionaryPageRange],
    *,
    merged: bool = False,
) -> PageRangesResponse:
    return PageRangesResponse(
        page_count=page_count,
        ranges=[
            PageRangeResponse(start_page=r.start_page, end_page=r.end_page)
            for r in sorted(ranges, key=lambda r: r.position)
        ],
        merged=merged,
    )


def create_page_ranges_router(
    authentication_service: AuthenticationService,
    get_service: GetDictionaryService,
    save_service: SavePageRangesService,
) -> APIRouter:
    """Create BH-28 page-range routes bound to application use cases."""
    router = APIRouter(
        prefix="/dictionaries/{dictionary_id}/page-ranges", tags=["page-ranges"]
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

    @router.get(
        "",
        response_model=PageRangesResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Read a dictionary's page ranges and its PDF page count (AC1)",
    )
    def get_page_ranges(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> PageRangesResponse | JSONResponse:
        try:
            get_service.get(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        source_file = None
        try:
            source_file = get_service.get_source_file(dictionary_id, user.id)
        except DictionaryAccessError:
            source_file = None
        ranges = get_service.get_page_ranges(dictionary_id, user.id)
        page_count = source_file.page_count if source_file is not None else None
        return _page_ranges_response(page_count, ranges)

    @router.put(
        "",
        response_model=PageRangesResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "One or more ranges are out of bounds or inverted, "
                "or the PDF's page count is not known yet",
            },
        },
        summary="Replace a dictionary's page ranges (AC3, AC6, AC7, AC8)",
    )
    def save_page_ranges(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        request: SavePageRangesRequest,
    ) -> PageRangesResponse | JSONResponse:
        inputs = [
            PageRangeInput(start_page=r.start_page, end_page=r.end_page)
            for r in request.ranges
        ]
        try:
            outcome = save_service.save(dictionary_id, user.id, inputs)
        except PageRangeValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except PageRangesUnavailableError:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={
                    "errors": {
                        "ranges": "PDF ще не завантажено чи не пройшло перевірку."
                    }
                },
            )
        except DictionaryAccessError:
            return _not_found()
        source_file = None
        try:
            source_file = get_service.get_source_file(dictionary_id, user.id)
        except DictionaryAccessError:
            source_file = None
        page_count = source_file.page_count if source_file is not None else None
        return _page_ranges_response(page_count, outcome.ranges, merged=outcome.merged)

    return router
