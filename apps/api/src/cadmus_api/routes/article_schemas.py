"""Thin HTTP adapters for the BH-148 AI article-schema use cases."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from cadmus.identity import AuthenticationError, AuthenticationService, User
from cadmus.lexicography import (
    ActivateArticleSchemaService,
    ArticleSchema,
    ArticleSchemaAccessError,
    ArticleSchemaValidationError,
    LexemeAccessError,
    OcrSuggestionStatus,
    QueueArticleSchemaGenerationService,
    SchemaGenerationStatus,
)
from fastapi import APIRouter, Cookie, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

SESSION_COOKIE_NAME = "cadmus_session"


class EnqueueGenerationResponse(BaseModel):
    """Accepted response for a newly queued schema-generation job."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: OcrSuggestionStatus = OcrSuggestionStatus.QUEUED


class GenerationTaskResponse(BaseModel):
    """Poll response: task status plus the resulting schema id once succeeded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    status: OcrSuggestionStatus
    schema_id: UUID | None = None
    error: str | None = None


class ArticleSchemaResponse(BaseModel):
    """One version of a dictionary's AI-generated (or activated) article schema."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    dictionary_id: UUID
    version: int
    status: SchemaGenerationStatus
    source_description: str
    definition: dict[str, Any]
    provider_name: str | None
    error_message: str | None
    created_at: datetime
    activated_at: datetime | None


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
        "description": "The dictionary or article schema does not exist or is not "
        "owned by the caller",
    }
}


def _article_schema_response(schema: ArticleSchema) -> ArticleSchemaResponse:
    return ArticleSchemaResponse(
        id=schema.id,
        dictionary_id=schema.dictionary_id,
        version=schema.version,
        status=schema.status,
        source_description=schema.source_description,
        definition=schema.definition,
        provider_name=schema.provider_name,
        error_message=schema.error_message,
        created_at=schema.created_at,
        activated_at=schema.activated_at,
    )


def _not_found() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"code": "not_found", "message": "Словник чи схему не знайдено."},
    )


def create_article_schemas_router(
    authentication_service: AuthenticationService,
    generation_service: QueueArticleSchemaGenerationService,
    activate_service: ActivateArticleSchemaService,
) -> APIRouter:
    """Create BH-148 article-schema routes bound to application use cases."""
    router = APIRouter(prefix="/dictionaries/{dictionary_id}", tags=["article-schemas"])

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
        "/article-schema/generate",
        response_model=EnqueueGenerationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Enqueue AI article-schema generation from article_description",
    )
    def enqueue_generation(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
    ) -> EnqueueGenerationResponse | JSONResponse:
        try:
            task_id = generation_service.enqueue(dictionary_id, user.id)
        except LexemeAccessError:
            return _not_found()
        return EnqueueGenerationResponse(task_id=task_id)

    @router.get(
        "/article-schema/generate/{task_id}",
        response_model=GenerationTaskResponse,
        response_model_exclude_none=True,
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="Poll an article-schema generation task's status and result",
    )
    def get_generation_task(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        task_id: Annotated[str, Path(min_length=1, max_length=128)],
    ) -> GenerationTaskResponse | JSONResponse:
        try:
            snapshot = generation_service.get_task(dictionary_id, user.id, task_id)
        except LexemeAccessError:
            return _not_found()
        return GenerationTaskResponse(
            task_id=snapshot.task_id,
            status=snapshot.status,
            schema_id=snapshot.schema_id,
            error=snapshot.error,
        )

    @router.get(
        "/article-schemas",
        response_model=list[ArticleSchemaResponse],
        responses={**UNAUTHORIZED_RESPONSE, **NOT_FOUND_RESPONSE},
        summary="List every article-schema version generated for a dictionary",
    )
    def list_article_schemas(
        user: AuthenticatedUser, dictionary_id: Annotated[UUID, Path()]
    ) -> list[ArticleSchemaResponse] | JSONResponse:
        try:
            versions = activate_service.list_versions(dictionary_id, user.id)
        except LexemeAccessError:
            return _not_found()
        return [_article_schema_response(version) for version in versions]

    @router.post(
        "/article-schemas/{schema_id}/activate",
        response_model=ArticleSchemaResponse,
        responses={
            **UNAUTHORIZED_RESPONSE,
            **NOT_FOUND_RESPONSE,
            status.HTTP_422_UNPROCESSABLE_CONTENT: {
                "model": FieldErrorsResponse,
                "description": "The schema version is not READY and cannot be "
                "activated",
            },
        },
        summary="Confirm one generated schema version as the dictionary's active one",
    )
    def activate_article_schema(
        user: AuthenticatedUser,
        dictionary_id: Annotated[UUID, Path()],
        schema_id: Annotated[UUID, Path()],
    ) -> ArticleSchemaResponse | JSONResponse:
        try:
            schema = activate_service.activate(dictionary_id, schema_id, user.id)
        except ArticleSchemaValidationError as error:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                content={"errors": error.errors},
            )
        except (LexemeAccessError, ArticleSchemaAccessError):
            return _not_found()
        return _article_schema_response(schema)

    return router
