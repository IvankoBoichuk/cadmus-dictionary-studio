from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

from cadmus.sources import (
    Abbreviation,
    AbbreviationCategory,
    AbbreviationVariant,
    Contributor,
    Dictionary,
    DictionaryEvent,
    DictionaryLanguage,
    DictionaryPage,
    InspectionStatus,
    PagesStatus,
    SourceFile,
)
from cadmus_worker.backfill_pages import _enqueue_pending

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _source_file(**overrides: object) -> SourceFile:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": uuid4(),
        "original_filename": "dictionary.pdf",
        "mime_type": "application/pdf",
        "byte_size": 1024,
        "checksum_sha256": "a" * 64,
        "storage_key": "sources/owner/file.pdf",
        "uploaded_at": NOW,
        "uploaded_by": uuid4(),
        "inspection_status": InspectionStatus.VERIFIED,
        "page_count": 2,
    }
    defaults.update(overrides)
    return SourceFile(**defaults)  # type: ignore[arg-type]


@dataclass
class MemorySourcesRepository:
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        raise AssertionError("not used by backfill tests")

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        raise AssertionError("not used by backfill tests")

    def get_source_file_by_id(self, source_file_id: UUID) -> SourceFile | None:
        raise AssertionError("not used by backfill tests")

    def find_duplicate_source(
        self, owner_id: UUID, checksum_sha256: str
    ) -> Dictionary | None:
        raise AssertionError("not used by backfill tests")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        raise AssertionError("not used by backfill tests")

    def update_dictionary(self, dictionary: Dictionary) -> None:
        raise AssertionError("not used by backfill tests")

    def add_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by backfill tests")

    def update_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by backfill tests")

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError("not used by backfill tests")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by backfill tests")

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError("not used by backfill tests")

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by backfill tests")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        return [
            source_file
            for source_file in self.source_files.values()
            if source_file.inspection_status is InspectionStatus.VERIFIED
            and source_file.pages_status is not PagesStatus.COMPLETED
        ]

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by backfill tests")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by backfill tests")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by backfill tests")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by backfill tests")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by backfill tests")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by backfill tests")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by backfill tests")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by backfill tests")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by backfill tests")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by backfill tests")


class MemorySourcesUnitOfWork:
    def __init__(self, shared: MemorySourcesRepository) -> None:
        self.sources = shared

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
class FakePagesQueue:
    enqueued: list[UUID] = field(default_factory=list)

    def enqueue_split(self, source_file_id: UUID) -> None:
        self.enqueued.append(source_file_id)


def test_enqueue_pending_targets_only_unsplit_verified_source_files() -> None:
    repository = MemorySourcesRepository()
    pending = _source_file()
    completed = _source_file(pages_status=PagesStatus.COMPLETED)
    unverified = _source_file(inspection_status=InspectionStatus.PENDING)
    for source_file in (pending, completed, unverified):
        repository.source_files[source_file.id] = source_file
    queue = FakePagesQueue()

    count = _enqueue_pending(lambda: MemorySourcesUnitOfWork(repository), queue)

    assert count == 1
    assert queue.enqueued == [pending.id]


def test_enqueue_pending_retries_a_previously_failed_split() -> None:
    repository = MemorySourcesRepository()
    failed = _source_file(pages_status=PagesStatus.FAILED, pages_error="boom")
    repository.source_files[failed.id] = failed
    queue = FakePagesQueue()

    count = _enqueue_pending(lambda: MemorySourcesUnitOfWork(repository), queue)

    assert count == 1
    assert queue.enqueued == [failed.id]


def test_enqueue_pending_returns_zero_when_nothing_is_pending() -> None:
    repository = MemorySourcesRepository()
    queue = FakePagesQueue()

    count = _enqueue_pending(lambda: MemorySourcesUnitOfWork(repository), queue)

    assert count == 0
    assert queue.enqueued == []
