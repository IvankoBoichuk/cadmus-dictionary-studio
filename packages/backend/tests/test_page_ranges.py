from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
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
    DictionaryEventType,
    DictionaryLanguage,
    DictionaryPage,
    DictionaryPageRange,
    DictionarySettlementMapping,
    DictionaryStatus,
    InspectionStatus,
    LegalStatus,
    PageRangeInput,
    PageRangesUnavailableError,
    PageRangeValidationError,
    SavePageRangesService,
    SourceFile,
    SourcesRepository,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    page_ranges: dict[UUID, list[DictionaryPageRange]] = field(default_factory=dict)
    events: list[DictionaryEvent] = field(default_factory=list)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        return self.source_files.get(dictionary_id)

    def get_source_file_by_id(self, source_file_id: UUID) -> None:
        raise AssertionError("not used by page-range tests")

    def find_duplicate_source(self, owner_id: UUID, checksum_sha256: str) -> None:
        raise AssertionError("not used by page-range tests")

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
        raise AssertionError("not used by page-range tests")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by page-range tests")

    def add_event(self, event: DictionaryEvent) -> None:
        self.events.append(event)

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by page-range tests")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by page-range tests")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by page-range tests")

    def get_page_by_id(self, page_id: UUID) -> DictionaryPage | None:
        raise AssertionError("not used by page-range tests")

    def list_pages(self, source_file_id: UUID) -> list[DictionaryPage]:
        raise AssertionError("not used by page-range tests")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by page-range tests")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by page-range tests")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by page-range tests")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by page-range tests")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by page-range tests")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by page-range tests")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by page-range tests")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by page-range tests")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by page-range tests")

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        raise AssertionError("not used by page-range tests")

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by page-range tests")

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by page-range tests")

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by page-range tests")

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by page-range tests")

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError("not used by page-range tests")

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]:
        return list(self.page_ranges.get(dictionary_id, []))

    def replace_page_ranges(
        self, dictionary_id: UUID, ranges: Sequence[DictionaryPageRange]
    ) -> None:
        self.page_ranges[dictionary_id] = list(ranges)


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = cast(SourcesRepository, repository)
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
        self.committed = True


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


def _service(repository: MemorySourcesRepository) -> SavePageRangesService:
    return SavePageRangesService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository)
    )


def test_save_stores_a_single_valid_range() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)

    outcome = service.save(
        dictionary.id, owner_id, [PageRangeInput(start_page=10, end_page=220)]
    )

    assert outcome.merged is False
    assert [(r.start_page, r.end_page) for r in outcome.ranges] == [(10, 220)]
    stored = repository.page_ranges[dictionary.id]
    assert [(r.start_page, r.end_page) for r in stored] == [(10, 220)]
    assert stored[0].position == 0


def test_save_stores_multiple_ranges_in_sorted_order() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)

    outcome = service.save(
        dictionary.id,
        owner_id,
        [PageRangeInput(225, 310), PageRangeInput(10, 220)],
    )

    assert [(r.start_page, r.end_page) for r in outcome.ranges] == [
        (10, 220),
        (225, 310),
    ]
    assert [r.position for r in outcome.ranges] == [0, 1]


def test_save_merges_overlapping_ranges_and_reports_it() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)

    outcome = service.save(
        dictionary.id, owner_id, [PageRangeInput(1, 20), PageRangeInput(15, 40)]
    )

    assert outcome.merged is True
    assert [(r.start_page, r.end_page) for r in outcome.ranges] == [(1, 40)]


def test_save_replaces_the_previous_set_of_ranges() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)
    service.save(dictionary.id, owner_id, [PageRangeInput(1, 10)])

    outcome = service.save(dictionary.id, owner_id, [PageRangeInput(50, 60)])

    assert [(r.start_page, r.end_page) for r in outcome.ranges] == [(50, 60)]
    assert len(repository.page_ranges[dictionary.id]) == 1


def test_save_clears_ranges_when_given_an_empty_list() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)
    service.save(dictionary.id, owner_id, [PageRangeInput(1, 10)])

    outcome = service.save(dictionary.id, owner_id, [])

    assert outcome.ranges == []
    assert repository.page_ranges[dictionary.id] == []


def test_save_rejects_a_range_that_exceeds_the_pdf_bounds() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id, page_count=100))
    service = _service(repository)

    with pytest.raises(PageRangeValidationError) as error:
        service.save(dictionary.id, owner_id, [PageRangeInput(1, 101)])
    assert "ranges.0.end_page" in error.value.errors
    assert dictionary.id not in repository.page_ranges


def test_save_rejects_an_inverted_range() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)

    with pytest.raises(PageRangeValidationError) as error:
        service.save(dictionary.id, owner_id, [PageRangeInput(50, 10)])
    assert "ranges.0.end_page" in error.value.errors


def test_save_requires_a_known_page_count() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(
        _source_file(
            dictionary.id, inspection_status=InspectionStatus.PENDING, page_count=None
        )
    )
    service = _service(repository)

    with pytest.raises(PageRangesUnavailableError):
        service.save(dictionary.id, owner_id, [PageRangeInput(1, 10)])


def test_save_requires_a_source_file() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(PageRangesUnavailableError):
        service.save(dictionary.id, owner_id, [PageRangeInput(1, 10)])


def test_save_actor_other_than_owner_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)

    with pytest.raises(DictionaryAccessError):
        service.save(dictionary.id, uuid4(), [PageRangeInput(1, 10)])


def test_save_missing_dictionary_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    service = _service(repository)

    with pytest.raises(DictionaryAccessError):
        service.save(uuid4(), uuid4(), [PageRangeInput(1, 10)])


def test_clearing_ranges_on_a_configured_dictionary_reverts_it_to_draft() -> None:
    """BH-31 AC7: page ranges are part of readiness too, so emptying them on

    a ``configured`` dictionary must demote it, mirroring metadata edits.
    """
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    dictionary.title = "Словник"
    dictionary.status = DictionaryStatus.CONFIGURED
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)

    service.save(dictionary.id, owner_id, [])

    assert repository.dictionaries[dictionary.id].status is DictionaryStatus.DRAFT
    status_events = [
        e
        for e in repository.events
        if e.event_type is DictionaryEventType.STATUS_CHANGED
    ]
    assert len(status_events) == 1
    assert status_events[0].previous_status is DictionaryStatus.CONFIGURED
    assert status_events[0].new_status is DictionaryStatus.DRAFT
    assert status_events[0].reason == "page_ranges_no_longer_ready"


def test_replacing_ranges_on_a_configured_dictionary_leaves_it_configured() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    dictionary.title = "Словник"
    dictionary.legal_status = LegalStatus.PUBLIC_DOMAIN
    dictionary.languages = [
        DictionaryLanguage(
            id=uuid4(), dictionary_id=dictionary.id, language_code="uk", position=0
        )
    ]
    dictionary.status = DictionaryStatus.CONFIGURED
    repository.add_dictionary(dictionary)
    repository.add_source_file(_source_file(dictionary.id))
    service = _service(repository)

    service.save(dictionary.id, owner_id, [PageRangeInput(1, 50)])

    assert repository.dictionaries[dictionary.id].status is DictionaryStatus.CONFIGURED
    assert repository.events == []
