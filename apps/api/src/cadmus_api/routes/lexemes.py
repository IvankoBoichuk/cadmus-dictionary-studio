"""Thin HTTP adapters for the BH-54 manual lexeme-selection use cases."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import (
    CreateLexemeService,
    DeleteLexemeService,
    DuplicateLexemeError,
    Lexeme,
    LexemeAccessError,
    LexemeInput,
    LexemeNotEditableError,
    LexemeNotFoundError,
    LexemeOrigin,
    LexemePageNotFoundError,
    LexemeQueryService,
    LexemeStatus,
    LexemeValidationError,
    UpdateLexemeInput,
    UpdateLexemeService,
)
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

SESSION_COOKIE_NAME = "cadmus_session"


class CreateLexemeRequest(BaseModel):
    """One BH-54 lexeme submission (AC1, AC2, AC3).

    ``origin`` defaults to ``manual`` (BH-54's hand-drawn flow); accepting
    an OCR suggestion sends ``origin="ocr"`` instead, so the resulting
    ``Lexeme`` records where its text and box actually came from.
    """

    model_config = ConfigDict(extra="forbid")

    source_text: str = Field(min_length=1, max_length=500)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    confirm_duplicate: bool = False
    origin: LexemeOrigin = LexemeOrigin.MANUAL
    x2: float | None = Field(default=None, ge=0)
    y2: float | None = Field(default=None, ge=0)
    width2: float | None = Field(default=None, gt=0)
    height2: float | None = Field(default=None, gt=0)


class LexemeResponse(BaseModel):
    """One persisted BH-54 lexeme."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    dictionary_id: UUID
    page_id: UUID
    source_text: str
    x: float
    y: float
    width: float
    height: float
    origin: LexemeOrigin
    status: LexemeStatus
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    updated_by: UUID
    x2: float | None = None
    y2: float | None = None
    width2: float | None = None
    height2: float | None = None


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class FieldErrorsResponse(BaseModel):
    """Validation errors addressable by form field (AC1, AC2, AC3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    errors: dict[str, str]


class UpdateLexemeRequest(BaseModel):
    """One BH-56 lexeme edit submission: full replacement text and box."""

    model_config = ConfigDict(extra="forbid")

    source_text: str = Field(min_length=1, max_length=500)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    x2: float | None = Field(default=None, ge=0)
    y2: float | None = Field(default=None, ge=0)
    width2: float | None = Field(default=None, gt=0)
    height2: float | None = Field(default=None, gt=0)
    status: LexemeStatus | None = None


class DuplicateLexemeResponse(BaseModel):
    """AC6: a heavily overlapping lexeme already exists; resubmit to confirm."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = "duplicate_lexeme"
    existing_lexeme_id: UUID
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
LEXEME_NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "The dictionary, or the lexeme within it, does not exist",
    }
}
LEXEME_LOCKED_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_409_CONFLICT: {
        "model": ErrorResponse,
        "description": "The lexeme is 'complete' and can no longer be edited",
    }
}


def _lexeme_response(lexeme: Lexeme) -> LexemeResponse:
    return LexemeResponse(
        id=lexeme.id,
        dictionary_id=lexeme.dictionary_id,
        page_id=lexeme.page_id,
        source_text=lexeme.source_text,
        x=lexeme.x,
        y=lexeme.y,
        width=lexeme.width,
        height=lexeme.height,
        origin=lexeme.origin,
        status=lexeme.status,
        created_at=lexeme.created_at,
        created_by=lexeme.created_by,
        updated_at=lexeme.updated_at,
        updated_by=lexeme.updated_by,
        x2=lexeme.x2,
        y2=lexeme.y2,
        width2=lexeme.width2,
        height2=lexeme.height2,
    )


