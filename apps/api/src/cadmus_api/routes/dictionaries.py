"""Thin HTTP adapters for the dictionary draft (BH-26 + BH-27) use cases."""

import re
from collections.abc import Generator
from datetime import datetime
from tempfile import SpooledTemporaryFile
from typing import Annotated, BinaryIO, cast
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.sources import (
    ContributorInput,
    ContributorRole,
    DeleteDictionaryService,
    Dictionary,
    DictionaryAccessError,
    DictionaryNotReadyError,
    DictionaryPageRange,
    DictionaryReadinessService,
    DictionaryStatus,
    DuplicateSourceError,
    GetDictionaryService,
    InspectionStatus,
    InvalidUploadError,
    LegalStatus,
    MetadataInput,
    MetadataValidationError,
    ObjectNotFoundError,
    ObjectStorage,
    PagesStatus,
    ReadinessBlocker,
    SaveDictionaryMetadataService,
    SourceFile,
    UploadDictionaryService,
    UploadTooLargeError,
    missing_required_fields,
    readiness_blockers,
)
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    HTTPException,
    Path,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

SESSION_COOKIE_NAME = "cadmus_session"
_DOWNLOAD_SPOOL_MAX_BYTES = 64 * 1024 * 1024
_THUMBNAIL_SPOOL_MAX_BYTES = 8 * 1024 * 1024
_UNSAFE_FILENAME_CHARS = re.compile(r'[\r\n"]')

_PAGE_IMAGE_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
}


def page_image_content_type(storage_key: str) -> str:
    """Derive a rendered page's media type from its stored file extension.

    Pages are currently rendered as PNG (ADR-0006's pipeline), but BH-53's
    Acceptance Criteria describe them as ``.jpg``; staying extension-driven
    here serves either without a route change or forcing a re-render of
    already-processed pages.
    """
    extension = storage_key.rsplit(".", 1)[-1].lower() if "." in storage_key else ""
    return _PAGE_IMAGE_CONTENT_TYPES.get(extension, "image/png")


