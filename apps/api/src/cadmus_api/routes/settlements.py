"""Thin HTTP adapters for the BH-30 dictionary settlement mapping use cases."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.sources import (
    DictionaryAccessError,
    DictionarySettlementMapping,
    DuplicateSettlementMappingError,
    ImportFormat,
    SettlementConfirmationService,
    SettlementMappingAccessError,
    SettlementMappingCrudService,
    SettlementMappingImportService,
    SettlementMappingInput,
    SettlementMappingStatus,
    SettlementMappingValidationError,
    SettlementSearchService,
    SettlementSuggestion,
    UnparsableImportFileError,
    export_settlement_mappings_csv,
    export_settlement_mappings_json,
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


class SettlementMappingRequest(BaseModel):
    """One BH-30 settlement mapping submission (AC7, AC11, AC12).

    Deliberately has no ``status`` field: create/update can only ever
    produce ``unresolved``/``suggested`` mappings (AC9) -- the only way to
    reach ``confirmed`` is the dedicated confirm endpoint below.
    """

    model_config = ConfigDict(extra="forbid")

    source_label: str = Field(min_length=1, max_length=512)
    source_note: str | None = Field(default=None, max_length=2000)
    modern_settlement_name: str | None = Field(default=None, max_length=255)
    settlement_category: str | None = Field(default=None, max_length=64)
    settlement_id: UUID | None = None


class SettlementMappingResponse(BaseModel):
    """One persisted BH-30 settlement mapping entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    source_label: str
    status: SettlementMappingStatus
    source_note: str | None
    modern_settlement_name: str | None
    settlement_category: str | None
    area_id: UUID | None
    region_id: UUID | None
    community_id: UUID | None
    settlement_id: UUID | None
    community_geometry_id: UUID | None
    area_name: str | None
    region_name: str | None
    community_name: str | None
    external_community_id: str | None
    katottg: str | None
    koatuu: str | None
    confirmed_by: UUID | None
    confirmed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SettlementSuggestionResponse(BaseModel):
    """One AC8 search result: a settlement flattened with its hierarchy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    settlement_id: UUID
    title: str
    category: str
    community_id: UUID
    community_name: str
    region_id: UUID
    area_id: UUID


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class FieldErrorsResponse(BaseModel):
    """Validation errors addressable by form field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    errors: dict[str, str]


class DuplicateSettlementMappingResponse(BaseModel):
    """Structured duplicate warning."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = "duplicate_settlement_mapping"
    mapping_id: UUID
    message: str


class ImportRowResponse(BaseModel):
    """One previewed or committed import row."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row_number: int
    valid: bool
    input: SettlementMappingRequest | None
    errors: dict[str, str]
    duplicate_of: UUID | None = None


class ImportPreviewResponse(BaseModel):
    """A parsed-and-validated import file, not yet persisted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rows: list[ImportRowResponse]
    valid_count: int
    error_count: int


class ImportCommitRequest(BaseModel):
    """The rows the client kept from a preview, to actually persist."""

    model_config = ConfigDict(extra="forbid")

    rows: list[SettlementMappingRequest] = Field(max_length=5000)


class ImportSkippedRowResponse(BaseModel):
    """One row that a commit could not persist, with the reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    row_number: int
    errors: dict[str, str]


