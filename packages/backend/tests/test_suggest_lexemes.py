"""OCR word-suggestion domain and application behavior."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    Lexeme,
    LexemeAccessError,
    LexemeOrigin,
    LexemePageNotFoundError,
    LexemeSuggestion,
    OcrSuggestionStatus,
    OcrSuggestionTaskSnapshot,
    SuggestLexemesService,
    resolve_ocr_language,
)
from cadmus.sources import (
    Dictionary,
    DictionaryLanguage,
    DictionaryPage,
    DictionaryPageRange,
    DictionaryStatus,
    GetDictionaryService,
    InspectionStatus,
    SourceFile,
)

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


def test_resolve_ocr_language_maps_known_codes() -> None:
    assert resolve_ocr_language(["uk"]) == "ukr"
    assert resolve_ocr_language(["uk", "ru"]) == "ukr+rus"


def test_resolve_ocr_language_deduplicates_preserving_order() -> None:
    assert resolve_ocr_language(["uk", "uk", "en"]) == "ukr+eng"


def test_resolve_ocr_language_falls_back_when_empty() -> None:
    assert resolve_ocr_language([]) == "ukr+eng"


def test_resolve_ocr_language_falls_back_when_unmapped() -> None:
    assert resolve_ocr_language(["zz"]) == "ukr+eng"


def test_resolve_ocr_language_skips_unmapped_alongside_mapped() -> None:
    assert resolve_ocr_language(["zz", "uk"]) == "ukr"


@dataclass
class MemorySourcesRepository:
    """A minimal fake covering only what ``GetDictionaryService`` needs here."""

    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    page_ranges: dict[UUID, list[DictionaryPageRange]] = field(default_factory=dict)
    pages: dict[tuple[UUID, int], DictionaryPage] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        return self.source_files.get(dictionary_id)

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]:
        return list(self.page_ranges.get(dictionary_id, []))

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        return self.pages.get((source_file_id, page_index))


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = repository

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

    def list_lexemes_for_page(self, page_id: UUID) -> list[Lexeme]:
        return [lexeme for lexeme in self.lexemes.values() if lexeme.page_id == page_id]


class MemoryLexicographyUnitOfWork:
    def __init__(self, repository: MemoryLexicographyRepository) -> None:
        self.lexicography = repository

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
class FakeOcrSuggestionQueue:
    snapshot: OcrSuggestionTaskSnapshot | None = None
    enqueued: tuple[UUID, UUID, str] | None = None
    returned_task_id: str = "task-123"

    def enqueue_suggestions(
        self, source_file_id: UUID, page_id: UUID, language: str
    ) -> str:
        self.enqueued = (source_file_id, page_id, language)
        return self.returned_task_id

    def get_suggestions_task(self, task_id: str) -> OcrSuggestionTaskSnapshot:
        assert self.snapshot is not None
        return self.snapshot


def _dictionary(owner_id: UUID, language_codes: list[str] | None = None) -> Dictionary:
    dictionary = Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )
    dictionary.languages = [
        DictionaryLanguage(
            id=uuid4(), dictionary_id=dictionary.id, language_code=code, position=i
        )
        for i, code in enumerate(language_codes or [])
    ]
    return dictionary


def _source_file(dictionary_id: UUID, **overrides: object) -> SourceFile:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": dictionary_id,
        "original_filename": "dictionary.pdf",
        "mime_type": "application/pdf",
        "byte_size": 1024,
        "checksum_sha256": "a" * 64,
        "storage_key": f"sources/{dictionary_id}/file.pdf",
        "uploaded_at": NOW,
        "uploaded_by": dictionary_id,
        "inspection_status": InspectionStatus.VERIFIED,
        "page_count": 400,
    }
    defaults.update(overrides)
    return SourceFile(**defaults)  # type: ignore[arg-type]


def _page(source_file_id: UUID, page_index: int) -> DictionaryPage:
    return DictionaryPage(
        id=uuid4(),
        source_file_id=source_file_id,
        page_index=page_index,
        processed_asset_key=f"sources/x/pages/{page_index:05d}.png",
        width=1000,
        height=1400,
        checksum_sha256="b" * 64,
        created_at=NOW,
    )


def _lexeme(dictionary_id: UUID, page_id: UUID, x: float, y: float) -> Lexeme:
    return Lexeme(
        id=uuid4(),
        dictionary_id=dictionary_id,
        page_id=page_id,
        source_text="існуюче",
        x=x,
        y=y,
        width=100,
        height=40,
        origin=LexemeOrigin.MANUAL,
        created_at=NOW,
        created_by=uuid4(),
        updated_at=NOW,
        updated_by=uuid4(),
    )


def _suggestion(x: float = 10, y: float = 10, text: str = "слово") -> LexemeSuggestion:
    return LexemeSuggestion(
        source_text=text, x=x, y=y, width=100, height=40, confidence=0.9
    )


class Fixture:
    """A dictionary with one viewable page, no lexemes yet."""

    def __init__(self, language_codes: list[str] | None = None) -> None:
        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id, language_codes)
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary
        self.source_file = _source_file(self.dictionary.id)
        self.sources_repository.source_files[self.dictionary.id] = self.source_file
        self.sources_repository.page_ranges[self.dictionary.id] = [
            DictionaryPageRange(
                id=uuid4(),
                dictionary_id=self.dictionary.id,
                start_page=1,
                end_page=1,
                position=0,
            )
        ]
        self.page = _page(self.source_file.id, page_index=0)
        self.sources_repository.pages[(self.source_file.id, 0)] = self.page

        self.dictionary_pages = GetDictionaryService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.lexicography_repository = MemoryLexicographyRepository()
        self.queue = FakeOcrSuggestionQueue()
        self.service = SuggestLexemesService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            queue=self.queue,
        )

    def add_lexeme(self, x: float, y: float) -> None:
        lexeme = _lexeme(self.dictionary.id, self.page.id, x, y)
        self.lexicography_repository.lexemes[lexeme.id] = lexeme


def test_enqueue_passes_the_page_s_source_file_and_page_id() -> None:
    fixture = Fixture()

    task_id = fixture.service.enqueue(fixture.dictionary.id, fixture.owner_id, 1)

    assert task_id == fixture.queue.returned_task_id
    assert fixture.queue.enqueued == (
        fixture.source_file.id,
        fixture.page.id,
        "ukr+eng",
    )


def test_enqueue_resolves_language_from_dictionary_languages() -> None:
    fixture = Fixture(language_codes=["uk"])

    fixture.service.enqueue(fixture.dictionary.id, fixture.owner_id, 1)

    assert fixture.queue.enqueued is not None
    assert fixture.queue.enqueued[2] == "ukr"


def test_enqueue_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.service.enqueue(fixture.dictionary.id, uuid4(), 1)


def test_enqueue_out_of_range_page_raises_page_not_found() -> None:
    fixture = Fixture()

    with pytest.raises(LexemePageNotFoundError):
        fixture.service.enqueue(fixture.dictionary.id, fixture.owner_id, 99)


def test_get_task_passes_through_queued_status() -> None:
    fixture = Fixture()
    fixture.queue.snapshot = OcrSuggestionTaskSnapshot(
        task_id="t1", status=OcrSuggestionStatus.QUEUED
    )

    snapshot = fixture.service.get_task(
        fixture.dictionary.id, fixture.owner_id, 1, "t1"
    )

    assert snapshot.status is OcrSuggestionStatus.QUEUED
    assert snapshot.suggestions is None


def test_get_task_passes_through_failure() -> None:
    fixture = Fixture()
    fixture.queue.snapshot = OcrSuggestionTaskSnapshot(
        task_id="t1", status=OcrSuggestionStatus.FAILED, error="boom"
    )

    snapshot = fixture.service.get_task(
        fixture.dictionary.id, fixture.owner_id, 1, "t1"
    )

    assert snapshot.status is OcrSuggestionStatus.FAILED
    assert snapshot.error == "boom"


def test_get_task_filters_out_suggestions_overlapping_existing_lexemes() -> None:
    fixture = Fixture()
    fixture.add_lexeme(x=10, y=10)
    fixture.queue.snapshot = OcrSuggestionTaskSnapshot(
        task_id="t1",
        status=OcrSuggestionStatus.SUCCEEDED,
        suggestions=(
            _suggestion(x=12, y=11, text="перетинається"),
            _suggestion(x=500, y=500, text="окреме"),
        ),
    )

    snapshot = fixture.service.get_task(
        fixture.dictionary.id, fixture.owner_id, 1, "t1"
    )

    assert snapshot.suggestions is not None
    assert [s.source_text for s in snapshot.suggestions] == ["окреме"]


def test_get_task_keeps_all_suggestions_when_no_lexemes_exist_yet() -> None:
    fixture = Fixture()
    fixture.queue.snapshot = OcrSuggestionTaskSnapshot(
        task_id="t1",
        status=OcrSuggestionStatus.SUCCEEDED,
        suggestions=(_suggestion(), _suggestion(x=200, text="інше")),
    )

    snapshot = fixture.service.get_task(
        fixture.dictionary.id, fixture.owner_id, 1, "t1"
    )

    assert snapshot.suggestions is not None
    assert len(snapshot.suggestions) == 2


def test_get_task_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.service.get_task(fixture.dictionary.id, uuid4(), 1, "t1")


def test_get_task_out_of_range_page_raises_page_not_found() -> None:
    fixture = Fixture()

    with pytest.raises(LexemePageNotFoundError):
        fixture.service.get_task(fixture.dictionary.id, fixture.owner_id, 99, "t1")
