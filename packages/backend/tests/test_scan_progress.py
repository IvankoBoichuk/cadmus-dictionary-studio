"""BH-57: dictionary scan-progress domain and application behavior."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    Lexeme,
    LexemeAccessError,
    LexemeEvent,
    LexemeOrigin,
    LexicographyRepository,
    ScanProgressService,
)
from cadmus.sources import (
    Dictionary,
    DictionaryPage,
    DictionaryPageRange,
    DictionaryStatus,
    GetDictionaryService,
    InspectionStatus,
    SourceFile,
    SourcesRepository,
)

NOW = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


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

    def list_pages(self, source_file_id: UUID) -> list[DictionaryPage]:
        return sorted(
            (p for (sfid, _), p in self.pages.items() if sfid == source_file_id),
            key=lambda p: p.page_index,
        )


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
    events: list[LexemeEvent] = field(default_factory=list)

    def add_lexeme(self, lexeme: Lexeme) -> None:
        self.lexemes[lexeme.id] = lexeme

    def list_page_ids_with_lexemes(self, dictionary_id: UUID) -> set[UUID]:
        return {
            lexeme.page_id
            for lexeme in self.lexemes.values()
            if lexeme.dictionary_id == dictionary_id
        }

    def has_any_lexeme(self, dictionary_id: UUID) -> bool:
        return any(
            lexeme.dictionary_id == dictionary_id for lexeme in self.lexemes.values()
        )


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


def _dictionary(owner_id: UUID) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


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


def _page_range(dictionary_id: UUID, start: int, end: int) -> DictionaryPageRange:
    return DictionaryPageRange(
        id=uuid4(),
        dictionary_id=dictionary_id,
        start_page=start,
        end_page=end,
        position=0,
    )


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


def _lexeme(dictionary_id: UUID, page_id: UUID) -> Lexeme:
    return Lexeme(
        id=uuid4(),
        dictionary_id=dictionary_id,
        page_id=page_id,
        source_text="слово",
        x=10,
        y=10,
        width=100,
        height=40,
        origin=LexemeOrigin.MANUAL,
        created_at=NOW,
        created_by=uuid4(),
        updated_at=NOW,
        updated_by=uuid4(),
    )


class Fixture:
    """A dictionary with 3 viewable pages (indices 0-2), no lexemes yet."""

    def __init__(self, page_count: int = 3) -> None:
        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id)
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary
        self.source_file = _source_file(self.dictionary.id)
        self.sources_repository.source_files[self.dictionary.id] = self.source_file
        self.sources_repository.page_ranges[self.dictionary.id] = [
            _page_range(self.dictionary.id, 1, page_count)
        ]
        self.pages = [
            _page(self.source_file.id, page_index=i) for i in range(page_count)
        ]
        for page in self.pages:
            self.sources_repository.pages[(self.source_file.id, page.page_index)] = page

        self.dictionary_pages = GetDictionaryService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.lexicography_repository = MemoryLexicographyRepository()
        self.service = ScanProgressService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
        )

    def add_lexeme_on_page(self, page_number: int) -> None:
        page = self.pages[page_number - 1]
        lexeme = _lexeme(self.dictionary.id, page.id)
        self.lexicography_repository.add_lexeme(lexeme)


def test_get_progress_with_no_lexemes_reports_nothing_processed() -> None:
    fixture = Fixture()

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.total_pages == 3
    assert progress.processed_pages == 0
    assert [p.has_lexemes for p in progress.pages] == [False, False, False]


def test_get_progress_marks_only_pages_with_at_least_one_lexeme() -> None:
    fixture = Fixture()
    fixture.add_lexeme_on_page(1)
    fixture.add_lexeme_on_page(3)

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.processed_pages == 2
    assert [p.has_lexemes for p in progress.pages] == [True, False, True]


def test_get_progress_page_numbers_match_viewer_ordinals() -> None:
    fixture = Fixture()

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert [p.page_number for p in progress.pages] == [1, 2, 3]


def test_get_progress_multiple_lexemes_on_one_page_count_it_once() -> None:
    fixture = Fixture()
    fixture.add_lexeme_on_page(2)
    fixture.add_lexeme_on_page(2)

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.processed_pages == 1
    assert progress.pages[1].has_lexemes is True


def test_get_progress_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.service.get_progress(fixture.dictionary.id, uuid4())


def test_get_progress_missing_dictionary_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.service.get_progress(uuid4(), fixture.owner_id)


def test_get_progress_without_saved_ranges_is_empty() -> None:
    fixture = Fixture()
    fixture.sources_repository.page_ranges[fixture.dictionary.id] = []

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.total_pages == 0
    assert progress.processed_pages == 0
    assert progress.pages == ()
