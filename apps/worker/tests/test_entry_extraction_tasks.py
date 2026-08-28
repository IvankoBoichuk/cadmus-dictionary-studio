"""Celery task: AI entry field extraction (BH-148, ALTO segmentation variant 1)."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import BinaryIO, cast
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
    FragmentSegment,
    LexicographyRepository,
    RuleBasedAnnotationService,
    SchemaGenerationStatus,
)
from cadmus.sources import (
    Dictionary,
    DictionaryPage,
    DictionaryStatus,
    ObjectNotFoundError,
    SourcesRepository,
)
from cadmus_worker import entry_extraction_tasks
from cadmus_worker.entry_extraction_tasks import (
    _EntryExtractionDependencies,
    extract_entry_fields,
)

NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)

_SEGMENTS = [
    FragmentSegment(
        index=0, text="слово", x=0, y=0, width=40, height=10, confidence=0.9
    ),
    FragmentSegment(
        index=1, text="означає", x=45, y=0, width=50, height=10, confidence=0.9
    ),
    FragmentSegment(
        index=2, text="щось", x=100, y=0, width=30, height=10, confidence=0.9
    ),
]


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    pages: dict[UUID, DictionaryPage] = field(default_factory=dict)
    abbreviations: dict[UUID, list[object]] = field(default_factory=dict)
    settlements: dict[UUID, list[object]] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_page_by_id(self, page_id: UUID) -> DictionaryPage | None:
        return self.pages.get(page_id)

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


@dataclass
class FakeObjectStorage:
    uploaded: dict[str, bytes] = field(default_factory=dict)

    def upload(
        self, key: str, source: BinaryIO, length: int, content_type: str
    ) -> None:
        raise AssertionError("not used by extraction")

    def download(self, key: str, destination: BinaryIO) -> None:
        if key not in self.uploaded:
            raise ObjectNotFoundError(key)
        destination.write(self.uploaded[key])

    def delete(self, key: str) -> None:
        raise AssertionError("not used by extraction")

    def delete_prefix(self, prefix: str) -> None:
        raise AssertionError("not used by extraction")


class FakeOcrProvider:
    def __init__(self, *, segments: list[FragmentSegment] | None = _SEGMENTS) -> None:
        self.segments = segments
        self.calls: list[tuple[bytes, object, str]] = []

    def segment_region(
        self, image_bytes: bytes, boxes: object, language: str
    ) -> list[FragmentSegment]:
        self.calls.append((image_bytes, boxes, language))
        return list(self.segments or [])


class FakeAiSchemaProvider:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.received_segments: list[FragmentSegment] | None = None

    def generate_schema(self, article_description: str):  # type: ignore[no-untyped-def]
        raise AssertionError("not used by extraction")

    def extract_fields(self, schema: ArticleSchema, segments):  # type: ignore[no-untyped-def]
        from cadmus.infrastructure.ai_schema import AiSchemaProviderError

        self.received_segments = list(segments)
        if self.fail:
            raise AiSchemaProviderError("provider unavailable")
        return [
            ExtractedField(
                field_path="headword",
                role=EntryFieldRole.HEADWORD,
                value=segments[0].text,
                segment_start=0,
                segment_end=1,
                confidence=0.9,
            )
        ]


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


def _page() -> DictionaryPage:
    return DictionaryPage(
        id=uuid4(),
        source_file_id=uuid4(),
        page_index=0,
        processed_asset_key="pages/0.png",
        width=1000,
        height=1400,
        checksum_sha256="checksum",
        created_at=NOW,
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


def _fragment(entry_id: UUID, page_id: UUID) -> EntryFragment:
    return EntryFragment(
        id=uuid4(),
        entry_id=entry_id,
        page_id=page_id,
        x=0,
        y=0,
        width=100,
        height=40,
        reading_order=0,
        recognized_text="слово означає щось важливе",
    )


def _schema(dictionary_id: UUID) -> ArticleSchema:
    return ArticleSchema(
        id=uuid4(),
        dictionary_id=dictionary_id,
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="headword",
        definition={"fields": [{"name": "headword", "role": "headword"}]},
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
        segments: list[FragmentSegment] | None = _SEGMENTS,
        page_image_missing: bool = False,
    ) -> None:
        self.sources_repository = MemorySourcesRepository()
        self.lexicography_repository = MemoryLexicographyRepository()
        self.provider = FakeAiSchemaProvider(fail=provider_fails)
        self.ocr_provider = FakeOcrProvider(segments=segments)
        self.object_storage = FakeObjectStorage()

        self.dictionary = _dictionary()
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary
        self.page = _page()
        self.sources_repository.pages[self.page.id] = self.page
        if not page_image_missing:
            self.object_storage.uploaded[self.page.processed_asset_key] = b"fake-png"
        self.entry = _entry(self.dictionary.id)
        self.lexicography_repository.entries[self.entry.id] = self.entry
        self.fragment = _fragment(self.entry.id, self.page.id)
        self.lexicography_repository.fragments[self.entry.id] = [self.fragment]
        self.schema = _schema(self.dictionary.id)
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
            object_storage=self.object_storage,
            ocr_provider=self.ocr_provider,  # type: ignore[arg-type]
            ai_schema_provider=self.provider,  # type: ignore[arg-type]
            annotation_service=annotation_service,
        )

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            entry_extraction_tasks, "_entry_extraction_dependencies", lambda: self._deps
        )


def test_extract_entry_fields_persists_model_fields_with_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture()
    fixture.install(monkeypatch)

    result = extract_entry_fields.apply(
        args=[str(fixture.entry.id), str(fixture.entry.created_by)], task_id="task-1"
    ).get()

    assert result["status"] == "succeeded"
    fields = fixture.lexicography_repository.list_fields_for_entry(fixture.entry.id)
    assert len(fields) == 1
    stored = fields[0]
    assert stored.origin is EntryFieldOrigin.MODEL
    assert stored.fragment_id == fixture.fragment.id
    # union of segments 0 and 1: x in [0, 45+50) -> width 95, height 10
    assert stored.source_text == "слово означає"
    assert (stored.x, stored.y, stored.width, stored.height) == (0, 0, 95, 10)
    assert stored.source_start is None
    assert stored.source_end is None
    stored_entry = fixture.lexicography_repository.entries[fixture.entry.id]
    assert stored_entry.status is EntryStatus.READY_TO_REVIEW
    assert stored_entry.schema_id == fixture.schema.id


def test_extract_entry_fields_skips_a_failed_fragment_without_crashing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(provider_fails=True)
    fixture.install(monkeypatch)

    result = extract_entry_fields.apply(
        args=[str(fixture.entry.id), str(fixture.entry.created_by)], task_id="task-2"
    ).get()

    assert result["status"] == "succeeded"
    assert result["created_fields"] == 0
    assert fixture.lexicography_repository.list_fields_for_entry(fixture.entry.id) == []
    # status still advances even though extraction produced nothing
    assert (
        fixture.lexicography_repository.entries[fixture.entry.id].status
        is EntryStatus.READY_TO_REVIEW
    )


def test_extract_entry_fields_skips_a_fragment_with_no_ocr_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(segments=[])
    fixture.install(monkeypatch)

    result = extract_entry_fields.apply(
        args=[str(fixture.entry.id), str(fixture.entry.created_by)], task_id="task-2b"
    ).get()

    assert result["status"] == "succeeded"
    assert result["created_fields"] == 0
    assert fixture.provider.received_segments is None


def test_extract_entry_fields_skips_a_fragment_with_a_missing_page_image(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(page_image_missing=True)
    fixture.install(monkeypatch)

    result = extract_entry_fields.apply(
        args=[str(fixture.entry.id), str(fixture.entry.created_by)], task_id="task-2c"
    ).get()

    assert result["status"] == "succeeded"
    assert result["created_fields"] == 0
    assert fixture.provider.received_segments is None


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

    result = extract_entry_fields.apply(
        args=[str(fixture.entry.id), str(fixture.entry.created_by)], task_id="task-4"
    ).get()

    assert result["status"] == "failed"
    assert result["error"] == "no active article schema"
