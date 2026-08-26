"""AI article-schema generation and activation: application behavior (BH-148)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    ActivateArticleSchemaService,
    ArticleSchema,
    ArticleSchemaAccessError,
    ArticleSchemaGenerationSnapshot,
    ArticleSchemaValidationError,
    LexemeAccessError,
    OcrSuggestionStatus,
    QueueArticleSchemaGenerationService,
    SchemaGenerationStatus,
)
from cadmus.sources import (
    Dictionary,
    DictionaryStatus,
    GetDictionaryService,
    SourcesRepository,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    """A minimal fake covering only what ``GetDictionaryService`` needs here."""

    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> None:
        return None


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = cast(SourcesRepository, repository)

    def __enter__(self) -> "MemorySourcesUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        pass


@dataclass
class MemoryLexicographyRepository:
    article_schemas: dict[UUID, ArticleSchema] = field(default_factory=dict)

    def add_article_schema(self, schema: ArticleSchema) -> None:
        self.article_schemas[schema.id] = schema

    def get_article_schema(self, schema_id: UUID) -> ArticleSchema | None:
        return self.article_schemas.get(schema_id)

    def get_active_article_schema(self, dictionary_id: UUID) -> ArticleSchema | None:
        for schema in self.article_schemas.values():
            if (
                schema.dictionary_id == dictionary_id
                and schema.activated_at is not None
            ):
                return schema
        return None

    def list_article_schemas(self, dictionary_id: UUID) -> list[ArticleSchema]:
        return [
            schema
            for schema in self.article_schemas.values()
            if schema.dictionary_id == dictionary_id
        ]

    def update_article_schema(self, schema: ArticleSchema) -> None:
        self.article_schemas[schema.id] = schema


class MemoryLexicographyUnitOfWork:
    def __init__(self, repository: MemoryLexicographyRepository) -> None:
        from cadmus.lexicography import LexicographyRepository

        self.lexicography = cast(LexicographyRepository, repository)

    def __enter__(self) -> "MemoryLexicographyUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        pass


@dataclass
class FakeArticleSchemaQueue:
    snapshot: ArticleSchemaGenerationSnapshot | None = None
    enqueued: tuple[UUID, UUID] | None = None
    returned_task_id: str = "schema-task-123"

    def enqueue_generation(self, dictionary_id: UUID, actor_id: UUID) -> str:
        self.enqueued = (dictionary_id, actor_id)
        return self.returned_task_id

    def get_generation_task(self, task_id: str) -> ArticleSchemaGenerationSnapshot:
        assert self.snapshot is not None
        return self.snapshot


def _dictionary(owner_id: UUID) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


def _schema(
    dictionary_id: UUID,
    version: int,
    status: SchemaGenerationStatus = SchemaGenerationStatus.READY,
    activated_at: datetime | None = None,
) -> ArticleSchema:
    return ArticleSchema(
        id=uuid4(),
        dictionary_id=dictionary_id,
        version=version,
        status=status,
        source_description="headword; meaning; example",
        definition={"fields": []},
        created_at=NOW,
        created_by=dictionary_id,
        activated_at=activated_at,
    )


class Fixture:
    def __init__(self) -> None:
        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id)
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary

        self.dictionary_pages = GetDictionaryService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.lexicography_repository = MemoryLexicographyRepository()
        self.queue = FakeArticleSchemaQueue()
        self.queue_service = QueueArticleSchemaGenerationService(
            dictionary_pages=self.dictionary_pages,
            queue=self.queue,
        )
        self.activate_service = ActivateArticleSchemaService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            clock=lambda: NOW,
        )

    def add_schema(self, schema: ArticleSchema) -> None:
        self.lexicography_repository.article_schemas[schema.id] = schema


def test_enqueue_passes_the_dictionary_and_actor_id() -> None:
    fixture = Fixture()

    task_id = fixture.queue_service.enqueue(fixture.dictionary.id, fixture.owner_id)

    assert task_id == fixture.queue.returned_task_id
    assert fixture.queue.enqueued == (fixture.dictionary.id, fixture.owner_id)


def test_enqueue_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.queue_service.enqueue(fixture.dictionary.id, uuid4())


def test_enqueue_unknown_dictionary_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.queue_service.enqueue(uuid4(), fixture.owner_id)


def test_get_task_passes_through_ready_schema_id() -> None:
    fixture = Fixture()
    schema_id = uuid4()
    fixture.queue.snapshot = ArticleSchemaGenerationSnapshot(
        task_id="t1", status=OcrSuggestionStatus.SUCCEEDED, schema_id=schema_id
    )

    snapshot = fixture.queue_service.get_task(
        fixture.dictionary.id, fixture.owner_id, "t1"
    )

    assert snapshot.status is OcrSuggestionStatus.SUCCEEDED
    assert snapshot.schema_id == schema_id


def test_get_task_passes_through_failure() -> None:
    fixture = Fixture()
    fixture.queue.snapshot = ArticleSchemaGenerationSnapshot(
        task_id="t1", status=OcrSuggestionStatus.FAILED, error="boom"
    )

    snapshot = fixture.queue_service.get_task(
        fixture.dictionary.id, fixture.owner_id, "t1"
    )

    assert snapshot.status is OcrSuggestionStatus.FAILED
    assert snapshot.error == "boom"


def test_get_task_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.queue_service.get_task(fixture.dictionary.id, uuid4(), "t1")


def test_list_versions_returns_only_this_dictionary_s_schemas() -> None:
    fixture = Fixture()
    own_schema = _schema(fixture.dictionary.id, version=1)
    other_schema = _schema(uuid4(), version=1)
    fixture.add_schema(own_schema)
    fixture.add_schema(other_schema)

    versions = fixture.activate_service.list_versions(
        fixture.dictionary.id, fixture.owner_id
    )

    assert [schema.id for schema in versions] == [own_schema.id]


def test_activate_sets_activated_at_and_by() -> None:
    fixture = Fixture()
    schema = _schema(fixture.dictionary.id, version=1)
    fixture.add_schema(schema)

    activated = fixture.activate_service.activate(
        fixture.dictionary.id, schema.id, fixture.owner_id
    )

    assert activated.activated_at == NOW
    assert activated.activated_by == fixture.owner_id


def test_activate_deactivates_the_previously_active_version() -> None:
    fixture = Fixture()
    first = _schema(fixture.dictionary.id, version=1, activated_at=NOW)
    first.activated_by = fixture.owner_id
    second = _schema(fixture.dictionary.id, version=2)
    fixture.add_schema(first)
    fixture.add_schema(second)

    fixture.activate_service.activate(
        fixture.dictionary.id, second.id, fixture.owner_id
    )

    stored_first = fixture.lexicography_repository.article_schemas[first.id]
    assert stored_first.activated_at is None
    assert stored_first.activated_by is None
    stored_second = fixture.lexicography_repository.article_schemas[second.id]
    assert stored_second.activated_at == NOW


def test_activate_rejects_a_non_ready_version() -> None:
    fixture = Fixture()
    schema = _schema(
        fixture.dictionary.id, version=1, status=SchemaGenerationStatus.PENDING
    )
    fixture.add_schema(schema)

    with pytest.raises(ArticleSchemaValidationError):
        fixture.activate_service.activate(
            fixture.dictionary.id, schema.id, fixture.owner_id
        )


def test_activate_unknown_schema_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(ArticleSchemaAccessError):
        fixture.activate_service.activate(
            fixture.dictionary.id, uuid4(), fixture.owner_id
        )


def test_activate_schema_from_another_dictionary_raises_access_error() -> None:
    fixture = Fixture()
    schema = _schema(uuid4(), version=1)
    fixture.add_schema(schema)

    with pytest.raises(ArticleSchemaAccessError):
        fixture.activate_service.activate(
            fixture.dictionary.id, schema.id, fixture.owner_id
        )
