"""Celery task: AI entry field extraction from plain ``recognized_text`` (BH-148)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    ArticleSchema,
    DictionaryEntry,
    EntryField,
    EntryFieldOrigin,
    EntryFieldRole,
    EntryFragment,
    EntryStatus,
    ExtractedField,
    LexicographyRepository,
    RuleBasedAnnotationService,
    SchemaGenerationStatus,
)
from cadmus.sources import Dictionary, DictionaryStatus, SourcesRepository
from cadmus_worker import entry_extraction_tasks
from cadmus_worker.entry_extraction_tasks import (
    _EntryExtractionDependencies,
    extract_entry_fields,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)
FRAGMENT_TEXT = "слово означає щось важливе"

_HEADWORD_ITEM = ExtractedField(
    field_path="headword",
    role=EntryFieldRole.HEADWORD,
    value="слово",
    confidence=0.9,
)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    abbreviations: dict[UUID, list[object]] = field(default_factory=dict)
    settlements: dict[UUID, list[object]] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def list_abbreviations(self, dictionary_id: UUID) -> list[object]:
        return list(self.abbreviations.get(dictionary_id, []))

    def list_settlement_mappings(self, dictionary_id: UUID) -> list[object]:
        return list(self.settlements.get(dictionary_id, []))


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
    entries: dict[UUID, DictionaryEntry] = field(default_factory=dict)
    fragments: dict[UUID, list[EntryFragment]] = field(default_factory=dict)
    fields: dict[UUID, list[EntryField]] = field(default_factory=dict)
    article_schemas: dict[UUID, ArticleSchema] = field(default_factory=dict)

    def get_entry(self, entry_id: UUID) -> DictionaryEntry | None:
        return self.entries.get(entry_id)

    def update_entry(self, entry: DictionaryEntry) -> None:
        self.entries[entry.id] = entry

    def get_active_article_schema(self, dictionary_id: UUID) -> ArticleSchema | None:
        for schema in self.article_schemas.values():
            if (
                schema.dictionary_id == dictionary_id
                and schema.activated_at is not None
            ):
                return schema
        return None

    def list_fragments_for_entry(self, entry_id: UUID) -> list[EntryFragment]:
        return list(self.fragments.get(entry_id, []))

    def add_field(self, entry_field: EntryField) -> None:
        self.fields.setdefault(entry_field.entry_id, []).append(entry_field)

    def list_fields_for_entry(self, entry_id: UUID) -> list[EntryField]:
        return list(self.fields.get(entry_id, []))


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
    def __init__(
        self,
        *,
        fail: bool = False,
        items: list[ExtractedField] | None = None,
    ) -> None:
        self.fail = fail
        self.items = [_HEADWORD_ITEM] if items is None else items
        self.received_text: str | None = None

    def generate_schema(self, article_description: str):  # type: ignore[no-untyped-def]
        raise AssertionError("not used by extraction")

    def extract_fields(  # type: ignore[no-untyped-def]
        self, schema: ArticleSchema, text: str
    ):
        from cadmus.infrastructure.ai_schema import AiSchemaProviderError

        self.received_text = text
        if self.fail:
            raise AiSchemaProviderError("provider unavailable")
        return list(self.items)


def _dictionary() -> Dictionary:
    owner_id = uuid4()
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


def _entry(dictionary_id: UUID) -> DictionaryEntry:
    owner_id = uuid4()
    return DictionaryEntry(
        id=uuid4(),
        dictionary_id=dictionary_id,
        lexeme_id=uuid4(),
        headword="слово",
        status=EntryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        created_by=owner_id,
        updated_by=owner_id,
    )


def _fragment(entry_id: UUID, *, text: str = FRAGMENT_TEXT) -> EntryFragment:
    return EntryFragment(
        id=uuid4(),
        entry_id=entry_id,
        page_id=uuid4(),
        x=0,
        y=0,
        width=100,
        height=40,
        reading_order=0,
        recognized_text=text,
    )


def _schema(
    dictionary_id: UUID, definition: dict[str, object] | None = None
) -> ArticleSchema:
    return ArticleSchema(
        id=uuid4(),
        dictionary_id=dictionary_id,
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="headword",
        definition=definition or {"fields": [{"name": "headword", "role": "headword"}]},
        created_at=NOW,
        created_by=dictionary_id,
        activated_at=NOW,
        activated_by=dictionary_id,
    )


class Fixture:
    def __init__(
        self,
        *,
        provider_fails: bool = False,
        items: list[ExtractedField] | None = None,
        fragment_text: str = FRAGMENT_TEXT,
        definition: dict[str, object] | None = None,
    ) -> None:
        self.sources_repository = MemorySourcesRepository()
        self.lexicography_repository = MemoryLexicographyRepository()
        self.provider = FakeAiSchemaProvider(fail=provider_fails, items=items)

        self.dictionary = _dictionary()
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary
        self.entry = _entry(self.dictionary.id)
        self.lexicography_repository.entries[self.entry.id] = self.entry
        self.fragment = _fragment(self.entry.id, text=fragment_text)
        self.lexicography_repository.fragments[self.entry.id] = [self.fragment]
        self.schema = _schema(self.dictionary.id, definition)
        self.lexicography_repository.article_schemas[self.schema.id] = self.schema

        annotation_service = RuleBasedAnnotationService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            sources_unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            ),
        )
        self._deps = _EntryExtractionDependencies(
            lexicography_unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            sources_unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            ),
            ai_schema_provider=self.provider,  # type: ignore[arg-type]
            annotation_service=annotation_service,
        )

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            entry_extraction_tasks, "_entry_extraction_dependencies", lambda: self._deps
        )

    def run(self, task_id: str) -> dict[str, object]:
        return cast(
            "dict[str, object]",
            extract_entry_fields.apply(
                args=[str(self.entry.id), str(self.entry.created_by)], task_id=task_id
            ).get(),
        )

    def stored_fields(self) -> list[EntryField]:
        return self.lexicography_repository.list_fields_for_entry(self.entry.id)


def test_extract_entry_fields_persists_model_fields_from_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture()
    fixture.install(monkeypatch)

    result = fixture.run("task-1")

    assert result["status"] == "succeeded"
    assert fixture.provider.received_text == FRAGMENT_TEXT
    fields = fixture.stored_fields()
    assert len(fields) == 1
    stored = fields[0]
    assert stored.origin is EntryFieldOrigin.MODEL
    assert stored.fragment_id == fixture.fragment.id
    assert stored.field_path == "headword"
    assert stored.source_text == "слово"
    assert (stored.source_start, stored.source_end) == (0, 5)
    assert stored.normalized_text is None  # value already verbatim
    assert stored.x is None and stored.y is None
    assert stored.width is None and stored.height is None
    stored_entry = fixture.lexicography_repository.entries[fixture.entry.id]
    assert stored_entry.status is EntryStatus.READY_TO_REVIEW
    assert stored_entry.schema_id == fixture.schema.id


def test_extract_entry_fields_value_absent_from_text_stores_no_offsets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(
        items=[ExtractedField("headword", EntryFieldRole.HEADWORD, "вигадане", 0.8)]
    )
    fixture.install(monkeypatch)

    fixture.run("task-1b")

    stored = fixture.stored_fields()[0]
    assert stored.source_text == "вигадане"
    assert stored.source_start is None and stored.source_end is None


def test_extract_entry_fields_dedupes_repeats_for_a_non_repeatable_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(
        definition={
            "fields": [
                {"name": "district", "role": "geographic_label", "type": "string"}
            ]
        },
        fragment_text="Сок. Кельм. Хот.",
        items=[
            ExtractedField("district", EntryFieldRole.GEOGRAPHIC_LABEL, "Сок.", 0.90),
            ExtractedField("district", EntryFieldRole.GEOGRAPHIC_LABEL, "сок.", 0.88),
            ExtractedField("district", EntryFieldRole.GEOGRAPHIC_LABEL, "Сок.", 0.80),
        ],
    )
    fixture.install(monkeypatch)

    fixture.run("task-1c")

    fields = fixture.stored_fields()
    assert len(fields) == 1
    assert fields[0].confidence == 0.90


def test_extract_entry_fields_skips_a_failed_fragment_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(provider_fails=True)
    fixture.install(monkeypatch)

    result = fixture.run("task-2")

    assert result["status"] == "succeeded"
    assert result["created_fields"] == 0
    assert fixture.stored_fields() == []
    assert (
        fixture.lexicography_repository.entries[fixture.entry.id].status
        is EntryStatus.READY_TO_REVIEW
    )


def test_extract_entry_fields_skips_a_fragment_with_blank_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(fragment_text="   ")
    fixture.install(monkeypatch)

    result = fixture.run("task-2b")

    assert result["status"] == "succeeded"
    assert result["created_fields"] == 0
    assert fixture.provider.received_text is None  # provider never called


def test_extract_entry_fields_missing_entry_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture()
    fixture.install(monkeypatch)

    result = extract_entry_fields.apply(
        args=[str(uuid4()), str(fixture.entry.created_by)], task_id="task-3"
    ).get()

    assert result["status"] == "failed"
    assert result["error"] == "entry not found"


def test_extract_entry_fields_no_active_schema_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture()
    fixture.schema.activated_at = None
    fixture.install(monkeypatch)

    result = fixture.run("task-4")

    assert result["status"] == "failed"
    assert result["error"] == "no active article schema"
