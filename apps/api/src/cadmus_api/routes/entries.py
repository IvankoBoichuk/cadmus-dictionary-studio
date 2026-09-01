"""Thin HTTP adapters for the BH-148 dictionary entry / structured-field use cases."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import (
    CreateEntryFieldService,
    DeleteEntryFieldService,
    DictionaryEntry,
    DuplicateEntryError,
    EntryAccessError,
    EntryField,
    EntryFieldAccessError,
    EntryFieldOrigin,
    EntryFieldRole,
    EntryFieldValidationError,
    EntryFragment,
    EntryQueryService,
    EntryStatus,
    EntryValidationError,
    LexemeAccessError,
    LexemeNotFoundError,
    OcrSuggestionStatus,
    PromoteLexemeToEntryService,
    QueueEntryFieldExtractionService,
    RenderEntryService,
    UpdateEntryFieldService,
    ValidateEntryService,
)
from cadmus.processing import ProcessingTaskKind, ProcessingTaskService
from cadmus.sources import GetDictionaryService
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from cadmus_api.processing_recording import record_enqueued_task

SESSION_COOKIE_NAME = "cadmus_session"


class EntryFragmentResponse(BaseModel):
    """The physical location of one part of an entry on one page."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    page_id: UUID
    page_number: int | None
    x: float
    y: float
    width: float
    height: float
    x2: float | None
    y2: float | None
    width2: float | None
    height2: float | None
    reading_order: int
    recognized_text: str


class EntryFieldResponse(BaseModel):
    """One structured field extracted (or manually added) from an entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    fragment_id: UUID
    parent_field_id: UUID | None
    field_path: str
    role: EntryFieldRole
    position: int
    source_text: str
    source_start: int | None
    source_end: int | None
    x: float | None
    y: float | None
    width: float | None
    height: float | None
    normalized_text: str | None
    confidence: float | None
    origin: EntryFieldOrigin
    created_at: datetime
    updated_at: datetime


class EntryResponse(BaseModel):
    """A dictionary entry, its source fragments, and its structured fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    dictionary_id: UUID
    lexeme_id: UUID
    headword: str
    status: EntryStatus
    schema_id: UUID | None
    created_at: datetime
    updated_at: datetime
    fragments: list[EntryFragmentResponse]
    fields: list[EntryFieldResponse]


class EntrySummaryResponse(BaseModel):
    """One row of a dictionary's entries list (BH-148)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    headword: str
    status: EntryStatus
    field_count: int
    created_at: datetime
    updated_at: datetime


class EnqueueExtractionResponse(BaseModel):
    """Accepted response for a newly queued field-extraction job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: OcrSuggestionStatus = OcrSuggestionStatus.QUEUED


class ExtractionTaskResponse(BaseModel):
    """Poll response: task status plus how many fields it created."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: OcrSuggestionStatus
    created_fields: int = 0
    error: str | None = None


class EntryRenderResponse(BaseModel):
    """The entry rendered to Markdown via its schema's presentation formula.

    ``markdown`` is ``None`` when it could not be produced; ``reason`` then says
    why (``"no_schema"``, ``"no_formula"`` or ``"template_error"``) and
    ``error`` carries the template message for the last case. This is a preview,
    so every one of those is a 200, not an error status.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    markdown: str | None
    reason: str | None = None
    error: str | None = None


class CreateEntryFieldRequest(BaseModel):
    """A manually added field an automatic pass missed."""

    model_config = ConfigDict(extra="forbid")

    fragment_id: UUID
    field_path: str = Field(min_length=1, max_length=255)
    role: EntryFieldRole
    source_text: str = Field(min_length=1, max_length=10_000)
    source_start: int = Field(ge=0)
    source_end: int = Field(ge=0)
    parent_field_id: UUID | None = None
    normalized_text: str | None = Field(default=None, max_length=10_000)


class UpdateEntryFieldRequest(BaseModel):
    """An edit to an existing field; always flips its origin to manual."""

    model_config = ConfigDict(extra="forbid")

    role: EntryFieldRole | None = None
    source_text: str | None = Field(default=None, max_length=10_000)
    normalized_text: str | None = Field(default=None, max_length=10_000)