def create_lexemes_router(
    authentication_service: AuthenticationService,
    create_service: CreateLexemeService,
    query_service: LexemeQueryService,
) -> APIRouter:
    """Create BH-54 lexeme routes bound to application use cases."""
    router = APIRouter(
        prefix="/dictionaries/{dictionary_id}/pages/{page_number}/lexemes",
        tags=["lexemes"],
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

    @router.get(
        "",
        response_model=list[LexemeResponse],
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="List the lexemes manually selected on one page (AC7)",
    )
    def list_lexemes(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        page_number: Annotated[int, Path(ge=1)],
    ) -> list[LexemeResponse] | JSONResponse:
        try:
            lexemes = query_service.list_for_page(dictionary_id, user.id, page_number)
        except (LexemeAccessError, LexemePageNotFoundError):
            return _not_found()
        return [_lexeme_response(lexeme) for lexeme in lexemes]

    @router.post(
        "",
        response_model=LexemeResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": DuplicateLexemeResponse,
                "description": (
                    "A heavily overlapping lexeme already exists on this page"
                ),
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The text or bounding box failed validation",
            },
        },
        summary="Manually select a lexeme on a page (AC1-AC6)",
    )
    def create_lexeme(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        page_number: Annotated[int, Path(ge=1)],
        request: CreateLexemeRequest,
    ) -> LexemeResponse | JSONResponse:
        data = LexemeInput(
            page_number=page_number,
            source_text=request.source_text,
            x=request.x,
            y=request.y,
            width=request.width,
            height=request.height,
            confirm_duplicate=request.confirm_duplicate,
            origin=request.origin,
            x2=request.x2,
            y2=request.y2,
            width2=request.width2,
            height2=request.height2,
        )
        try:
            lexeme = create_service.create(dictionary_id, user.id, data)
        except (LexemeAccessError, LexemePageNotFoundError):
            return _not_found()
        except LexemeValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except DuplicateLexemeError as error:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=DuplicateLexemeResponse(
                    existing_lexeme_id=error.existing_id,
                    message=(
                        "Схожа лексема вже виділена на цій сторінці. "
                        "Підтвердіть, щоб зберегти все одно."
                    ),
                ).model_dump(mode="json"),
            )
        return _lexeme_response(lexeme)

    return router


def create_lexeme_management_router(
    authentication_service: AuthenticationService,
    update_service: UpdateLexemeService,
    delete_service: DeleteLexemeService,
) -> APIRouter:
    """Create BH-56 lexeme edit/delete routes bound to application use cases."""
    router = APIRouter(prefix="/dictionaries/{dictionary_id}/lexemes", tags=["lexemes"])

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
            content={"code": "not_found", "message": "Лексему не знайдено."},
        )

    def _locked() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "code": "lexeme_not_editable",
                "message": "Лексема завершена, редагування заблоковане.",
            },
        )

    @router.patch(
        "/{lexeme_id}",
        response_model=LexemeResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **LEXEME_NOT_FOUND_RESPONSE,
            **LEXEME_LOCKED_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The text or bounding box failed validation",
            },
        },
        summary="Edit a lexeme's text, bounding box, and/or status (BH-56, BH-113)",
    )
    def update_lexeme(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        lexeme_id: Annotated[UUID, Path()],
        request: UpdateLexemeRequest,
    ) -> LexemeResponse | JSONResponse:
        data = UpdateLexemeInput(
            source_text=request.source_text,
            x=request.x,
            y=request.y,
            width=request.width,
            height=request.height,
            x2=request.x2,
            y2=request.y2,
            width2=request.width2,
            height2=request.height2,
            status=request.status,
        )
        try:
            lexeme = update_service.update(dictionary_id, lexeme_id, user.id, data)
        except (LexemeAccessError, LexemeNotFoundError, LexemePageNotFoundError):
            return _not_found()
        except LexemeNotEditableError:
            return _locked()
        except LexemeValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        return _lexeme_response(lexeme)

    @router.delete(
        "/{lexeme_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_model=None,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **LEXEME_NOT_FOUND_RESPONSE,
            **LEXEME_LOCKED_RESPONSE,
        },
        summary="Delete a lexeme (BH-56)",
    )
    def delete_lexeme(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        lexeme_id: Annotated[UUID, Path()],
    ) -> Response | JSONResponse:
        try:
            delete_service.delete(dictionary_id, lexeme_id, user.id)
        except (LexemeAccessError, LexemeNotFoundError):
            return _not_found()
        except LexemeNotEditableError:
            return _locked()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
