"""Celery entrypoint for AI-generated dictionary article schemas (BH-148),
kept separate from ``entry_extraction_tasks.py`` -- generating a
dictionary-level schema and extracting one entry's fields are different
capabilities with different inputs.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from uuid import UUID, uuid4

from cadmus.config import Settings
from cadmus.infrastructure.ai_schema import (
    AiSchemaProviderError,
    AnthropicAiSchemaProvider,
)
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.lexicography import (
    create_lexicography_unit_of_work_factory,
)
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.lexicography import (
    GENERATE_ARTICLE_SCHEMA_TASK_NAME,
    ArticleSchema,
    LexicographyUnitOfWorkFactory,
    SchemaGenerationStatus,
)
from cadmus.sources import SourcesUnitOfWorkFactory
from celery import Task

from cadmus_worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def _log_task_event(event: str, task_id: str, **fields: object) -> None:
    logger.info(
        json.dumps({"event": event, "task_id": task_id, **fields}, sort_keys=True)
    )


@dataclass(frozen=True)
class _ArticleSchemaDependencies:
    sources_unit_of_work_factory: SourcesUnitOfWorkFactory
    lexicography_unit_of_work_factory: LexicographyUnitOfWorkFactory
    ai_schema_provider: AnthropicAiSchemaProvider


@lru_cache(maxsize=1)
def _article_schema_dependencies() -> _ArticleSchemaDependencies:
    settings = Settings()
    engine = create_database_engine(settings)
    api_key = settings.anthropic_api_key
    return _ArticleSchemaDependencies(
        sources_unit_of_work_factory=create_sources_unit_of_work_factory(engine),
        lexicography_unit_of_work_factory=create_lexicography_unit_of_work_factory(
            engine
        ),
        ai_schema_provider=AnthropicAiSchemaProvider(
            api_key=api_key.get_secret_value() if api_key is not None else "",
            model=settings.ai_schema_model,
            timeout_seconds=settings.ai_schema_timeout_seconds,
        ),
    )


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=GENERATE_ARTICLE_SCHEMA_TASK_NAME,
    soft_time_limit=90,
    time_limit=120,
)
def generate_article_schema(
    task: Task, dictionary_id: str, actor_id: str
) -> dict[str, object]:
    """Turn a dictionary's ``article_description`` into a new
    ``ArticleSchema`` version, persisted as ``READY`` on success or
    ``FAILED`` with an ``error_message`` otherwise -- a provider failure
    never crashes the task itself.
    """
    task_id = str(task.request.id)
    _log_task_event("article_schema_generation_started", task_id)
    deps = _article_schema_dependencies()
    dictionary_uuid = UUID(dictionary_id)
    actor_uuid = UUID(actor_id)

    with deps.sources_unit_of_work_factory() as unit_of_work:
        dictionary = unit_of_work.sources.get_dictionary(dictionary_uuid)
    if dictionary is None:
        _log_task_event("article_schema_generation_dictionary_missing", task_id)
        return {"status": "failed", "error": "dictionary not found"}

    description = dictionary.article_description
    if not description or not description.strip():
        _log_task_event("article_schema_generation_no_description", task_id)
        return {"status": "failed", "error": "dictionary has no article_description"}

    now = datetime.now(UTC)
    with deps.lexicography_unit_of_work_factory() as unit_of_work:
        next_version = (
            len(unit_of_work.lexicography.list_article_schemas(dictionary_uuid)) + 1
        )
        try:
            generated = deps.ai_schema_provider.generate_schema(description)
        except AiSchemaProviderError as error:
            schema = ArticleSchema(
                id=uuid4(),
                dictionary_id=dictionary_uuid,
                version=next_version,
                status=SchemaGenerationStatus.FAILED,
                source_description=description,
                definition={},
                created_at=now,
                created_by=actor_uuid,
                error_message=str(error),
            )
            unit_of_work.lexicography.add_article_schema(schema)
            unit_of_work.commit()
            _log_task_event(
                "article_schema_generation_failed", task_id, error=str(error)
            )
            return {"status": "failed", "error": str(error)}

        schema = ArticleSchema(
            id=uuid4(),
            dictionary_id=dictionary_uuid,
            version=next_version,
            status=SchemaGenerationStatus.READY,
            source_description=description,
            definition=generated.definition,
            created_at=now,
            created_by=actor_uuid,
            raw_provider_response=generated.raw_response,
            provider_name=generated.provider_name,
        )
        unit_of_work.lexicography.add_article_schema(schema)
        unit_of_work.commit()

    _log_task_event(
        "article_schema_generation_succeeded", task_id, schema_id=str(schema.id)
    )
    return {"status": "succeeded", "schema_id": str(schema.id)}