class ImportCommitResponse(BaseModel):
    """What a commit actually persisted vs. skipped."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    imported: list[SettlementMappingResponse]
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
        "description": "The dictionary or settlement mapping does not exist or is "
        "not owned by the caller",
    }
}


def _mapping_response(
    mapping: DictionarySettlementMapping,
) -> SettlementMappingResponse:
    return SettlementMappingResponse(
        id=mapping.id,
        source_label=mapping.source_label,
        status=mapping.status,
        source_note=mapping.source_note,
        modern_settlement_name=mapping.modern_settlement_name,
        settlement_category=mapping.settlement_category,
        area_id=mapping.area_id,
        region_id=mapping.region_id,
        community_id=mapping.community_id,
        settlement_id=mapping.settlement_id,
        community_geometry_id=mapping.community_geometry_id,
        area_name=mapping.area_name,
        region_name=mapping.region_name,
        community_name=mapping.community_name,
        external_community_id=mapping.external_community_id,
        katottg=mapping.katottg,
        koatuu=mapping.koatuu,
        confirmed_by=mapping.confirmed_by,
        confirmed_at=mapping.confirmed_at,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


def _suggestion_response(
    suggestion: SettlementSuggestion,
) -> SettlementSuggestionResponse:
    return SettlementSuggestionResponse(
        settlement_id=suggestion.settlement_id,
        title=suggestion.title,
        category=suggestion.category,
        community_id=suggestion.community_id,
        community_name=suggestion.community_name,
        region_id=suggestion.region_id,
        area_id=suggestion.area_id,
    )


def _to_input(
    request: SettlementMappingRequest, *, status_: SettlementMappingStatus
) -> SettlementMappingInput:
    return SettlementMappingInput(
        source_label=request.source_label,
        source_note=request.source_note,
        modern_settlement_name=request.modern_settlement_name,
        settlement_category=request.settlement_category,
        settlement_id=request.settlement_id,
        status=status_,
    )


def _duplicate_response(error: DuplicateSettlementMappingError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=DuplicateSettlementMappingResponse(
            mapping_id=error.existing_id,
            message="Така географічна позначка вже існує в цьому словнику.",
        ).model_dump(mode="json"),
    )


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "code": "not_found",
            "message": "Словник чи географічну позначку не знайдено.",
        },
    )


def create_settlements_router(
    authentication_service: AuthenticationService,
    mapping_crud_service: SettlementMappingCrudService,
    search_service: SettlementSearchService,
    confirmation_service: SettlementConfirmationService,
    import_service: SettlementMappingImportService,
) -> APIRouter:
    """Create BH-30 settlement mapping routes bound to application use cases."""
    router = APIRouter(
        prefix="/dictionaries/{dictionary_id}/settlements", tags=["settlements"]
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
        response_model=list[SettlementMappingResponse],
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="List every settlement mapping configured for a dictionary",
    )
    def list_mappings(
        user: AuthenticatedUser, dictionary_id: Annotated[UUID, Path()]
    ) -> list[SettlementMappingResponse] | JSONResponse:
        try:
            mappings = mapping_crud_service.list_for_dictionary(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        return [_mapping_response(item) for item in mappings]

    @router.post(
        "",
        response_model=SettlementMappingResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": DuplicateSettlementMappingResponse,
                "description": "A mapping with this source label already exists",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "Settlement mapping fields are invalid",
            },
        },
        summary="Add a geographic label to a dictionary (AC7)",
    )
    def create_mapping(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        request: SettlementMappingRequest,
    ) -> SettlementMappingResponse | JSONResponse:
        status_ = (
            SettlementMappingStatus.SUGGESTED
            if request.settlement_id is not None
            else SettlementMappingStatus.UNRESOLVED
        )
        try:
            mapping = mapping_crud_service.create(
                dictionary_id, user.id, _to_input(request, status_=status_)
            )
        except SettlementMappingValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except DuplicateSettlementMappingError as error:
            return _duplicate_response(error)
        except DictionaryAccessError:
            return _not_found()
        return _mapping_response(mapping)

    @router.patch(
        "/{mapping_id}",
        response_model=SettlementMappingResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": DuplicateSettlementMappingResponse,
                "description": "A mapping with this source label already exists",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "Settlement mapping fields are invalid",
            },
        },
        summary="Edit an existing settlement mapping (AC12)",
    )
    def update_mapping(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        mapping_id: Annotated[UUID, Path()],
        request: SettlementMappingRequest,
    ) -> SettlementMappingResponse | JSONResponse:
        status_ = (
            SettlementMappingStatus.SUGGESTED
            if request.settlement_id is not None
            else SettlementMappingStatus.UNRESOLVED
        )
        try:
            mapping = mapping_crud_service.update(
                dictionary_id,
                mapping_id,
                user.id,
                _to_input(request, status_=status_),
            )
        except SettlementMappingValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except DuplicateSettlementMappingError as error:
            return _duplicate_response(error)
        except (DictionaryAccessError, SettlementMappingAccessError):
            return _not_found()
        return _mapping_response(mapping)

    @router.delete(
        "/{mapping_id}",
        response_model=None,
        status_code=status.HTTP_204_NO_CONTENT,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Delete a settlement mapping (AC12)",
    )
    def delete_mapping(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        mapping_id: Annotated[UUID, Path()],
    ) -> Response | JSONResponse:
        try:
            mapping_crud_service.delete(dictionary_id, mapping_id, user.id)
        except (DictionaryAccessError, SettlementMappingAccessError):
            return _not_found()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/{mapping_id}/confirm",
        response_model=SettlementMappingResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The mapping has no linked settlement, or it no "
                "longer exists in the reference data",
            },
        },
        summary="Confirm a mapping against its linked modern settlement (AC10)",
    )
    def confirm_mapping(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        mapping_id: Annotated[UUID, Path()],
    ) -> SettlementMappingResponse | JSONResponse:
        try:
            mapping = confirmation_service.confirm(dictionary_id, mapping_id, user.id)
        except SettlementMappingValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except (DictionaryAccessError, SettlementMappingAccessError):
            return _not_found()
        return _mapping_response(mapping)

    @router.post(
        "/{mapping_id}/unconfirm",
        response_model=SettlementMappingResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Revert a confirmed mapping back to unresolved (AC12)",
    )
    def unconfirm_mapping(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        mapping_id: Annotated[UUID, Path()],
    ) -> SettlementMappingResponse | JSONResponse:
        try:
            mapping = mapping_crud_service.unconfirm(dictionary_id, mapping_id, user.id)
        except (DictionaryAccessError, SettlementMappingAccessError):
            return _not_found()
        return _mapping_response(mapping)

    @router.get(
        "/search",
        response_model=list[SettlementSuggestionResponse],
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Search the local settlement cache for a modern equivalent (AC8)",
    )
    def search_settlements(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        query: Annotated[str | None, Query()] = None,
        area_id: Annotated[UUID | None, Query()] = None,
        region_id: Annotated[UUID | None, Query()] = None,
        community_id: Annotated[UUID | None, Query()] = None,
        category: Annotated[str | None, Query()] = None,
    ) -> list[SettlementSuggestionResponse] | JSONResponse:
        try:
            # Ownership check only; the caller must be the dictionary's owner
            # even though the reference data itself is shared/public.
            mapping_crud_service.list_for_dictionary(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        results = search_service.search(
            query=query,
            area_id=area_id,
            region_id=region_id,
            community_id=community_id,
            category=category,
        )
        return [_suggestion_response(item) for item in results]

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
        summary="Parse and validate a bulk import file without saving it",
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
                input=SettlementMappingRequest(
                    source_label=result.input.source_label,
                    source_note=result.input.source_note,
                    modern_settlement_name=result.input.modern_settlement_name,
                    settlement_category=result.input.settlement_category,
                    settlement_id=result.input.settlement_id,
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
        summary="Persist the rows kept from a preview",
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
                [
                    _to_input(row, status_=SettlementMappingStatus.UNRESOLVED)
                    for row in request.rows
                ],
            )
        except DictionaryAccessError:
            return _not_found()
        return ImportCommitResponse(
            imported=[_mapping_response(item) for item in outcome.imported],
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
        summary="Export a dictionary's settlement mappings as JSON or CSV",
    )
    def export_mappings(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        export_format: Annotated[str, Query(alias="format", pattern="^(json|csv)$")] = (
            "json"
        ),
    ) -> Response | JSONResponse:
        try:
            mappings = mapping_crud_service.list_for_dictionary(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()

        if export_format == "csv":
            body = export_settlement_mappings_csv(mappings)
            media_type = "text/csv"
            filename = "settlements.csv"
        else:
            body = export_settlement_mappings_json(mappings)
            media_type = "application/json"
            filename = "settlements.json"
        return Response(
            content=body,
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router
