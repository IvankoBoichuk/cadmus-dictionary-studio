"""BH-57: dictionary scan-progress domain and application behavior."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    DictionaryEntry,
    EntryStatus,
    Lexeme,
    LexemeAccessError,
    LexemeEvent,
    LexemeOrigin,
    LexemeStatus,
    LexicographyRepository,
    ScanProgressService,
)
from cadmus.sources import (
    AdvanceDictionaryProcessingStatusService,
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
    events: list[object] = field(default_factory=list)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_event(self, event: object) -> None:
        self.events.append(event)

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
    entries: dict[UUID, DictionaryEntry] = field(default_factory=dict)
    events: list[LexemeEvent] = field(default_factory=list)

    def add_lexeme(self, lexeme: Lexeme) -> None:
        self.lexemes[lexeme.id] = lexeme

    def add_entry(self, entry: DictionaryEntry) -> None:
        self.entries[entry.id] = entry

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

    def count_lexemes_by_status(self, dictionary_id: UUID) -> dict[LexemeStatus, int]:
        counts: dict[LexemeStatus, int] = {}
        for lexeme in self.lexemes.values():
            if lexeme.dictionary_id == dictionary_id:
                counts[lexeme.status] = counts.get(lexeme.status, 0) + 1
        return counts

    def count_entries_by_status(self, dictionary_id: UUID) -> dict[EntryStatus, int]:
        counts: dict[EntryStatus, int] = {}
        for entry in self.entries.values():
            if entry.dictionary_id == dictionary_id:
                counts[entry.status] = counts.get(entry.status, 0) + 1
        return counts


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


def _dictionary(
    owner_id: UUID, status: DictionaryStatus = DictionaryStatus.DRAFT
) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=status,
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


def _lexeme(
    dictionary_id: UUID,
    page_id: UUID,
    status: LexemeStatus = LexemeStatus.DRAFT,
) -> Lexeme:
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
        status=status,
        created_at=NOW,
        created_by=uuid4(),
        updated_at=NOW,
        updated_by=uuid4(),
    )


def _entry(dictionary_id: UUID, status: EntryStatus) -> DictionaryEntry:
    return DictionaryEntry(
        id=uuid4(),
        dictionary_id=dictionary_id,
        lexeme_id=uuid4(),
        headword="слово",
        status=status,
        created_at=NOW,
        updated_at=NOW,
        created_by=uuid4(),
        updated_by=uuid4(),
    )


class Fixture:
    """A dictionary with 3 viewable pages (indices 0-2), no lexemes yet."""

    def __init__(
        self,
        page_count: int = 3,
        status: DictionaryStatus = DictionaryStatus.DRAFT,
    ) -> None:
        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id, status)
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
        self.status_service = AdvanceDictionaryProcessingStatusService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            ),
            clock=lambda: NOW,
        )
        self.lexicography_repository = MemoryLexicographyRepository()
        self.service = ScanProgressService(
            unit_of_work_factory=lambda: MemoryLexicographyUnitOfWork(
                self.lexicography_repository
            ),
            dictionary_pages=self.dictionary_pages,
            status_service=self.status_service,
        )

    def add_lexeme_on_page(
        self, page_number: int, status: LexemeStatus = LexemeStatus.DRAFT
    ) -> None:
        page = self.pages[page_number - 1]
        lexeme = _lexeme(self.dictionary.id, page.id, status)
        self.lexicography_repository.add_lexeme(lexeme)

    def add_entry(self, status: EntryStatus) -> None:
        self.lexicography_repository.add_entry(_entry(self.dictionary.id, status))


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


def test_get_progress_reports_zero_lexeme_and_entry_totals_when_empty() -> None:
    fixture = Fixture()

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.total_lexemes == 0
    assert progress.completed_lexemes == 0
    assert progress.total_entries == 0
    assert progress.completed_entries == 0


def test_get_progress_counts_completed_lexemes_and_entries() -> None:
    fixture = Fixture()
    fixture.add_lexeme_on_page(1, LexemeStatus.COMPLETE)
    fixture.add_lexeme_on_page(1, LexemeStatus.READY_TO_REVIEW)
    fixture.add_lexeme_on_page(2, LexemeStatus.DRAFT)
    fixture.add_entry(EntryStatus.COMPLETE)
    fixture.add_entry(EntryStatus.DRAFT)

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.total_lexemes == 3
    assert progress.completed_lexemes == 1
    assert progress.total_entries == 2
    assert progress.completed_entries == 1


def test_get_progress_leaves_draft_status_untouched() -> None:
    fixture = Fixture(status=DictionaryStatus.DRAFT)
    fixture.add_lexeme_on_page(1, LexemeStatus.COMPLETE)

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.status == DictionaryStatus.DRAFT


def test_get_progress_advances_scanned_to_in_progress_once_work_starts() -> None:
    fixture = Fixture(status=DictionaryStatus.SCANNED)
    fixture.add_lexeme_on_page(1, LexemeStatus.READY_TO_REVIEW)
    fixture.add_lexeme_on_page(2, LexemeStatus.DRAFT)

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.status == DictionaryStatus.IN_PROGRESS
    assert (
        fixture.sources_repository.dictionaries[fixture.dictionary.id].status
        == DictionaryStatus.IN_PROGRESS
    )


def test_get_progress_advances_to_processed_when_all_complete() -> None:
    fixture = Fixture(status=DictionaryStatus.IN_PROGRESS)
    fixture.add_lexeme_on_page(1, LexemeStatus.COMPLETE)
    fixture.add_lexeme_on_page(2, LexemeStatus.COMPLETE)
    fixture.add_entry(EntryStatus.COMPLETE)

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.status == DictionaryStatus.PROCESSED


def test_get_progress_reverts_processed_to_in_progress_if_work_reopens() -> None:
    fixture = Fixture(status=DictionaryStatus.PROCESSED)
    fixture.add_lexeme_on_page(1, LexemeStatus.COMPLETE)
    fixture.add_lexeme_on_page(2, LexemeStatus.READY_TO_REVIEW)

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.status == DictionaryStatus.IN_PROGRESS


def test_get_progress_never_reverts_published() -> None:
    fixture = Fixture(status=DictionaryStatus.PUBLISHED)
    fixture.add_lexeme_on_page(1, LexemeStatus.READY_TO_REVIEW)

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.status == DictionaryStatus.PUBLISHED


def test_get_progress_without_saved_ranges_is_empty() -> None:
    fixture = Fixture()
    fixture.sources_repository.page_ranges[fixture.dictionary.id] = []

    progress = fixture.service.get_progress(fixture.dictionary.id, fixture.owner_id)

    assert progress.total_pages == 0
    assert progress.processed_pages == 0
    assert progress.pages == ()
