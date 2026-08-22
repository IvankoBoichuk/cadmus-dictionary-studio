"""BH-53: page-viewer domain and application behavior."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.sources import (
    Abbreviation,
    AbbreviationCategory,
    AbbreviationVariant,
    Contributor,
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryLanguage,
    DictionaryPage,
    DictionaryPageRange,
    DictionarySettlementMapping,
    DictionaryStatus,
    GetDictionaryService,
    InspectionStatus,
    SourceFile,
    expand_page_ranges,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    page_ranges: dict[UUID, list[DictionaryPageRange]] = field(default_factory=dict)
    pages: dict[tuple[UUID, int], DictionaryPage] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        return self.source_files.get(dictionary_id)

    def get_source_file_by_id(self, source_file_id: UUID) -> None:
        raise AssertionError("not used by page-viewer tests")

    def find_duplicate_source(self, owner_id: UUID, checksum_sha256: str) -> None:
        raise AssertionError("not used by page-viewer tests")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_source_file(self, source_file: SourceFile) -> None:
        self.source_files[source_file.dictionary_id] = source_file

    def update_source_file(self, source_file: SourceFile) -> None:
        self.source_files[source_file.dictionary_id] = source_file

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError("not used by page-viewer tests")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by page-viewer tests")

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError("not used by page-viewer tests")

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        for page in pages:
            self.pages[(source_file_id, page.page_index)] = page

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by page-viewer tests")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        return self.pages.get((source_file_id, page_index))

    def get_page_by_id(self, page_id: UUID) -> DictionaryPage | None:
        return next((p for p in self.pages.values() if p.id == page_id), None)

    def list_pages(self, source_file_id: UUID) -> list[DictionaryPage]:
        return [p for (sfid, _), p in self.pages.items() if sfid == source_file_id]

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by page-viewer tests")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by page-viewer tests")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by page-viewer tests")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by page-viewer tests")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by page-viewer tests")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by page-viewer tests")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by page-viewer tests")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by page-viewer tests")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by page-viewer tests")

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        raise AssertionError("not used by page-viewer tests")

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by page-viewer tests")

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by page-viewer tests")

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by page-viewer tests")

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by page-viewer tests")

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError("not used by page-viewer tests")

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]:
        return list(self.page_ranges.get(dictionary_id, []))

    def replace_page_ranges(
        self, dictionary_id: UUID, ranges: Sequence[DictionaryPageRange]
    ) -> None:
        self.page_ranges[dictionary_id] = list(ranges)


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


def _page_range(
    dictionary_id: UUID, start: int, end: int, position: int
) -> DictionaryPageRange:
    return DictionaryPageRange(
        id=uuid4(),
        dictionary_id=dictionary_id,
        start_page=start,
        end_page=end,
        position=position,
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


def _service(repository: MemorySourcesRepository) -> GetDictionaryService:
    return GetDictionaryService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository)
    )


def test_expand_page_ranges_flattens_a_single_range() -> None:
    dictionary_id = uuid4()
    ranges = [_page_range(dictionary_id, 5, 8, position=0)]

    assert expand_page_ranges(ranges) == [5, 6, 7, 8]


def test_expand_page_ranges_orders_by_position_not_start_page() -> None:
    dictionary_id = uuid4()
    ranges = [
        _page_range(dictionary_id, 20, 21, position=1),
        _page_range(dictionary_id, 1, 2, position=0),
    ]

    assert expand_page_ranges(ranges) == [1, 2, 20, 21]


def test_expand_page_ranges_of_an_empty_list_is_empty() -> None:
    assert expand_page_ranges([]) == []


def test_count_viewable_pages_sums_configured_ranges() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.page_ranges[dictionary.id] = [
        _page_range(dictionary.id, 1, 5, position=0),
        _page_range(dictionary.id, 10, 12, position=1),
    ]
    service = _service(repository)

    assert service.count_viewable_pages(dictionary.id, owner_id) == 8


def test_count_viewable_pages_is_zero_without_saved_ranges() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    assert service.count_viewable_pages(dictionary.id, owner_id) == 0


def test_count_viewable_pages_actor_other_than_owner_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(DictionaryAccessError):
        service.count_viewable_pages(dictionary.id, uuid4())


def test_get_viewable_page_maps_ordinal_to_the_physical_page() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    source_file = _source_file(dictionary.id)
    repository.add_source_file(source_file)
    repository.page_ranges[dictionary.id] = [
        _page_range(dictionary.id, 10, 12, position=0)
    ]
    repository.pages[(source_file.id, 10)] = _page(source_file.id, 10)  # page 11
    service = _service(repository)

    page = service.get_viewable_page(dictionary.id, owner_id, ordinal=2)

    assert page is not None
    assert page.page_index == 10


def test_get_viewable_page_out_of_range_ordinal_returns_none() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    repository.page_ranges[dictionary.id] = [
        _page_range(dictionary.id, 1, 3, position=0)
    ]
    service = _service(repository)

    assert service.get_viewable_page(dictionary.id, owner_id, ordinal=4) is None
    assert service.get_viewable_page(dictionary.id, owner_id, ordinal=0) is None


def test_get_viewable_page_excludes_pages_outside_saved_ranges() -> None:
    """AC4: a page just outside the configured ranges must never be reachable."""
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    source_file = _source_file(dictionary.id)
    repository.add_source_file(source_file)
    repository.page_ranges[dictionary.id] = [
        _page_range(dictionary.id, 5, 5, position=0)
    ]
    repository.pages[(source_file.id, 3)] = _page(source_file.id, 3)  # page 4, unlisted
    service = _service(repository)

    assert service.get_viewable_page(dictionary.id, owner_id, ordinal=2) is None


def test_get_viewable_page_without_a_source_file_returns_none() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    assert service.get_viewable_page(dictionary.id, owner_id, ordinal=1) is None


def test_get_viewable_page_actor_other_than_owner_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(DictionaryAccessError):
        service.get_viewable_page(dictionary.id, uuid4(), ordinal=1)
