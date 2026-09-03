"""Celery task: AI article-schema generation (BH-148)."""

from dataclasses import dataclass, field
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    ArticleSchema,
    LexicographyRepository,
    SchemaGenerationStatus,
)
from cadmus.sources import Dictionary, DictionaryStatus, SourcesRepository
from cadmus_worker import article_schema_tasks
from cadmus_worker.article_schema_tasks import (
    _ArticleSchemaDependencies,
    generate_article_schema,
)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)


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

    def list_article_schemas(self, dictionary_id: UUID) -> list[ArticleSchema]:
        return [
            schema
            for schema in self.article_schemas.values()
            if schema.dictionary_id == dictionary_id
        ]


class MemoryLexicographyUnitOfWork:
    def __init__(self, repository: MemoryLexicographyRepository) -> None:
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


class FakeAiSchemaProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[str] = []

    def generate_schema(self, article_description: str):  # type: ignore[no-untyped-def]
        from cadmus.infrastructure.ai_schema import AiSchemaProviderError
        from cadmus.lexicography import GeneratedSchema

        self.calls.append(article_description)
        if self.fail:
            raise AiSchemaProviderError("provider unavailable")
        return GeneratedSchema(
            definition={
                "fields": [{"name": "headword", "role": "headword", "type": "string"}]
            },
            raw_response={"ok": True},
            provider_name="fake:test",
            presentation_formula="# {{ headword }}",
        )

    def extract_fields(self, schema, source_text):  # type: ignore[no-untyped-def]
        raise AssertionError("not used by schema generation")


def _dictionary(description: str | None = "headword; meaning; example") -> Dictionary:
    owner_id = uuid4()
    from datetime import UTC, datetime

    now = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
    dictionary = Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=now,
        updated_at=now,
        updated_by=owner_id,
    )
    dictionary.article_description = description
    return dictionary


class Fixture:
    def __init__(self, *, provider_fails: bool = False) -> None:
        self.sources_repository = MemorySourcesRepository()
        self.lexicography_repository = MemoryLexicographyRepository()
        self.provider = FakeAiSchemaProvider(fail=provider_fails)
        self.dictionary = _dictionary()
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary

        deps = _ArticleSchemaDependencies(
            sources_unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            ),
            lexicography_unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            ai_schema_provider=self.provider,  # type: ignore[arg-type]
        )
        self._deps = deps

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            article_schema_tasks, "_article_schema_dependencies", lambda: self._deps
        )


def test_generate_article_schema_persists_a_ready_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture()
    fixture.install(monkeypatch)

    result = generate_article_schema.apply(
        args=[str(fixture.dictionary.id), str(fixture.dictionary.owner_id)],
        task_id="task-1",
    ).get()

    assert result["status"] == "succeeded"
    schemas = fixture.lexicography_repository.list_article_schemas(
        fixture.dictionary.id
    )
    assert len(schemas) == 1
    assert schemas[0].status is SchemaGenerationStatus.READY
    assert schemas[0].definition["fields"][0]["name"] == "headword"
    assert schemas[0].presentation_formula == "# {{ headword }}"
    assert str(schemas[0].id) == result["schema_id"]


def test_generate_article_schema_persists_failed_on_provider_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(provider_fails=True)
    fixture.install(monkeypatch)

    result = generate_article_schema.apply(
        args=[str(fixture.dictionary.id), str(fixture.dictionary.owner_id)],
        task_id="task-2",
    ).get()

    assert result["status"] == "failed"
    schemas = fixture.lexicography_repository.list_article_schemas(
        fixture.dictionary.id
    )
    assert len(schemas) == 1
    assert schemas[0].status is SchemaGenerationStatus.FAILED
    assert schemas[0].error_message == "provider unavailable"


def test_generate_article_schema_missing_dictionary_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture()
    fixture.install(monkeypatch)

    result = generate_article_schema.apply(
        args=[str(uuid4()), str(fixture.dictionary.owner_id)], task_id="task-3"
    ).get()

    assert result["status"] == "failed"
    assert result["error"] == "dictionary not found"


def test_generate_article_schema_missing_description_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture()
    fixture.dictionary.article_description = None
    fixture.install(monkeypatch)

    result = generate_article_schema.apply(
        args=[str(fixture.dictionary.id), str(fixture.dictionary.owner_id)],
        task_id="task-4",
    ).get()

    assert result["status"] == "failed"
    assert (
        fixture.lexicography_repository.list_article_schemas(fixture.dictionary.id)
        == []
    )
