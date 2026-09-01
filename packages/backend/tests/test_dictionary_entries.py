"""Lexeme promotion, extraction queueing, and schema validation (BH-148)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    ArticleSchema,
    DictionaryEntry,
    DuplicateEntryError,
    EntryAccessError,
    EntryExtractionSnapshot,
    EntryField,
    EntryFieldOrigin,
    EntryFieldRole,
    EntryFragment,
    EntryQueryService,
    EntryStatus,
    EntryValidationError,
    Lexeme,
    LexemeOrigin,
    LexemeStatus,
    LexicographyRepository,
    OcrSuggestionStatus,
    PromoteLexemeToEntryService,
    QueueEntryFieldExtractionService,
    SchemaGenerationStatus,
    ValidateEntryService,
    validate_entry_against_schema,
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
    lexemes: dict[UUID, Lexeme] = field(default_factory=dict)
    entries: dict[UUID, DictionaryEntry] = field(default_factory=dict)
    fragments: dict[UUID, list[EntryFragment]] = field(default_factory=dict)
    fields: dict[UUID, list[EntryField]] = field(default_factory=dict)
    article_schemas: dict[UUID, ArticleSchema] = field(default_factory=dict)

    def get_lexeme(self, dictionary_id: UUID, lexeme_id: UUID) -> Lexeme | None:
        lexeme = self.lexemes.get(lexeme_id)
        if lexeme is None or lexeme.dictionary_id != dictionary_id:
            return None
        return lexeme

    def get_entry_by_lexeme(self, lexeme_id: UUID) -> DictionaryEntry | None:
        for entry in self.entries.values():
            if entry.lexeme_id == lexeme_id:
                return entry
        return None

    def add_entry(self, entry: DictionaryEntry) -> None:
        self.entries[entry.id] = entry

    def get_entry(self, entry_id: UUID) -> DictionaryEntry | None:
        return self.entries.get(entry_id)

    def list_entries_for_dictionary(self, dictionary_id: UUID) -> list[DictionaryEntry]:
        return sorted(
            (
                entry
                for entry in self.entries.values()
                if entry.dictionary_id == dictionary_id
            ),
            key=lambda entry: (entry.headword, entry.created_at),
        )

    def count_fields_by_entry(self, dictionary_id: UUID) -> dict[UUID, int]:
        entry_ids = {
            entry.id
            for entry in self.entries.values()
            if entry.dictionary_id == dictionary_id
        }
        return {
            entry_id: len(bucket)
            for entry_id, bucket in self.fields.items()
            if entry_id in entry_ids and bucket
        }

    def update_entry(self, entry: DictionaryEntry) -> None:
        self.entries[entry.id] = entry

    def add_fragment(self, fragment: EntryFragment) -> None:
        self.fragments.setdefault(fragment.entry_id, []).append(fragment)

    def list_fragments_for_entry(self, entry_id: UUID) -> list[EntryFragment]:
        return list(self.fragments.get(entry_id, []))

    def add_field(self, entry_field: EntryField) -> None:
        self.fields.setdefault(entry_field.entry_id, []).append(entry_field)

    def list_fields_for_entry(self, entry_id: UUID) -> list[EntryField]:
        return list(self.fields.get(entry_id, []))

    def update_field(self, entry_field: EntryField) -> None:
        bucket = self.fields.setdefault(entry_field.entry_id, [])
        for index, existing in enumerate(bucket):
            if existing.id == entry_field.id:
                bucket[index] = entry_field
                return

    def delete_field(self, field_id: UUID) -> None:
        for bucket in self.fields.values():
            bucket[:] = [f for f in bucket if f.id != field_id]

    def add_article_schema(self, schema: ArticleSchema) -> None:
        self.article_schemas[schema.id] = schema

    def get_article_schema(self, schema_id: UUID) -> ArticleSchema | None:
        return self.article_schemas.get(schema_id)


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


@dataclass
class FakeEntryExtractionQueue:
    snapshot: EntryExtractionSnapshot | None = None
    enqueued: tuple[UUID, UUID] | None = None
    returned_task_id: str = "extract-task-123"

    def enqueue_extraction(self, entry_id: UUID, actor_id: UUID) -> str:
        self.enqueued = (entry_id, actor_id)
        return self.returned_task_id

    def get_extraction_task(self, task_id: str) -> EntryExtractionSnapshot:
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


def _lexeme(
    dictionary_id: UUID, status: LexemeStatus = LexemeStatus.COMPLETE
) -> Lexeme:
    return Lexeme(
        id=uuid4(),
        dictionary_id=dictionary_id,
        page_id=uuid4(),
        source_text="слово",
        x=10,
        y=10,
        width=100,
        height=40,
        origin=LexemeOrigin.MANUAL,
        created_at=NOW,
        created_by=dictionary_id,
        updated_at=NOW,
        updated_by=dictionary_id,
        status=status,
    )


def _field(
    entry_id: UUID,
    fragment_id: UUID,
    field_path: str,
    role: EntryFieldRole = EntryFieldRole.MEANING,
    source_text: str = "значення",
    normalized_text: str | None = None,
) -> EntryField:
    return EntryField(
        id=uuid4(),
        entry_id=entry_id,
        fragment_id=fragment_id,
        field_path=field_path,
        role=role,
        position=0,
        source_text=source_text,
        normalized_text=normalized_text,
        source_start=0,
        source_end=8,
        origin=EntryFieldOrigin.MODEL,
        created_at=NOW,
        created_by=entry_id,
        updated_at=NOW,
        updated_by=entry_id,
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
        self.promote_service = PromoteLexemeToEntryService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            clock=lambda: NOW,
        )
        self.extraction_queue = FakeEntryExtractionQueue()
        self.extraction_service = QueueEntryFieldExtractionService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            queue=self.extraction_queue,
        )
        self.validate_service = ValidateEntryService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            clock=lambda: NOW,
        )
        self.query_service = EntryQueryService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
        )

    def add_entry(
        self,
        headword: str,
        *,
        dictionary_id: UUID | None = None,
        status: EntryStatus = EntryStatus.DRAFT,
        field_count: int = 0,
    ) -> DictionaryEntry:
        entry = DictionaryEntry(
            id=uuid4(),
            dictionary_id=dictionary_id or self.dictionary.id,
            lexeme_id=uuid4(),
            headword=headword,
            status=status,
            created_at=NOW,
            updated_at=NOW,
            created_by=self.owner_id,
            updated_by=self.owner_id,
            schema_id=None,
        )
        self.lexicography_repository.entries[entry.id] = entry
        for index in range(field_count):
            self.lexicography_repository.add_field(
                _field(entry.id, uuid4(), f"field_{index}")
            )
        return entry

    def add_lexeme(self, status: LexemeStatus = LexemeStatus.COMPLETE) -> Lexeme:
        lexeme = _lexeme(self.dictionary.id, status)
        self.lexicography_repository.lexemes[lexeme.id] = lexeme
        return lexeme

    def add_schema(self, definition: dict[str, object]) -> ArticleSchema:
        schema = ArticleSchema(
            id=uuid4(),
            dictionary_id=self.dictionary.id,
            version=1,
            status=SchemaGenerationStatus.READY,
            source_description="headword; meaning",
            definition=definition,
            created_at=NOW,
            created_by=self.owner_id,
            activated_at=NOW,
            activated_by=self.owner_id,
        )
        self.lexicography_repository.article_schemas[schema.id] = schema
        return schema


# --- PromoteLexemeToEntryService -------------------------------------------


def test_promote_creates_entry_and_one_fragment_from_the_lexeme() -> None:
    fixture = Fixture()
    lexeme = fixture.add_lexeme()

    entry = fixture.promote_service.create(
        fixture.dictionary.id, lexeme.id, fixture.owner_id
    )

    assert entry.lexeme_id == lexeme.id
    assert entry.headword == lexeme.source_text
    assert entry.status is EntryStatus.DRAFT
    fragments = fixture.lexicography_repository.list_fragments_for_entry(entry.id)
    assert len(fragments) == 1
    assert fragments[0].page_id == lexeme.page_id
    assert fragments[0].recognized_text == lexeme.source_text
    assert fragments[0].x == lexeme.x
    assert fragments[0].width == lexeme.width


def test_promote_rejects_a_non_complete_lexeme() -> None:
    fixture = Fixture()
    lexeme = fixture.add_lexeme(status=LexemeStatus.DRAFT)

    with pytest.raises(EntryValidationError):
        fixture.promote_service.create(
            fixture.dictionary.id, lexeme.id, fixture.owner_id
        )


def test_promote_twice_raises_duplicate_entry_error() -> None:
    fixture = Fixture()
    lexeme = fixture.add_lexeme()
    fixture.promote_service.create(fixture.dictionary.id, lexeme.id, fixture.owner_id)

    with pytest.raises(DuplicateEntryError):
        fixture.promote_service.create(
            fixture.dictionary.id, lexeme.id, fixture.owner_id
        )


def test_promote_actor_other_than_owner_raises_access_error() -> None:
    from cadmus.lexicography import LexemeAccessError

    fixture = Fixture()
    lexeme = fixture.add_lexeme()

    with pytest.raises(LexemeAccessError):
        fixture.promote_service.create(fixture.dictionary.id, lexeme.id, uuid4())


# --- QueueEntryFieldExtractionService ---------------------------------------


def test_extraction_enqueue_and_get_task_round_trip() -> None:
    fixture = Fixture()
    lexeme = fixture.add_lexeme()
    entry = fixture.promote_service.create(
        fixture.dictionary.id, lexeme.id, fixture.owner_id
    )

    task_id = fixture.extraction_service.enqueue(entry.id, fixture.owner_id)

    assert task_id == fixture.extraction_queue.returned_task_id
    assert fixture.extraction_queue.enqueued == (entry.id, fixture.owner_id)

    fixture.extraction_queue.snapshot = EntryExtractionSnapshot(
        task_id="t1", status=OcrSuggestionStatus.SUCCEEDED, created_fields=3
    )
    snapshot = fixture.extraction_service.get_task(entry.id, fixture.owner_id, "t1")
    assert snapshot.created_fields == 3


def test_extraction_enqueue_unknown_entry_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(EntryAccessError):
        fixture.extraction_service.enqueue(uuid4(), fixture.owner_id)


def test_extraction_get_returns_entry_fragments_and_fields() -> None:
    fixture = Fixture()
    lexeme = fixture.add_lexeme()
    entry = fixture.promote_service.create(
        fixture.dictionary.id, lexeme.id, fixture.owner_id
    )
    fragment = fixture.lexicography_repository.list_fragments_for_entry(entry.id)[0]
    a_field = _field(entry.id, fragment.id, "meaning")
    fixture.lexicography_repository.add_field(a_field)

    got_entry, fragments, fields = fixture.extraction_service.get(
        entry.id, fixture.owner_id
    )

    assert got_entry.id == entry.id
    assert len(fragments) == 1
    assert [f.id for f in fields] == [a_field.id]


# --- validate_entry_against_schema / ValidateEntryService -------------------


def _entry(dictionary_id: UUID, schema_id: UUID | None) -> DictionaryEntry:
    return DictionaryEntry(
        id=uuid4(),
        dictionary_id=dictionary_id,
        lexeme_id=uuid4(),
        headword="слово",
        status=EntryStatus.READY_TO_REVIEW,
        created_at=NOW,
        updated_at=NOW,
        created_by=dictionary_id,
        updated_by=dictionary_id,
        schema_id=schema_id,
    )


def test_validate_entry_against_schema_passes_when_required_fields_present() -> None:
    schema = ArticleSchema(
        id=uuid4(),
        dictionary_id=uuid4(),
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="",
        definition={
            "fields": [
                {"name": "headword", "role": "headword", "required": True},
                {
                    "name": "meaning",
                    "role": "meaning",
                    "required": True,
                    "repeatable": True,
                },
            ]
        },
        created_at=NOW,
        created_by=uuid4(),
    )
    entry = _entry(schema.dictionary_id, schema.id)
    fields = [
        _field(entry.id, uuid4(), "headword", EntryFieldRole.HEADWORD),
        _field(entry.id, uuid4(), "meaning[0]", EntryFieldRole.MEANING),
    ]

    errors = validate_entry_against_schema(entry, fields, schema)

    assert errors == {}


def test_validate_entry_against_schema_reports_missing_required_field() -> None:
    schema = ArticleSchema(
        id=uuid4(),
        dictionary_id=uuid4(),
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="",
        definition={
            "fields": [
                {"name": "headword", "role": "headword", "required": True},
                {"name": "meaning", "role": "meaning", "required": True},
            ]
        },
        created_at=NOW,
        created_by=uuid4(),
    )
    entry = _entry(schema.dictionary_id, schema.id)
    fields = [_field(entry.id, uuid4(), "headword", EntryFieldRole.HEADWORD)]

    errors = validate_entry_against_schema(entry, fields, schema)

    assert "meaning" in errors


def _typed_schema(node_type: str, options: list[str] | None = None) -> ArticleSchema:
    node: dict[str, object] = {"name": "attr", "role": "other", "type": node_type}
    if options is not None:
        node["options"] = options
    return ArticleSchema(
        id=uuid4(),
        dictionary_id=uuid4(),
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="",
        definition={"fields": [node]},
        created_at=NOW,
        created_by=uuid4(),
    )


def test_validate_entry_against_schema_rejects_value_outside_enum_options() -> None:
    schema = _typed_schema("enum", ["ч.", "ж.", "с."])  # noqa: RUF001
    entry = _entry(schema.dictionary_id, schema.id)
    fields = [
        _field(entry.id, uuid4(), "attr", EntryFieldRole.OTHER, source_text="мн.")
    ]

    errors = validate_entry_against_schema(entry, fields, schema)

    assert "attr" in errors


def test_validate_entry_against_schema_accepts_value_in_enum_options() -> None:
    schema = _typed_schema("enum", ["ч.", "ж.", "с."])  # noqa: RUF001
    entry = _entry(schema.dictionary_id, schema.id)
    fields = [_field(entry.id, uuid4(), "attr", EntryFieldRole.OTHER, source_text="ж.")]

    assert validate_entry_against_schema(entry, fields, schema) == {}


def test_validate_entry_against_schema_flags_non_numeric_number_field() -> None:
    schema = _typed_schema("number")
    entry = _entry(schema.dictionary_id, schema.id)
    fields = [
        _field(entry.id, uuid4(), "attr", EntryFieldRole.OTHER, source_text="кілька")
    ]

    assert "attr" in validate_entry_against_schema(entry, fields, schema)


def test_validate_entry_against_schema_flags_malformed_date_field() -> None:
    schema = _typed_schema("date")
    entry = _entry(schema.dictionary_id, schema.id)
    fields = [
        _field(entry.id, uuid4(), "attr", EntryFieldRole.OTHER, source_text="1917 рік")
    ]

    assert "attr" in validate_entry_against_schema(entry, fields, schema)


def test_validate_entry_against_schema_checks_normalized_text_over_source() -> None:
    schema = _typed_schema("enum", ["ч.", "ж.", "с."])  # noqa: RUF001
    entry = _entry(schema.dictionary_id, schema.id)
    fields = [
        _field(
            entry.id,
            uuid4(),
            "attr",
            EntryFieldRole.OTHER,
            source_text="ж.",
            normalized_text="не-опція",
        )
    ]

    assert "attr" in validate_entry_against_schema(entry, fields, schema)


def test_validate_service_blocks_completion_when_fields_missing() -> None:
    fixture = Fixture()
    schema = fixture.add_schema(
        {"fields": [{"name": "headword", "role": "headword", "required": True}]}
    )
    lexeme = fixture.add_lexeme()
    entry = fixture.promote_service.create(
        fixture.dictionary.id, lexeme.id, fixture.owner_id
    )
    entry.schema_id = schema.id
    fixture.lexicography_repository.update_entry(entry)

    with pytest.raises(EntryValidationError):
        fixture.validate_service.complete(
            fixture.dictionary.id, entry.id, fixture.owner_id
        )


def test_validate_service_allows_completion_when_schema_satisfied() -> None:
    fixture = Fixture()
    schema = fixture.add_schema(
        {"fields": [{"name": "headword", "role": "headword", "required": True}]}
    )
    lexeme = fixture.add_lexeme()
    entry = fixture.promote_service.create(
        fixture.dictionary.id, lexeme.id, fixture.owner_id
    )
    entry.schema_id = schema.id
    fixture.lexicography_repository.update_entry(entry)
    fragment = fixture.lexicography_repository.list_fragments_for_entry(entry.id)[0]
    fixture.lexicography_repository.add_field(
        _field(entry.id, fragment.id, "headword", EntryFieldRole.HEADWORD)
    )

    completed = fixture.validate_service.complete(
        fixture.dictionary.id, entry.id, fixture.owner_id
    )

    assert completed.status is EntryStatus.COMPLETE


# --- EntryQueryService ---------------------------------------------------------


def test_list_for_dictionary_returns_only_this_dictionary_ordered_by_headword() -> None:
    fixture = Fixture()
    other_dictionary = uuid4()
    fixture.add_entry("яблуко")
    fixture.add_entry("абетка")
    fixture.add_entry("мова")
    fixture.add_entry("чужа", dictionary_id=other_dictionary)

    rows = fixture.query_service.list_for_dictionary(
        fixture.dictionary.id, fixture.owner_id
    )

    assert [entry.headword for entry, _ in rows] == ["абетка", "мова", "яблуко"]


def test_list_for_dictionary_reports_the_field_count_per_entry() -> None:
    fixture = Fixture()
    fixture.add_entry("абетка", field_count=3)
    fixture.add_entry("мова", field_count=0)

    counts = {
        entry.headword: field_count
        for entry, field_count in fixture.query_service.list_for_dictionary(
            fixture.dictionary.id, fixture.owner_id
        )
    }

    assert counts == {"абетка": 3, "мова": 0}


def test_list_for_dictionary_is_empty_for_a_dictionary_without_entries() -> None:
    fixture = Fixture()

    assert (
        fixture.query_service.list_for_dictionary(
            fixture.dictionary.id, fixture.owner_id
        )
        == []
    )


def test_list_for_dictionary_denies_a_non_member() -> None:
    from cadmus.lexicography import LexemeAccessError

    fixture = Fixture()
    fixture.add_entry("абетка")

    with pytest.raises(LexemeAccessError):
        fixture.query_service.list_for_dictionary(fixture.dictionary.id, uuid4())
