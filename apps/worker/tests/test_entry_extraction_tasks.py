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
from cadmus.reference_lexicon import (
    ReferenceLemma,
    ReferenceLemmaMatch,
    ReferenceLexiconNotFoundError,
    ReferenceMatchType,
    normalize_ukrainian_text,
)
from cadmus.sources import (
    Dictionary,
    DictionaryPage,
    DictionarySettlementMapping,
    DictionaryStatus,
    SettlementMappingStatus,
    SourcesRepository,
)
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

    def update_field(self, entry_field: EntryField) -> None:
        bucket = self.fields.setdefault(entry_field.entry_id, [])
        for index, existing in enumerate(bucket):
            if existing.id == entry_field.id:
                bucket[index] = entry_field
                return
        bucket.append(entry_field)

    def delete_field(self, field_id: UUID) -> None:
        for bucket in self.fields.values():
            bucket[:] = [f for f in bucket if f.id != field_id]

    def update_fragment(self, fragment: EntryFragment) -> None:
        bucket = self.fragments.setdefault(fragment.entry_id, [])
        for index, existing in enumerate(bucket):
            if existing.id == fragment.id:
                bucket[index] = fragment
                return
        bucket.append(fragment)


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


class FakeDictionaryPages:
    """Minimal stand-in for ``GetDictionaryService`` -- only the two lookups
    ``_refresh_fragment_text``/the task body use."""

    def __init__(self, dictionary: Dictionary, page: DictionaryPage) -> None:
        self.dictionary = dictionary
        self.page = page

    def get(self, dictionary_id: UUID, actor_id: UUID, **kwargs: object) -> Dictionary:
        return self.dictionary

    def get_page_by_id(
        self, dictionary_id: UUID, actor_id: UUID, page_id: UUID
    ) -> DictionaryPage | None:
        return self.page if page_id == self.page.id else None


class FakeObjectStorage:
    """Minimal stand-in for ``ObjectStorage`` -- ``download`` only, since
    re-OCR never uploads or deletes."""

    def __init__(self, *, missing: bool = False) -> None:
        self.missing = missing
        self.downloaded_keys: list[str] = []

    def download(self, key: str, destination: object) -> None:
        from cadmus.sources import ObjectNotFoundError

        self.downloaded_keys.append(key)
        if self.missing:
            raise ObjectNotFoundError(key)
        destination.write(b"fake-png-bytes")  # type: ignore[attr-defined]