class DuplicateEntryResponse(BaseModel):
    """Structured duplicate warning: this lexeme was already promoted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = "duplicate_entry"
    entry_id: UUID
    message: str


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
        "description": "The dictionary, lexeme, entry, or field does not exist or is "
        "not owned by the caller",
    }
}


def _page_numbers(
    dictionary_service: GetDictionaryService,
    dictionary_id: UUID,
    actor_id: UUID,
) -> dict[UUID, int]:
    """Map each viewable page's id to its 1-based viewer ordinal.

    Fragments store ``page_id``, but the page-image route (and
    ``dictionaryPageImageUrl`` on the frontend) addresses pages by their
    position within the dictionary's saved viewable ranges, not by id --
    this bridges the two so the UI can render a crop of the source scan.
    """
    pages = dictionary_service.list_viewable_pages(dictionary_id, actor_id)
    return {page.id: ordinal for ordinal, page in enumerate(pages, start=1)}


def _entry_response(
    entry: DictionaryEntry,
    fragments: list[EntryFragment],
    fields: list[EntryField],
    page_numbers: dict[UUID, int],
) -> EntryResponse:
    return EntryResponse(
        id=entry.id,
        dictionary_id=entry.dictionary_id,
        lexeme_id=entry.lexeme_id,
        headword=entry.headword,
        status=entry.status,
        schema_id=entry.schema_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        fragments=[
            EntryFragmentResponse(
                id=fragment.id,
                page_id=fragment.page_id,
                page_number=page_numbers.get(fragment.page_id),
                x=fragment.x,
                y=fragment.y,
                width=fragment.width,
                height=fragment.height,
                x2=fragment.x2,
                y2=fragment.y2,
                width2=fragment.width2,
                height2=fragment.height2,
                reading_order=fragment.reading_order,
                recognized_text=fragment.recognized_text,
            )
            for fragment in fragments
        ],
        fields=[
            EntryFieldResponse(
                id=field.id,
                fragment_id=field.fragment_id,
                parent_field_id=field.parent_field_id,
                field_path=field.field_path,
                role=field.role,
                position=field.position,
                source_text=field.source_text,
                source_start=field.source_start,
                source_end=field.source_end,
                x=field.x,
                y=field.y,
                width=field.width,
                height=field.height,
                normalized_text=field.normalized_text,
                confidence=field.confidence,
                origin=field.origin,
                created_at=field.created_at,
                updated_at=field.updated_at,
            )
            for field in fields
        ],
    )


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"code": "not_found", "message": "Статтю чи поле не знайдено."},
    )


def create_entries_router(
    authentication_service: AuthenticationService,
    promote_service: PromoteLexemeToEntryService,
    extraction_service: QueueEntryFieldExtractionService,
    create_field_service: CreateEntryFieldService,
    update_field_service: UpdateEntryFieldService,
    delete_field_service: DeleteEntryFieldService,
    validate_service: ValidateEntryService,
    render_entry_service: RenderEntryService,
    entry_query_service: EntryQueryService,
    dictionary_service: GetDictionaryService,
    processing_task_service: ProcessingTaskService | None = None,
) -> APIRouter:
    """Create BH-148 dictionary entry routes bound to application use cases."""
    router = APIRouter(tags=["entries"])

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
        "/dictionaries/{dictionary_id}/lexemes/{lexeme_id}/promote",
        response_model=EntryResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_409_CONFLICT: {
                "model": DuplicateEntryResponse,
                "description": "This lexeme was already promoted to an entry",
            },
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The lexeme is not COMPLETE yet",
            },
        },
        summary="Promote a completed lexeme into a structured dictionary entry",
    )
    def promote_lexeme(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        lexeme_id: Annotated[UUID, Path()],
    ) -> EntryResponse | JSONResponse:
        try:
            entry = promote_service.create(dictionary_id, lexeme_id, user.id)
        except EntryValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except DuplicateEntryError as error:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=DuplicateEntryResponse(
                    entry_id=error.existing_id,
                    message="Цю лексему вже перетворено на статтю.",
                ).model_dump(mode="json"),
            )
        except (LexemeAccessError, LexemeNotFoundError):
            return _not_found()
        _, fragments, fields = extraction_service.get(entry.id, user.id)
        page_numbers = _page_numbers(dictionary_service, entry.dictionary_id, user.id)
        return _entry_response(entry, fragments, fields, page_numbers)

    @router.get(
        "/dictionaries/{dictionary_id}/entries",
        response_model=list[EntrySummaryResponse],
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="List a dictionary's structured entries",
    )
    def list_entries(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> list[EntrySummaryResponse] | JSONResponse:
        try:
            rows = entry_query_service.list_for_dictionary(dictionary_id, user.id)
        except LexemeAccessError:
            return _not_found()
        return [
            EntrySummaryResponse(
                id=entry.id,
                headword=entry.headword,
                status=entry.status,
                field_count=field_count,
                created_at=entry.created_at,
                updated_at=entry.updated_at,
            )
            for entry, field_count in rows
        ]

    @router.get(
        "/entries/{entry_id}",
        response_model=EntryResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Read a dictionary entry with its fragments and structured fields",
    )
    def get_entry(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
    ) -> EntryResponse | JSONResponse:
        try:
            entry, fragments, fields = extraction_service.get(entry_id, user.id)
        except EntryAccessError:
            return _not_found()
        page_numbers = _page_numbers(dictionary_service, entry.dictionary_id, user.id)
        return _entry_response(entry, fragments, fields, page_numbers)

    @router.get(
        "/entries/{entry_id}/render",
        response_model=EntryRenderResponse,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Render an entry to Markdown via its schema's presentation formula",
    )
    def render_entry(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
    ) -> EntryRenderResponse | JSONResponse:
        try:
            result = render_entry_service.render(entry_id, user.id)
        except EntryAccessError:
            return _not_found()
        return EntryRenderResponse(
            markdown=result.markdown, reason=result.reason, error=result.error
        )

    @router.post(
        "/entries/{entry_id}/extract",
        response_model=EnqueueExtractionResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Enqueue AI field extraction for one entry",
    )
    def enqueue_extraction(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
    ) -> EnqueueExtractionResponse | JSONResponse:
        try:
            entry, _fragments, _fields = extraction_service.get(entry_id, user.id)
            task_id = extraction_service.enqueue(entry_id, user.id)
        except EntryAccessError:
            return _not_found()
        record_enqueued_task(
            processing_task_service,
            dictionary_id=entry.dictionary_id,
            kind=ProcessingTaskKind.ENTRY_EXTRACTION,
            celery_task_id=task_id,
            enqueued_by=user.id,
            target_id=entry_id,
            target_label=entry.headword,
        )
        return EnqueueExtractionResponse(task_id=task_id)

    @router.get(
        "/entries/{entry_id}/extract/{task_id}",
        response_model=ExtractionTaskResponse,
        response_model_exclude_none=True,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Poll a field-extraction task's status and result",
    )
    def get_extraction_task(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
        task_id: Annotated[str, Path(min_length=1, max_length=128)],
    ) -> ExtractionTaskResponse | JSONResponse:
        try:
            snapshot = extraction_service.get_task(entry_id, user.id, task_id)
        except EntryAccessError:
            return _not_found()
        return ExtractionTaskResponse(
            task_id=snapshot.task_id,
            status=snapshot.status,
            created_fields=snapshot.created_fields,
            error=snapshot.error,
        )

    @router.post(
        "/entries/{entry_id}/fields",
        response_model=EntryFieldResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "Field data is invalid",
            },
        },
        summary="Manually add a field an automatic pass missed",
    )
    def create_field(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
        request: CreateEntryFieldRequest,
    ) -> EntryFieldResponse | JSONResponse:
        try:
            field = create_field_service.create(
                entry_id,
                user.id,
                fragment_id=request.fragment_id,
                field_path=request.field_path,
                role=request.role,
                source_text=request.source_text,
                source_start=request.source_start,
                source_end=request.source_end,
                parent_field_id=request.parent_field_id,
                normalized_text=request.normalized_text,
            )
        except EntryFieldValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except EntryAccessError:
            return _not_found()
        return EntryFieldResponse(
            id=field.id,
            fragment_id=field.fragment_id,
            parent_field_id=field.parent_field_id,
            field_path=field.field_path,
            role=field.role,
            position=field.position,
            source_text=field.source_text,
            source_start=field.source_start,
            source_end=field.source_end,
            x=field.x,
            y=field.y,
            width=field.width,
            height=field.height,
            normalized_text=field.normalized_text,
            confidence=field.confidence,
            origin=field.origin,
            created_at=field.created_at,
            updated_at=field.updated_at,
        )

    @router.patch(
        "/entries/{entry_id}/fields/{field_id}",
        response_model=EntryFieldResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "Field data is invalid",
            },
        },
        summary="Edit a field; the edit flips its origin to manual",
    )
    def update_field(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
        field_id: Annotated[UUID, Path()],
        request: UpdateEntryFieldRequest,
    ) -> EntryFieldResponse | JSONResponse:
        try:
            field = update_field_service.update(
                entry_id,
                field_id,
                user.id,
                role=request.role,
                source_text=request.source_text,
                normalized_text=request.normalized_text,
            )
        except EntryFieldValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except (EntryAccessError, EntryFieldAccessError):
            return _not_found()
        return EntryFieldResponse(
            id=field.id,
            fragment_id=field.fragment_id,
            parent_field_id=field.parent_field_id,
            field_path=field.field_path,
            role=field.role,
            position=field.position,
            source_text=field.source_text,
            source_start=field.source_start,
            source_end=field.source_end,
            x=field.x,
            y=field.y,
            width=field.width,
            height=field.height,
            normalized_text=field.normalized_text,
            confidence=field.confidence,
            origin=field.origin,
            created_at=field.created_at,
            updated_at=field.updated_at,
        )

    @router.delete(
        "/entries/{entry_id}/fields/{field_id}",
        response_model=None,
        status_code=status.HTTP_204_NO_CONTENT,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Remove a manually-added or mistakenly-extracted field",
    )
    def delete_field(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
        field_id: Annotated[UUID, Path()],
    ) -> Response | JSONResponse:
        try:
            delete_field_service.delete(entry_id, field_id, user.id)
        except (EntryAccessError, EntryFieldAccessError):
            return _not_found()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post(
        "/entries/{entry_id}/complete",
        response_model=EntryResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The entry does not yet satisfy its article schema",
            },
        },
        summary="Validate an entry against its schema and mark it complete",
    )
    def complete_entry(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
    ) -> EntryResponse | JSONResponse:
        try:
            entry, fragments, fields = extraction_service.get(entry_id, user.id)
        except EntryAccessError:
            return _not_found()
        try:
            entry = validate_service.complete(entry.dictionary_id, entry_id, user.id)
        except EntryValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except (LexemeAccessError, EntryAccessError):
            return _not_found()
        page_numbers = _page_numbers(dictionary_service, entry.dictionary_id, user.id)
        return _entry_response(entry, fragments, fields, page_numbers)

    @router.post(
        "/entries/{entry_id}/submit-review",
        response_model=EntryResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The entry does not satisfy its schema, or is "
                "already complete",
            },
        },
        summary="Submit a draft entry for review (draft -> ready_to_review)",
    )
    def submit_entry_for_review(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
    ) -> EntryResponse | JSONResponse:
        try:
            entry, fragments, fields = extraction_service.get(entry_id, user.id)
        except EntryAccessError:
            return _not_found()
        try:
            entry = validate_service.submit_for_review(
                entry.dictionary_id, entry_id, user.id
            )
        except EntryValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except (LexemeAccessError, EntryAccessError):
            return _not_found()
        page_numbers = _page_numbers(dictionary_service, entry.dictionary_id, user.id)
        return _entry_response(entry, fragments, fields, page_numbers)

    return router
