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
    DictionarySettlementMapping,
    InspectionStatus,
    PagesStatus,
    RecordPageSplitService,
    SourceFile,
)

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


def _page(source_file_id: UUID, page_index: int) -> DictionaryPage:
    return DictionaryPage(
        id=uuid4(),
        source_file_id=source_file_id,
        page_index=page_index,
        processed_asset_key=f"sources/{source_file_id}/pages/{page_index:05d}.png",
        width=200,
        height=400,
        checksum_sha256="b" * 64,
        created_at=NOW,
    )


@dataclass
class MemorySourcesRepository:
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    pages: dict[UUID, list[DictionaryPage]] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        raise AssertionError("not used by page-split tests")

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        raise AssertionError("not used by page-split tests")

    def get_source_file_by_id(self, source_file_id: UUID) -> SourceFile | None:
        return self.source_files.get(source_file_id)

    def find_duplicate_source(
        self, owner_id: UUID, checksum_sha256: str
    ) -> Dictionary | None:
        raise AssertionError("not used by page-split tests")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        raise AssertionError("not used by page-split tests")

    def update_dictionary(self, dictionary: Dictionary) -> None:
        raise AssertionError("not used by page-split tests")

    def add_source_file(self, source_file: SourceFile) -> None:
        self.source_files[source_file.id] = source_file

    def update_source_file(self, source_file: SourceFile) -> None:
        self.source_files[source_file.id] = source_file

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError("not used by page-split tests")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by page-split tests")

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError("not used by page-split tests")

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        self.pages[source_file_id] = list(pages)

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        return [
            source_file
            for source_file in self.source_files.values()
            if source_file.inspection_status is InspectionStatus.VERIFIED
            and source_file.pages_status is not PagesStatus.COMPLETED
        ]

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by page-split tests")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by page-split tests")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by page-split tests")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by page-split tests")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by page-split tests")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by page-split tests")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by page-split tests")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by page-split tests")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by page-split tests")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by page-split tests")

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        raise AssertionError("not used by page-split tests")

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by page-split tests")

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by page-split tests")

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by page-split tests")

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by page-split tests")

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError("not used by page-split tests")


class MemorySourcesUnitOfWork:
    """Copy-on-write fake mirroring the upload tests' unit-of-work fake."""

    def __init__(self, shared: MemorySourcesRepository) -> None:
        self._shared = shared
        self.sources = MemorySourcesRepository(
            source_files=dict(shared.source_files), pages=dict(shared.pages)
        )
        self.committed = False

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
        self._shared.source_files = self.sources.source_files
        self._shared.pages = self.sources.pages
        self.committed = True


def test_record_success_replaces_pages_and_marks_completed() -> None:
    repository = MemorySourcesRepository()
    source_file = _source_file()
    repository.source_files[source_file.id] = source_file
    service = RecordPageSplitService(lambda: MemorySourcesUnitOfWork(repository))
    pages = [_page(source_file.id, 0), _page(source_file.id, 1)]

    service.record_success(source_file.id, pages)

    assert repository.pages[source_file.id] == pages
    assert repository.source_files[source_file.id].pages_status is PagesStatus.COMPLETED
    assert repository.source_files[source_file.id].pages_error is None


def test_record_failure_records_the_error_without_touching_pages() -> None:
    repository = MemorySourcesRepository()
    source_file = _source_file()
    repository.source_files[source_file.id] = source_file
    service = RecordPageSplitService(lambda: MemorySourcesUnitOfWork(repository))

    service.record_failure(source_file.id, "Stored PDF object is missing.")

    updated = repository.source_files[source_file.id]
    assert updated.pages_status is PagesStatus.FAILED
    assert updated.pages_error == "Stored PDF object is missing."
    assert source_file.id not in repository.pages


def test_record_success_is_a_no_op_for_a_missing_source_file() -> None:
    repository = MemorySourcesRepository()
    service = RecordPageSplitService(lambda: MemorySourcesUnitOfWork(repository))

    service.record_success(uuid4(), [])

    assert repository.pages == {}


def test_record_failure_does_not_downgrade_a_completed_split() -> None:
    repository = MemorySourcesRepository()
    source_file = _source_file(pages_status=PagesStatus.COMPLETED)
    repository.source_files[source_file.id] = source_file
    service = RecordPageSplitService(lambda: MemorySourcesUnitOfWork(repository))

    service.record_failure(source_file.id, "a stale retry raced a completed split")

    updated = repository.source_files[source_file.id]
    assert updated.pages_status is PagesStatus.COMPLETED
    assert updated.pages_error is None