class FakeOcrProvider:
    """Minimal stand-in for ``TesseractAltoOcrProvider`` -- returns no
    segments by default, so ``_refresh_fragment_text`` falls back to the
    fragment's existing ``recognized_text`` and every pre-existing test's
    fixed ``fragment_text`` still reaches the AI provider unchanged."""

    def __init__(self, *, text: str | None = None, fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.calls: list[tuple[list[tuple[float, float, float, float]], str]] = []

    def suggest_words(self, image_bytes: bytes, language: str) -> list[object]:
        raise AssertionError("not used by extraction")

    def segment_region(
        self,
        image_bytes: bytes,
        boxes: list[tuple[float, float, float, float]],
        language: str,
    ) -> list[object]:
        from cadmus.infrastructure.ocr import OcrExecutionError
        from cadmus.lexicography import FragmentSegment

        self.calls.append((list(boxes), language))
        if self.fail:
            raise OcrExecutionError("tesseract failed")
        if self.text is None:
            return []
        return [
            FragmentSegment(
                index=0, text=self.text, x=0, y=0, width=1, height=1, confidence=1.0
            )
        ]


def _page(page_id: UUID) -> DictionaryPage:
    return DictionaryPage(
        id=page_id,
        source_file_id=uuid4(),
        page_index=0,
        processed_asset_key="sources/x/pages/00001.png",
        width=1000,
        height=1000,
        checksum_sha256="0" * 64,
        created_at=NOW,
    )


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
        reference_lexicon_query: object | None = None,
        ocr_text: str | None = None,
        ocr_fails: bool = False,
        object_storage_missing: bool = False,
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

        self.page = _page(self.fragment.page_id)
        self.dictionary_pages = FakeDictionaryPages(self.dictionary, self.page)
        self.object_storage = FakeObjectStorage(missing=object_storage_missing)
        self.ocr_provider = FakeOcrProvider(text=ocr_text, fail=ocr_fails)

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
            dictionary_pages=self.dictionary_pages,  # type: ignore[arg-type]
            object_storage=self.object_storage,  # type: ignore[arg-type]
            ocr_provider=self.ocr_provider,  # type: ignore[arg-type]
            ai_schema_provider=self.provider,  # type: ignore[arg-type]
            annotation_service=annotation_service,
            reference_lexicon_query=reference_lexicon_query,  # type: ignore[arg-type]
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

    def stored_fragment(self) -> EntryFragment:
        return next(
            f
            for f in self.lexicography_repository.list_fragments_for_entry(
                self.entry.id
            )
            if f.id == self.fragment.id
        )


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


def test_extract_entry_fields_re_ocrs_the_fragment_before_extracting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fragment trimmed down to just the headword (e.g. by an editor) gets
    a fresh chance at its full text every time extraction runs."""
    fresh_text = "КИРИНЯ, -і, ж. Безладдя, бруд."  # noqa: RUF001
    fixture = Fixture(fragment_text="КИРИНЯ", ocr_text=fresh_text)
    fixture.install(monkeypatch)

    result = fixture.run("task-reocr-1")

    assert result["status"] == "succeeded"
    assert fixture.provider.received_text == fresh_text
    assert fixture.stored_fragment().recognized_text == fresh_text
    assert fixture.ocr_provider.calls == [([(0.0, 0.0, 100.0, 40.0)], "ukr+eng")]


def test_extract_entry_fields_falls_back_to_old_text_on_ocr_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(fragment_text=FRAGMENT_TEXT, ocr_fails=True)
    fixture.install(monkeypatch)

    result = fixture.run("task-reocr-2")

    assert result["status"] == "succeeded"
    assert fixture.provider.received_text == FRAGMENT_TEXT
    assert fixture.stored_fragment().recognized_text == FRAGMENT_TEXT


def test_extract_entry_fields_falls_back_to_old_text_when_page_image_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(fragment_text=FRAGMENT_TEXT, object_storage_missing=True)
    fixture.install(monkeypatch)

    result = fixture.run("task-reocr-3")

    assert result["status"] == "succeeded"
    assert fixture.provider.received_text == FRAGMENT_TEXT
    assert fixture.stored_fragment().recognized_text == FRAGMENT_TEXT


def test_extract_entry_fields_falls_back_to_old_text_when_re_ocr_finds_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(fragment_text=FRAGMENT_TEXT, ocr_text=None)
    fixture.install(monkeypatch)

    result = fixture.run("task-reocr-4")

    assert result["status"] == "succeeded"
    assert fixture.provider.received_text == FRAGMENT_TEXT
    assert fixture.stored_fragment().recognized_text == FRAGMENT_TEXT


class FakeReferenceLexiconQuery:
    """Minimal stand-in for ``ReferenceLexiconQueryService`` -- only ``search``
    is used, and only its ``lemma.normalized_lemma`` field is read."""

    def __init__(self, known: set[str] | None = None, *, missing: bool = False) -> None:
        self._known = {normalize_ukrainian_text(word) for word in known or set()}
        self._missing = missing
        self.queries: list[str] = []

    def search(
        self, code: str, query: str, *, standard_only: bool = True, limit: int = 20
    ) -> list[ReferenceLemmaMatch]:
        self.queries.append(query)
        if self._missing:
            raise ReferenceLexiconNotFoundError(code)
        normalized = normalize_ukrainian_text(query)
        if normalized not in self._known:
            return []
        lemma = ReferenceLemma(
            id=uuid4(),
            lexicon_id=uuid4(),
            external_key=normalized,
            lemma=query,
            normalized_lemma=normalized,
            part_of_speech="noun",
            key_tags=[],
            is_standard=True,
        )
        return [ReferenceLemmaMatch(lemma=lemma, match_type=ReferenceMatchType.LEMMA)]


_MEANING_DEFINITION: dict[str, object] = {
    "fields": [{"name": "meaning", "role": "meaning", "type": "string"}]
}


def test_extract_rejoins_line_break_hyphen_into_normalized_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = "Клинок під пахвою у жіночій сорочці, ко- жусі тощо."  # noqa: RUF001
    fixture = Fixture(
        definition=_MEANING_DEFINITION,
        fragment_text=raw,
        items=[ExtractedField("meaning", EntryFieldRole.MEANING, raw, 0.9)],
        reference_lexicon_query=FakeReferenceLexiconQuery({"кожусі"}),
    )
    fixture.install(monkeypatch)

    fixture.run("task-hy1")

    stored = fixture.stored_fields()[0]
    # verbatim span + offsets stay on the untouched OCR text ...
    assert stored.source_text == raw
    assert (stored.source_start, stored.source_end) == (0, len(raw))
    # ... the rejoined form is what the presentation formula will read.
    assert stored.normalized_text == (
        "Клинок під пахвою у жіночій сорочці, кожусі тощо."  # noqa: RUF001
    )
    assert stored.confidence == 0.9  # VESUM confirmed the join


def test_extract_keeps_hyphen_for_a_known_compound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = "мова військово- політичний устрій"
    fixture = Fixture(
        definition=_MEANING_DEFINITION,
        fragment_text=raw,
        items=[ExtractedField("meaning", EntryFieldRole.MEANING, raw, 0.9)],
        reference_lexicon_query=FakeReferenceLexiconQuery({"військово-політичний"}),
    )
    fixture.install(monkeypatch)

    fixture.run("task-hy2")

    stored = fixture.stored_fields()[0]
    assert stored.normalized_text == "мова військово-політичний устрій"
    assert stored.confidence == 0.9


def test_extract_lowers_confidence_for_an_unresolved_hyphen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = "щось незнай- оме тут"
    fixture = Fixture(
        definition=_MEANING_DEFINITION,
        fragment_text=raw,
        items=[ExtractedField("meaning", EntryFieldRole.MEANING, raw, 0.95)],
        reference_lexicon_query=FakeReferenceLexiconQuery(set()),
    )
    fixture.install(monkeypatch)

    fixture.run("task-hy3")

    stored = fixture.stored_fields()[0]
    assert stored.normalized_text == "щось незнайоме тут"
    assert stored.confidence == 0.5  # flagged for the editor's warning badge


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


def test_extract_entry_fields_links_a_geographic_label_to_its_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = Fixture(
        definition={
            "fields": [{"name": "place", "role": "geographic_label", "type": "string"}]
        },
        fragment_text="Атаки Хот.",
        items=[ExtractedField("place", EntryFieldRole.GEOGRAPHIC_LABEL, "Атаки", 0.9)],
    )
    mapping = DictionarySettlementMapping(
        id=uuid4(),
        dictionary_id=fixture.dictionary.id,
        source_label="Атаки",
        status=SettlementMappingStatus.CONFIRMED,
        created_at=NOW,
        updated_at=NOW,
        created_by=fixture.dictionary.owner_id,
        updated_by=fixture.dictionary.owner_id,
        modern_settlement_name="Атаки",
        community_name="Хотинська територіальна громада",
        district="Хот.",
    )
    fixture.sources_repository.settlements[fixture.dictionary.id] = [mapping]
    fixture.install(monkeypatch)

    fixture.run("task-geo")

    geo = next(
        f for f in fixture.stored_fields() if f.role is EntryFieldRole.GEOGRAPHIC_LABEL
    )
    assert geo.settlement_mapping_id == mapping.id
    assert geo.normalized_text == "Атаки"
