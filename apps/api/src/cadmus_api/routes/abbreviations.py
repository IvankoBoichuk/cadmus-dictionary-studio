"""Thin HTTP adapters for the BH-29 dictionary abbreviation use cases."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.sources import (
    Abbreviation,
    AbbreviationAccessError,
    AbbreviationCategory,
    AbbreviationCrudService,
    AbbreviationImportService,
    AbbreviationInput,
    AbbreviationValidationError,
    DictionaryAccessError,
    DuplicateAbbreviationError,
    ImportFormat,
    UnparsableImportFileError,
    export_abbreviations_csv,
    export_abbreviations_json,
)
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

SESSION_COOKIE_NAME = "cadmus_session"
_IMPORT_SPOOL_MAX_BYTES = 4 * 1024 * 1024


class AbbreviationRequest(BaseModel):
    """One BH-29 abbreviation submission (AC1, AC2)."""

    model_config = ConfigDict(extra="forbid")

    abbreviation: str = Field(min_length=1, max_length=64)
    category: AbbreviationCategory
    full_form: str | None = Field(default=None, max_length=512)
    language_code: str | None = Field(default=None, max_length=2)
    note: str | None = Field(default=None, max_length=2000)
    unresolved: bool = False
    variants: list[str] = Field(default_factory=list, max_length=50)


class AbbreviationResponse(BaseModel):
    """One persisted BH-29 abbreviation entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    abbreviation: str
    category: AbbreviationCategory
    full_form: str | None
    language_code: str | None
    note: str | None
    unresolved: bool
    variants: list[str]
    created_at: datetime
    updated_at: datetime


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class FieldErrorsResponse(BaseModel):
    """Validation errors addressable by form field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    errors: dict[str, str]


class DuplicateAbbreviationResponse(BaseModel):
    """Structured duplicate warning for AC4."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = "duplicate_abbreviation"
    abbreviation_id: UUID
    message: str


class ImportRowResponse(BaseModel):
    """One previewed or committed import row (AC5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row_number: int
    valid: bool
    input: AbbreviationRequest | None
    errors: dict[str, str]
    duplicate_of: UUID | None = None


class ImportPreviewResponse(BaseModel):
    """A parsed-and-validated import file, not yet persisted (AC5)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows: list[ImportRowResponse]
    valid_count: int
    error_count: int


class ImportCommitRequest(BaseModel):
    """The rows the client kept from a preview, to actually persist (AC6)."""

    model_config = ConfigDict(extra="forbid")

    rows: list[AbbreviationRequest] = Field(max_length=5000)


class ImportSkippedRowResponse(BaseModel):
    """One row that a commit could not persist, with the reason (AC6)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row_number: int
    errors: dict[str, str]


class ImportCommitResponse(BaseModel):
    """What a commit actually persisted vs. skipped (AC6)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    imported: list[AbbreviationResponse]
    skipped: list[ImportSkippedRowResponse]


UNAUTHORIZED_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "The browser has no valid session",
    }
}
NOT_FOUND_RESPONSE: dict[int | str, dict[str, object]] = {
    status.HTTP_404_NOT_FOUND: {
        "model": ErrorResponse,
        "description": "The dictionary or abbreviation does not exist or is not owned "
        "by the caller",
    }
}


def _abbreviation_response(abbreviation: Abbreviation) -> AbbreviationResponse:
    return AbbreviationResponse(
        id=abbreviation.id,
        abbreviation=abbreviation.abbreviation,
        category=abbreviation.category,
        full_form=abbreviation.full_form,
        language_code=abbreviation.language_code,
        note=abbreviation.note,
        unresolved=abbreviation.unresolved,
        variants=[variant.variant_text for variant in abbreviation.variants],
        created_at=abbreviation.created_at,
        updated_at=abbreviation.updated_at,
    )


def _to_input(request: AbbreviationRequest) -> AbbreviationInput:
    return AbbreviationInput(
        abbreviation=request.abbreviation,
        category=request.category,
        full_form=request.full_form,
        language_code=request.language_code,
        note=request.note,
        unresolved=request.unresolved,
        variants=tuple(request.variants),
    )


def _duplicate_response(error: DuplicateAbbreviationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=DuplicateAbbreviationResponse(
            abbreviation_id=error.existing_id,
            message="Таке скорочення вже існує в цьому словнику.",
        ).model_dump(mode="json"),
    )


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"code": "not_found", "message": "Словник чи скорочення не знайдено."},
    )


