"""Thin HTTP adapters for the BH-53 dictionary page-viewer use cases."""

from tempfile import SpooledTemporaryFile
from typing import Annotated, BinaryIO, cast
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.sources import (
    DictionaryAccessError,
    GetDictionaryService,
    ObjectNotFoundError,
    ObjectStorage,
)
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict

from cadmus_api.routes.dictionaries import iter_and_close, page_image_content_type

SESSION_COOKIE_NAME = "cadmus_session"
_PAGE_IMAGE_SPOOL_MAX_BYTES = 8 * 1024 * 1024


class DictionaryPagesSummaryResponse(BaseModel):
    """AC2: how many pages fall within the dictionary's saved ranges."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_pages: int


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


def create_pages_router(
    authentication_service: AuthenticationService,
    get_service: GetDictionaryService,
    object_storage: ObjectStorage,
) -> APIRouter:
    """Create BH-53 page-viewer routes bound to application use cases."""
    router = APIRouter(prefix="/dictionaries/{dictionary_id}/pages", tags=["pages"])

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

    @router.get(
        "",
        response_model=DictionaryPagesSummaryResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Read the total number of viewable pages (AC2, AC4)",
    )
    def get_summary(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> DictionaryPagesSummaryResponse | JSONResponse:
        try:
            total_pages = get_service.count_viewable_pages(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        return DictionaryPagesSummaryResponse(total_pages=total_pages)

    @router.get(
        "/{page_number}",
        response_model=None,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Stream one rendered page image by its 1-based position (AC1, AC4)",
    )
    def get_page(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        page_number: Annotated[int, Path(ge=1)],
    ) -> StreamingResponse | JSONResponse:
        try:
            page = get_service.get_viewable_page(dictionary_id, user.id, page_number)
        except DictionaryAccessError:
            return _not_found()
        if page is None:
            return _not_found()

        buffer: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
            max_size=_PAGE_IMAGE_SPOOL_MAX_BYTES
        )
        try:
            object_storage.download(page.processed_asset_key, cast(BinaryIO, buffer))
        except ObjectNotFoundError:
            buffer.close()
            return _not_found()
        buffer.seek(0)

        return StreamingResponse(
            iter_and_close(buffer),
            media_type=page_image_content_type(page.processed_asset_key),
            headers={"Cache-Control": "private, max-age=86400"},
        )

    return router
