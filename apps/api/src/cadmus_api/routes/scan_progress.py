"""Thin HTTP adapters for the BH-57 dictionary scan-progress use case."""

from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import LexemeAccessError, ScanProgress, ScanProgressService
from cadmus.sources import DictionaryStatus
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

SESSION_COOKIE_NAME = "cadmus_session"


class PageProgressResponse(BaseModel):
    """One page's scan status: does it have at least one lexeme (AC1)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    page_number: int
    has_lexemes: bool


class ScanProgressResponse(BaseModel):
    """AC2: aggregate scan progress alongside each page's status, plus
    lexeme- and entry-level completion and the current dictionary status
    (kept in sync with that completion)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: DictionaryStatus
    total_pages: int
    processed_pages: int
    pages: list[PageProgressResponse]
    total_lexemes: int
    completed_lexemes: int
    total_entries: int
    completed_entries: int


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


def _scan_progress_response(progress: ScanProgress) -> ScanProgressResponse:
    return ScanProgressResponse(
        status=progress.status,
        total_pages=progress.total_pages,
        processed_pages=progress.processed_pages,
        pages=[
            PageProgressResponse(
                page_number=page.page_number, has_lexemes=page.has_lexemes
            )
            for page in progress.pages
        ],
        total_lexemes=progress.total_lexemes,
        completed_lexemes=progress.completed_lexemes,
        total_entries=progress.total_entries,
        completed_entries=progress.completed_entries,
    )


def create_scan_progress_router(
    authentication_service: AuthenticationService,
    scan_progress_service: ScanProgressService,
) -> APIRouter:
    """Create the BH-57 scan-progress route bound to its application use case."""
    router = APIRouter(
        prefix="/dictionaries/{dictionary_id}/scan-progress", tags=["scan-progress"]
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

    @router.get(
        "",
        response_model=ScanProgressResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Read a dictionary's scan progress (AC1, AC2)",
    )
    def get_scan_progress(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> ScanProgressResponse | JSONResponse:
        try:
            progress = scan_progress_service.get_progress(dictionary_id, user.id)
        except LexemeAccessError:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"code": "not_found", "message": "Словник не знайдено."},
            )
        return _scan_progress_response(progress)

    return router