def create_abbreviations_router(
    authentication_service: AuthenticationService,
    crud_service: AbbreviationCrudService,
    import_service: AbbreviationImportService,
) -> APIRouter:
    """Create BH-29 abbreviation routes bound to application use cases."""
    router = APIRouter(
        prefix="/dictionaries/{dictionary_id}/abbreviations", tags=["abbreviations"]
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
        response_model=list[AbbreviationResponse],
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="List every abbreviation configured for a dictionary",
    )
    def list_abbreviations(
        user: AuthenticatedUser, dictionary_id: Annotated[UUID, Path()]
    ) -> list[AbbreviationResponse] | JSONResponse:
        try:
            abbreviations = crud_service.list_for_dictionary(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        return [_abbreviation_response(item) for item in abbreviations]

    @router.post(
        "",
        response_model=AbbreviationResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": DuplicateAbbreviationResponse,
                "description": "An abbreviation with this key already exists",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "Abbreviation fields are invalid",
            },
        },
        summary="Add an abbreviation to a dictionary",
    )
    def create_abbreviation(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        request: AbbreviationRequest,
    ) -> AbbreviationResponse | JSONResponse:
        try:
            abbreviation = crud_service.create(
                dictionary_id, user.id, _to_input(request)
            )
        except AbbreviationValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except DuplicateAbbreviationError as error:
            return _duplicate_response(error)
        except DictionaryAccessError:
            return _not_found()
        return _abbreviation_response(abbreviation)

    @router.patch(
        "/{abbreviation_id}",
        response_model=AbbreviationResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": DuplicateAbbreviationResponse,
                "description": "An abbreviation with this key already exists",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "Abbreviation fields are invalid",
            },
        },
        summary="Edit an existing abbreviation (AC3)",
    )
    def update_abbreviation(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        abbreviation_id: Annotated[UUID, Path()],
        request: AbbreviationRequest,
    ) -> AbbreviationResponse | JSONResponse:
        try:
            abbreviation = crud_service.update(
                dictionary_id, abbreviation_id, user.id, _to_input(request)
            )
        except AbbreviationValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except DuplicateAbbreviationError as error:
            return _duplicate_response(error)
        except (DictionaryAccessError, AbbreviationAccessError):
            return _not_found()
        return _abbreviation_response(abbreviation)

    @router.delete(
        "/{abbreviation_id}",
        response_model=None,
        status_code=status.HTTP_204_NO_CONTENT,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Delete an abbreviation (AC3)",
    )
    def delete_abbreviation(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        abbreviation_id: Annotated[UUID, Path()],
    ) -> Response | JSONResponse:
        try:
            crud_service.delete(dictionary_id, abbreviation_id, user.id)
        except (DictionaryAccessError, AbbreviationAccessError):
            return _not_found()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/import/preview",
        response_model=ImportPreviewResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": ErrorResponse,
                "description": "The file is not well-formed CSV or JSON",
            },
        },
        summary="Parse and validate a bulk import file without saving it (AC5)",
    )
    def preview_import(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        file: Annotated[UploadFile, File()],
    ) -> ImportPreviewResponse | JSONResponse:
        filename = (file.filename or "").lower()
        is_json = filename.endswith(".json") or file.content_type == "application/json"
        import_format: ImportFormat = "json" if is_json else "csv"
        raw = file.file.read(_IMPORT_SPOOL_MAX_BYTES + 1)
        if len(raw) > _IMPORT_SPOOL_MAX_BYTES:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={
                    "code": "import_too_large",
                    "message": "Файл імпорту завеликий.",
                },
            )
        try:
            results = import_service.preview(dictionary_id, user.id, raw, import_format)
        except UnparsableImportFileError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={
                    "code": "unparsable_import_file",
                    "message": f"Файл не вдалося розібрати: {error}",
                },
            )
        except DictionaryAccessError:
            return _not_found()

        rows = [
            ImportRowResponse(
                row_number=result.row_number,
                valid=result.input is not None
                and not result.errors
                and result.duplicate_of is None,
                input=AbbreviationRequest(
                    abbreviation=result.input.abbreviation,
                    category=result.input.category,
                    full_form=result.input.full_form,
                    language_code=result.input.language_code,
                    note=result.input.note,
                    unresolved=result.input.unresolved,
                    variants=list(result.input.variants),
                )
                if result.input is not None
                else None,
                errors=result.errors,
                duplicate_of=result.duplicate_of,
            )
            for result in results
        ]
        return ImportPreviewResponse(
            rows=rows,
            valid_count=sum(1 for row in rows if row.valid),
            error_count=sum(1 for row in rows if not row.valid),
        )

    @router.post(
        "/import/commit",
        response_model=ImportCommitResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Persist the rows kept from a preview (AC5, AC6)",
    )
    def commit_import(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        request: ImportCommitRequest,
    ) -> ImportCommitResponse | JSONResponse:
        try:
            outcome = import_service.commit(
                dictionary_id,
                user.id,
                [_to_input(row) for row in request.rows],
            )
        except DictionaryAccessError:
            return _not_found()
        return ImportCommitResponse(
            imported=[_abbreviation_response(item) for item in outcome.imported],
            skipped=[
                ImportSkippedRowResponse(
                    row_number=result.row_number, errors=result.errors
                )
                for result in outcome.skipped
            ],
        )

    @router.get(
        "/export",
        response_model=None,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Export a dictionary's abbreviations as JSON or CSV (AC9)",
    )
    def export_abbreviations(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        export_format: Annotated[str, Query(alias="format", pattern="^(json|csv)$")] = (
            "json"
        ),
    ) -> Response | JSONResponse:
        try:
            abbreviations = crud_service.list_for_dictionary(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()

        if export_format == "csv":
            body = export_abbreviations_csv(abbreviations)
            media_type = "text/csv"
            filename = "abbreviations.csv"
        else:
            body = export_abbreviations_json(abbreviations)
            media_type = "application/json"
            filename = "abbreviations.json"
        return Response(
            content=body,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router