class ContributorRequest(BaseModel):
    """One ordered contributor entry as submitted by the client."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    role: ContributorRole


class SaveMetadataRequest(BaseModel):
    """Full BH-27 metadata submission; missing required fields are allowed."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=512)
    description: str | None = Field(default=None, max_length=10_000)
    dictionary_type: str | None = Field(default=None, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    publication_year: int | None = None
    edition: str | None = Field(default=None, max_length=255)
    isbn: str | None = Field(default=None, max_length=32)
    digital_source: str | None = Field(default=None, max_length=500)
    legal_status: LegalStatus | None = None
    license_type: str | None = Field(default=None, max_length=255)
    permission_reference: str | None = Field(default=None, max_length=500)
    rights_note: str | None = Field(default=None, max_length=10_000)
    contributors: list[ContributorRequest] = Field(default_factory=list, max_length=50)
    language_codes: list[str] = Field(default_factory=list, max_length=50)


class ContributorResponse(BaseModel):
    """One ordered contributor entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    role: ContributorRole
    position: int


class SourceFileResponse(BaseModel):
    """Technical facts about the uploaded PDF and its inspection state."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    original_filename: str
    mime_type: str
    byte_size: int
    page_count: int | None
    checksum_sha256: str
    uploaded_at: datetime
    inspection_status: InspectionStatus
    inspection_error: str | None = None
    pages_status: PagesStatus
    pages_error: str | None = None


class ReadinessBlockerResponse(BaseModel):
    """One reason a draft cannot yet become ``configured`` (BH-31 AC3, AC4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class DictionaryResponse(BaseModel):
    """The dictionary draft, its structured metadata, and readiness gaps."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    status: DictionaryStatus
    title: str | None
    description: str | None
    dictionary_type: str | None
    publisher: str | None
    publication_year: int | None
    edition: str | None
    isbn: str | None
    digital_source: str | None
    legal_status: LegalStatus | None
    license_type: str | None
    permission_reference: str | None
    rights_note: str | None
    contributors: list[ContributorResponse]
    language_codes: list[str]
    created_at: datetime
    updated_at: datetime
    missing_required_fields: list[str]
    readiness_blockers: list[ReadinessBlockerResponse]
    source: SourceFileResponse | None = None


class ReadinessBlockersResponse(BaseModel):
    """AC6: structured reasons a ``configure`` request was rejected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blockers: list[ReadinessBlockerResponse]


class ErrorResponse(BaseModel):
    """Stable, non-sensitive error contract for a single failure reason."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class FieldErrorsResponse(BaseModel):
    """Validation errors addressable by form field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    errors: dict[str, str]


class DuplicateSourceResponse(BaseModel):
    """Structured duplicate-checksum warning; never discloses other users."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = "duplicate_source"
    dictionary_id: UUID
    title: str | None
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


def _source_file_response(source_file: SourceFile | None) -> SourceFileResponse | None:
    if source_file is None:
        return None
    return SourceFileResponse(
        original_filename=source_file.original_filename,
        mime_type=source_file.mime_type,
        byte_size=source_file.byte_size,
        page_count=source_file.page_count,
        checksum_sha256=source_file.checksum_sha256,
        uploaded_at=source_file.uploaded_at,
        inspection_status=source_file.inspection_status,
        inspection_error=source_file.inspection_error,
        pages_status=source_file.pages_status,
        pages_error=source_file.pages_error,
    )


def _readiness_blocker_responses(
    blockers: list[ReadinessBlocker],
) -> list[ReadinessBlockerResponse]:
    return [
        ReadinessBlockerResponse(code=blocker.code, message=blocker.message)
        for blocker in blockers
    ]


def _dictionary_response(
    dictionary: Dictionary,
    missing_required_fields: list[str],
    source_file: SourceFile | None = None,
    page_ranges: list[DictionaryPageRange] | None = None,
) -> DictionaryResponse:
    return DictionaryResponse(
        id=dictionary.id,
        status=dictionary.status,
        title=dictionary.title,
        description=dictionary.description,
        dictionary_type=dictionary.dictionary_type,
        publisher=dictionary.publisher,
        publication_year=dictionary.publication_year,
        edition=dictionary.edition,
        isbn=dictionary.isbn,
        digital_source=dictionary.digital_source,
        legal_status=dictionary.legal_status,
        license_type=dictionary.license_type,
        permission_reference=dictionary.permission_reference,
        rights_note=dictionary.rights_note,
        contributors=[
            ContributorResponse(
                name=contributor.name,
                role=contributor.role,
                position=contributor.position,
            )
            for contributor in dictionary.contributors
        ],
        language_codes=[language.language_code for language in dictionary.languages],
        created_at=dictionary.created_at,
        updated_at=dictionary.updated_at,
        missing_required_fields=missing_required_fields,
        readiness_blockers=_readiness_blocker_responses(
            readiness_blockers(dictionary, source_file, page_ranges)
        ),
        source=_source_file_response(source_file),
    )


def _sanitize_filename(filename: str) -> str:
    return _UNSAFE_FILENAME_CHARS.sub("", filename) or "dictionary.pdf"


def iter_and_close(
    buffer: "SpooledTemporaryFile[bytes]",
) -> Generator[bytes, None, None]:
    try:
        while True:
            chunk = buffer.read(1024 * 1024)
            if not chunk:
                return
            yield chunk
    finally:
        buffer.close()


def create_dictionaries_router(
    authentication_service: AuthenticationService,
    upload_service: UploadDictionaryService,
    metadata_service: SaveDictionaryMetadataService,
    get_service: GetDictionaryService,
    object_storage: ObjectStorage,
    delete_service: DeleteDictionaryService,
    readiness_service: DictionaryReadinessService,
) -> APIRouter:
    """Create dictionary draft routes bound to application use cases."""
    router = APIRouter(prefix="/dictionaries", tags=["dictionaries"])

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

    def _page_ranges_or_empty(
        dictionary_id: UUID, actor_id: UUID
    ) -> list[DictionaryPageRange]:
        try:
            return get_service.get_page_ranges(dictionary_id, actor_id)
        except DictionaryAccessError:
            return []

    @router.post(
        "/upload",
        response_model=DictionaryResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={
            **UNAUTHORIZED_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": DuplicateSourceResponse,
                "description": "A source with this checksum already exists",
            },
            status.HTTP_413_CONTENT_TOO_LARGE: {
                "model": ErrorResponse,
                "description": "The upload exceeds the configured maximum size",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The file failed type or signature validation",
            },
        },
        summary="Upload a dictionary source PDF and create its draft",
    )
    def upload(
        user: AuthenticatedUser,
        file: Annotated[UploadFile, File()],
    ) -> DictionaryResponse | JSONResponse:
        if file.content_type is None:
            content_type = ""
        else:
            content_type = file.content_type
        try:
            outcome = upload_service.upload(
                user.id,
                file.filename or "",
                content_type,
                file.file,
            )
        except InvalidUploadError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": {error.field: error.message}},
            )
        except UploadTooLargeError as error:
            return JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={
                    "code": "upload_too_large",
                    "message": (
                        "Файл перевищує максимальний розмір "
                        f"{error.max_size_bytes} байт."
                    ),
                },
            )
        except DuplicateSourceError as error:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=DuplicateSourceResponse(
                    dictionary_id=error.dictionary_id,
                    title=error.title,
                    message="Такий файл уже завантажено раніше.",
                ).model_dump(mode="json"),
            )
        return _dictionary_response(
            outcome.dictionary,
            outcome.missing_required_fields,
            outcome.source_file,
            [],
        )

    @router.get(
        "",
        response_model=list[DictionaryResponse],
        responses={**UNAUTHORIZED_RESPONSE},
        summary="List every dictionary draft owned by the caller",
    )
    def list_dictionaries(user: AuthenticatedUser) -> list[DictionaryResponse]:
        return [
            _dictionary_response(
                entry.dictionary,
                missing_required_fields(entry.dictionary),
                entry.source_file,
                entry.page_ranges,
            )
            for entry in get_service.list_for_owner(user.id)
        ]

    @router.delete(
        "/{dictionary_id}",
        response_model=None,
        status_code=status.HTTP_204_NO_CONTENT,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Delete a dictionary draft and its stored files",
    )
    def delete_dictionary(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> Response | JSONResponse:
        try:
            delete_service.delete(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get(
        "/{dictionary_id}",
        response_model=DictionaryResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Read a dictionary draft and its readiness gaps",
    )
    def get_dictionary(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> DictionaryResponse | JSONResponse:
        try:
            dictionary = get_service.get(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        source_file = None
        try:
            source_file = get_service.get_source_file(dictionary_id, user.id)
        except DictionaryAccessError:
            source_file = None
        return _dictionary_response(
            dictionary,
            missing_required_fields(dictionary),
            source_file,
            _page_ranges_or_empty(dictionary_id, user.id),
        )

    @router.patch(
        "/{dictionary_id}",
        response_model=DictionaryResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "Metadata fields are invalid",
            },
        },
        summary="Save bibliographic, language, and legal metadata for a draft",
    )
    def save_metadata(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        request: SaveMetadataRequest,
    ) -> DictionaryResponse | JSONResponse:
        data = MetadataInput(
            title=request.title,
            description=request.description,
            dictionary_type=request.dictionary_type,
            publisher=request.publisher,
            publication_year=request.publication_year,
            edition=request.edition,
            isbn=request.isbn,
            digital_source=request.digital_source,
            legal_status=request.legal_status,
            license_type=request.license_type,
            permission_reference=request.permission_reference,
            rights_note=request.rights_note,
            contributors=tuple(
                ContributorInput(name=contributor.name, role=contributor.role)
                for contributor in request.contributors
            ),
            language_codes=tuple(request.language_codes),
        )
        try:
            outcome = metadata_service.save(dictionary_id, user.id, data)
        except MetadataValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except DictionaryAccessError:
            return _not_found()
        source_file = None
        try:
            source_file = get_service.get_source_file(dictionary_id, user.id)
        except DictionaryAccessError:
            source_file = None
        return _dictionary_response(
            outcome.dictionary,
            outcome.missing_required_fields,
            source_file,
            _page_ranges_or_empty(dictionary_id, user.id),
        )

    @router.post(
        "/{dictionary_id}/configure",
        response_model=DictionaryResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": ReadinessBlockersResponse,
                "description": "The draft is not ready to become configured",
            },
        },
        summary="Confirm readiness and mark a draft as configured (BH-31 AC5, AC6)",
    )
    def configure_dictionary(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> DictionaryResponse | JSONResponse:
        try:
            dictionary = readiness_service.confirm_configured(dictionary_id, user.id)
        except DictionaryNotReadyError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content=ReadinessBlockersResponse(
                    blockers=_readiness_blocker_responses(error.blockers)
                ).model_dump(mode="json"),
            )
        except DictionaryAccessError:
            return _not_found()
        source_file = None
        try:
            source_file = get_service.get_source_file(dictionary_id, user.id)
        except DictionaryAccessError:
            source_file = None
        return _dictionary_response(
            dictionary,
            missing_required_fields(dictionary),
            source_file,
            _page_ranges_or_empty(dictionary_id, user.id),
        )

    @router.get(
        "/{dictionary_id}/source/download",
        response_model=None,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Download the immutable original source PDF",
    )
    def download_source(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> StreamingResponse | JSONResponse:
        try:
            source_file = get_service.get_source_file(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()

        buffer: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
            max_size=_DOWNLOAD_SPOOL_MAX_BYTES
        )
        try:
            object_storage.download(source_file.storage_key, cast(BinaryIO, buffer))
        except ObjectNotFoundError:
            buffer.close()
            return _not_found()
        buffer.seek(0)

        filename = _sanitize_filename(source_file.original_filename)
        return StreamingResponse(
            iter_and_close(buffer),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @router.get(
        "/{dictionary_id}/thumbnail",
        response_model=None,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Stream the first rendered page as a thumbnail image",
    )
    def get_thumbnail(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> StreamingResponse | JSONResponse:
        try:
            page = get_service.get_first_page(dictionary_id, user.id)
        except DictionaryAccessError:
            return _not_found()
        if page is None:
            return _not_found()

        buffer: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
            max_size=_THUMBNAIL_SPOOL_MAX_BYTES
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

    def _not_found() -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "code": "not_found",
                "message": "Словник не знайдено.",
            },
        )

    return router
