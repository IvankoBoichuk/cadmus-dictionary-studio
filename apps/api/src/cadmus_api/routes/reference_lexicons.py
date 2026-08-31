"""HTTP adapters for VESUM lookup and manually confirmed entry mappings."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import (
    EntryAccessError,
    ManageEntryReferenceLinksService,
    ReferenceLemmaNotStandardError,
    ReferenceLinkAccessError,
    ReferenceRelationType,
)
from cadmus.reference_lexicon import (
    ReferenceLemma,
    ReferenceLemmaNotFoundError,
    ReferenceLexicon,
    ReferenceLexiconNotFoundError,
    ReferenceLexiconQueryService,
    ReferenceMatchType,
)
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

SESSION_COOKIE_NAME = "cadmus_session"


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str


class ReferenceLexiconResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    code: str
    name: str
    language_code: str
    version: str
    source_url: str
    license_id: str
    source_commit: str | None
    checksum: str
    imported_at: datetime


class ReferenceLemmaResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    lemma: str
    normalized_lemma: str
    part_of_speech: str
    key_tags: list[str]
    is_standard: bool
    match_type: ReferenceMatchType | None = None
    matched_form: str | None = None


class EntryReferenceLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    entry_id: UUID
    reference_lemma_id: UUID
    relation_type: ReferenceRelationType
    origin: str
    validation_status: str
    confidence: float | None
    created_at: datetime
    lemma: ReferenceLemmaResponse


class CreateEntryReferenceLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_lemma_id: UUID
    relation_type: ReferenceRelationType = ReferenceRelationType.STANDARD_EQUIVALENT


def _lexicon_response(lexicon: ReferenceLexicon) -> ReferenceLexiconResponse:
    return ReferenceLexiconResponse(
        id=lexicon.id,
        code=lexicon.code,
        name=lexicon.name,
        language_code=lexicon.language_code,
        version=lexicon.version,
        source_url=lexicon.source_url,
        license_id=lexicon.license_id,
        source_commit=lexicon.source_commit,
        checksum=lexicon.checksum,
        imported_at=lexicon.imported_at,
    )


def _lemma_response(
    lemma: ReferenceLemma,
    *,
    match_type: ReferenceMatchType | None = None,
    matched_form: str | None = None,
) -> ReferenceLemmaResponse:
    return ReferenceLemmaResponse(
        id=lemma.id,
        lemma=lemma.lemma,
        normalized_lemma=lemma.normalized_lemma,
        part_of_speech=lemma.part_of_speech,
        key_tags=list(lemma.key_tags),
        is_standard=lemma.is_standard,
        match_type=match_type,
        matched_form=matched_form,
    )


def create_reference_lexicons_router(
    authentication_service: AuthenticationService,
    query_service: ReferenceLexiconQueryService,
    link_service: ManageEntryReferenceLinksService,
) -> APIRouter:
    """Create authenticated reference-lexicon lookup and mapping routes."""

    router = APIRouter(tags=["reference lexicons"])

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
        "/reference-lexicons/{code}",
        response_model=ReferenceLexiconResponse,
        responses={404: {"model": ErrorResponse}},
        summary="Read metadata for an imported reference lexicon",
    )
    def get_lexicon(
        user: AuthenticatedUser,
        code: Annotated[str, Path(min_length=1, max_length=64)],
    ) -> ReferenceLexiconResponse | JSONResponse:
        del user
        try:
            return _lexicon_response(query_service.get_lexicon(code))
        except ReferenceLexiconNotFoundError:
            return JSONResponse(
                status_code=404,
                content={
                    "code": "not_found",
                    "message": "Еталонний словник не імпортовано.",
                },
            )

    @router.get(
        "/reference-lexicons/{code}/lemmas",
        response_model=list[ReferenceLemmaResponse],
        responses={404: {"model": ErrorResponse}},
        summary="Search reference lemmas by lemma or generated word form",
    )
    def search_lemmas(
        user: AuthenticatedUser,
        code: Annotated[str, Path(min_length=1, max_length=64)],
        q: Annotated[str, Query(min_length=1, max_length=500)],
        standard_only: bool = True,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> list[ReferenceLemmaResponse] | JSONResponse:
        del user
        try:
            matches = query_service.search(
                code, q, standard_only=standard_only, limit=limit
            )
        except ReferenceLexiconNotFoundError:
            return JSONResponse(
                status_code=404,
                content={"code": "not_found", "message": "Еталонний словник не імпортовано."},
            )
        return [
            _lemma_response(
                match.lemma,
                match_type=match.match_type,
                matched_form=match.matched_form,
            )
            for match in matches
        ]

    @router.get(
        "/entries/{entry_id}/reference-links",
        response_model=list[EntryReferenceLinkResponse],
        responses={404: {"model": ErrorResponse}},
        summary="List confirmed reference lemmas linked to a dictionary entry",
    )
    def list_entry_links(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
    ) -> list[EntryReferenceLinkResponse] | JSONResponse:
        try:
            linked = link_service.list(entry_id, user.id)
        except (EntryAccessError, ReferenceLemmaNotFoundError):
            return JSONResponse(
                status_code=404,
                content={
                    "code": "not_found",
                    "message": "Статтю або відповідник не знайдено.",
                },
            )
        return [
            EntryReferenceLinkResponse(
                id=item.link.id,
                entry_id=item.link.entry_id,
                reference_lemma_id=item.link.reference_lemma_id,
                relation_type=item.link.relation_type,
                origin=str(item.link.origin),
                validation_status=str(item.link.validation_status),
                confidence=item.link.confidence,
                created_at=item.link.created_at,
                lemma=_lemma_response(item.lemma),
            )
            for item in linked
        ]

    @router.post(
        "/entries/{entry_id}/reference-links",
        response_model=EntryReferenceLinkResponse,
        status_code=status.HTTP_201_CREATED,
        responses={
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
        },
        summary="Confirm a reference lemma as an equivalent or related lemma",
    )
    def create_entry_link(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
        payload: CreateEntryReferenceLinkRequest,
    ) -> EntryReferenceLinkResponse | JSONResponse:
        try:
            item = link_service.create(
                entry_id,
                user.id,
                payload.reference_lemma_id,
                relation_type=payload.relation_type,
            )
        except (EntryAccessError, ReferenceLemmaNotFoundError):
            return JSONResponse(
                status_code=404,
                content={
                    "code": "not_found",
                    "message": "Статтю або відповідник не знайдено.",
                },
            )
        except ReferenceLemmaNotStandardError:
            return JSONResponse(
                status_code=422,
                content={
                    "code": "non_standard_reference",
                    "message": "Для літературного відповідника виберіть нормативну лему.",
                },
            )
        return EntryReferenceLinkResponse(
            id=item.link.id,
            entry_id=item.link.entry_id,
            reference_lemma_id=item.link.reference_lemma_id,
            relation_type=item.link.relation_type,
            origin=str(item.link.origin),
            validation_status=str(item.link.validation_status),
            confidence=item.link.confidence,
            created_at=item.link.created_at,
            lemma=_lemma_response(item.lemma),
        )

    @router.delete(
        "/entries/{entry_id}/reference-links/{link_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses={404: {"model": ErrorResponse}},
        summary="Remove a confirmed reference-lemma link",
    )
    def delete_entry_link(
        user: AuthenticatedUser,
        entry_id: Annotated[UUID, Path()],
        link_id: Annotated[UUID, Path()],
    ) -> Response | JSONResponse:
        try:
            link_service.delete(entry_id, link_id, user.id)
        except (EntryAccessError, ReferenceLinkAccessError):
            return JSONResponse(
                status_code=404,
                content={"code": "not_found", "message": "Прив'язку не знайдено."},
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
