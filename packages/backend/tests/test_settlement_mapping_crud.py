from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.geography.domain import (
    Area,
    Community,
    CommunityGeometry,
    Region,
    Settlement,
    SyncRun,
)
from cadmus.geography.ports import GeographyRepository
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
    DuplicateSettlementMappingError,
    SettlementMappingAccessError,
    SettlementMappingCrudService,
    SettlementMappingInput,
    SettlementMappingStatus,
    SettlementMappingValidationError,
    SourceFile,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 16, 13, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    mappings: dict[UUID, DictionarySettlementMapping] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def get_source_file_by_id(self, source_file_id: UUID) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def find_duplicate_source(self, owner_id: UUID, checksum_sha256: str) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def update_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by settlement mapping CRUD")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by settlement mapping CRUD")

    def get_page_by_id(self, page_id: UUID) -> DictionaryPage | None:
        raise AssertionError("not used by settlement mapping CRUD")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by settlement mapping CRUD")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by settlement mapping CRUD")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by settlement mapping CRUD")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by settlement mapping CRUD")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by settlement mapping CRUD")

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        return [
            item
            for item in self.mappings.values()
            if item.dictionary_id == dictionary_id
        ]

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        item = self.mappings.get(mapping_id)
        if item is None or item.dictionary_id != dictionary_id:
            return None
        return item

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        settlement_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        for item in self.mappings.values():
            if (
                item.dictionary_id == dictionary_id
                and item.source_label == source_label_key
                and item.id != exclude_id
                and (
                    settlement_id is None
                    or item.settlement_id is None
                    or item.settlement_id == settlement_id
                )
            ):
                return item
        return None

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        self.mappings[mapping.id] = mapping

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        self.mappings[mapping.id] = mapping

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        item = self.mappings.get(mapping_id)
        if item is not None and item.dictionary_id == dictionary_id:
            del self.mappings[mapping_id]

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]:
        raise AssertionError("not used by settlement mapping CRUD")

    def replace_page_ranges(
        self, dictionary_id: UUID, ranges: Sequence[DictionaryPageRange]
    ) -> None:
        raise AssertionError("not used by settlement mapping CRUD")


class MemorySourcesUnitOfWork:
    def __init__(self, repository: MemorySourcesRepository) -> None:
        self.sources = repository
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


class UnusedGeographyUnitOfWork:
    """Fails loudly if a test's mapping data ever triggers a geography lookup."""

    @property
    def geography(self) -> GeographyRepository:
        raise AssertionError("not used")

    def __enter__(self) -> "UnusedGeographyUnitOfWork":
        raise AssertionError(
            "settlement mapping CRUD test did not expect geography access"
        )

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        raise AssertionError("not used")


_GEOGRAPHY_UNUSED = "not used by BH-191 duplicate-detection tests"


@dataclass
class MemoryGeographyRepository:
    """Geography cache used by BH-191's cross-settlement duplicate tests."""

    settlements: dict[UUID, Settlement] = field(default_factory=dict)
    communities: dict[UUID, Community] = field(default_factory=dict)

    def upsert_area(self, area: Area) -> None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def upsert_region(self, region: Region) -> None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def upsert_community(
        self, community: Community, settlements: Sequence[Settlement]
    ) -> None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def upsert_geometry(self, geometry: CommunityGeometry) -> None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def find_area_by_external_id(self, external_id: str) -> Area | None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def find_region_by_external_id(self, external_id: str) -> Region | None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def find_community_by_external_id(self, external_id: str) -> Community | None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def get_area(self, area_id: UUID) -> Area | None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def get_region(self, region_id: UUID) -> Region | None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def get_settlement(self, settlement_id: UUID) -> Settlement | None:
        return self.settlements.get(settlement_id)

    def list_areas(self) -> list[Area]:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def list_regions(self, area_id: UUID | None = None) -> list[Region]:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def list_communities(
        self, area_id: UUID | None = None, region_id: UUID | None = None
    ) -> list[Community]:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def search_settlements(
        self,
        *,
        query: str | None,
        area_id: UUID | None,
        region_id: UUID | None,
        community_id: UUID | None,
        category: str | None,
        limit: int = 25,
    ) -> list[tuple[Settlement, Community]]:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def get_community(self, community_id: UUID) -> Community | None:
        return self.communities.get(community_id)

    def get_community_geometry(self, community_id: UUID) -> CommunityGeometry | None:
        raise AssertionError(_GEOGRAPHY_UNUSED)

    def add_sync_run(self, run: SyncRun) -> None:
        raise AssertionError(_GEOGRAPHY_UNUSED)


class MemoryGeographyUnitOfWork:
    def __init__(self, repository: MemoryGeographyRepository) -> None:
        self.geography = repository

    def __enter__(self) -> "MemoryGeographyUnitOfWork":
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
        status=DictionaryStatus.CONFIGURED,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


def _service(
    repository: MemorySourcesRepository,
    clock: datetime = NOW,
    geography: MemoryGeographyRepository | None = None,
) -> SettlementMappingCrudService:
    return SettlementMappingCrudService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository),
        geography_unit_of_work_factory=(
            (lambda: MemoryGeographyUnitOfWork(geography))
            if geography is not None
            else (lambda: UnusedGeographyUnitOfWork())
        ),
        clock=lambda: clock,
    )


def _input(**overrides: object) -> SettlementMappingInput:
    defaults: dict[str, object] = {
        "source_label": "Іванівка",
        "source_note": None,
        "modern_settlement_name": None,
        "settlement_category": None,
        "settlement_id": None,
        "status": SettlementMappingStatus.UNRESOLVED,
    }
    defaults.update(overrides)
    return SettlementMappingInput(**defaults)  # type: ignore[arg-type]


def test_create_stores_a_settlement_mapping() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    created = service.create(dictionary.id, owner_id, _input())

    assert created.source_label == "Іванівка"
    assert created.status is SettlementMappingStatus.UNRESOLVED


def test_create_rejects_invalid_input() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(SettlementMappingValidationError) as error:
        service.create(dictionary.id, owner_id, _input(source_label=""))
    assert "source_label" in error.value.errors


def test_create_rejects_confirmed_status() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(SettlementMappingValidationError) as error:
        service.create(
            dictionary.id, owner_id, _input(status=SettlementMappingStatus.CONFIRMED)
        )
    assert "status" in error.value.errors


def test_duplicate_source_label_is_rejected() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    service.create(dictionary.id, owner_id, _input())

    with pytest.raises(DuplicateSettlementMappingError):
        service.create(dictionary.id, owner_id, _input())


def test_duplicate_check_trims_whitespace() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    service.create(dictionary.id, owner_id, _input(source_label="Іванівка"))

    with pytest.raises(DuplicateSettlementMappingError):
        service.create(dictionary.id, owner_id, _input(source_label="  Іванівка  "))


def _settlement(title: str, category: str) -> tuple[Settlement, Community]:
    community_id = uuid4()
    community = Community(
        id=community_id,
        external_id=str(uuid4()),
        name=f"{title} ({category}) громада",
        area_id=uuid4(),
        region_id=uuid4(),
        last_synced_at=NOW,
    )
    settlement = Settlement(
        id=uuid4(), community_id=community_id, title=title, category=category
    )
    return settlement, community


def test_same_label_linked_to_different_settlements_is_not_a_duplicate() -> None:
    """BH-191: homonym settlements (e.g. "Банилів" village vs. town) must
    both be addable once each is resolved to its own distinct settlement."""
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    geography = MemoryGeographyRepository()
    village, village_community = _settlement("Банилів", "село")
    town, town_community = _settlement("Банилів", "селище")
    geography.settlements[village.id] = village
    geography.communities[village_community.id] = village_community
    geography.settlements[town.id] = town
    geography.communities[town_community.id] = town_community
    service = _service(repository, geography=geography)

    first = service.create(
        dictionary.id,
        owner_id,
        _input(source_label="Банилів", settlement_id=village.id),
    )
    second = service.create(
        dictionary.id,
        owner_id,
        _input(source_label="Банилів", settlement_id=town.id),
    )

    assert first.settlement_id == village.id
    assert second.settlement_id == town.id
    assert first.community_id == village_community.id
    assert second.community_id == town_community.id


def test_same_label_linked_to_the_same_settlement_is_still_a_duplicate() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    geography = MemoryGeographyRepository()
    village, village_community = _settlement("Банилів", "село")
    geography.settlements[village.id] = village
    geography.communities[village_community.id] = village_community
    service = _service(repository, geography=geography)
    service.create(
        dictionary.id,
        owner_id,
        _input(source_label="Банилів", settlement_id=village.id),
    )

    with pytest.raises(DuplicateSettlementMappingError):
        service.create(
            dictionary.id,
            owner_id,
            _input(source_label="Банилів", settlement_id=village.id),
        )


def test_same_label_still_conflicts_with_an_unresolved_entry() -> None:
    """A second, not-yet-resolved entry can't tell it apart from an
    existing one yet, so the original text-only duplicate check still
    applies until the user actually resolves it to a distinct settlement."""
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    service.create(dictionary.id, owner_id, _input(source_label="Банилів"))

    with pytest.raises(DuplicateSettlementMappingError):
        service.create(dictionary.id, owner_id, _input(source_label="Банилів"))


def test_update_can_change_fields_without_conflicting_with_itself() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository, clock=NOW)
    created = service.create(dictionary.id, owner_id, _input())

    later_service = _service(repository, clock=LATER)
    updated = later_service.update(
        dictionary.id, created.id, owner_id, _input(source_note="уточнення")
    )

    assert updated.source_note == "уточнення"
    assert updated.updated_at == LATER


def test_update_rejects_a_duplicate_of_another_entry() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    first = service.create(dictionary.id, owner_id, _input())
    second = service.create(dictionary.id, owner_id, _input(source_label="Петрівка"))

    with pytest.raises(DuplicateSettlementMappingError):
        service.update(
            dictionary.id, second.id, owner_id, _input(source_label="Іванівка")
        )
    assert first.source_label == "Іванівка"


def test_update_rejects_confirmed_status() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    created = service.create(dictionary.id, owner_id, _input())

    with pytest.raises(SettlementMappingValidationError):
        service.update(
            dictionary.id,
            created.id,
            owner_id,
            _input(status=SettlementMappingStatus.CONFIRMED),
        )


def test_update_missing_mapping_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(SettlementMappingAccessError):
        service.update(dictionary.id, uuid4(), owner_id, _input())


def test_delete_removes_the_entry() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    created = service.create(dictionary.id, owner_id, _input())

    service.delete(dictionary.id, created.id, owner_id)

    assert service.list_for_dictionary(dictionary.id, owner_id) == []


def test_delete_missing_mapping_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(SettlementMappingAccessError):
        service.delete(dictionary.id, uuid4(), owner_id)


def test_unconfirm_resets_status_and_clears_confirmation() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    created = service.create(dictionary.id, owner_id, _input())
    # Simulate a prior confirmation without going through the confirmation
    # service (that flow is covered in test_settlement_confirmation.py).
    created.status = SettlementMappingStatus.CONFIRMED
    created.confirmed_by = owner_id
    created.confirmed_at = NOW
    repository.update_settlement_mapping(created)

    reverted = service.unconfirm(dictionary.id, created.id, owner_id)

    assert reverted.status is SettlementMappingStatus.UNRESOLVED
    assert reverted.confirmed_by is None
    assert reverted.confirmed_at is None


def test_unconfirm_missing_mapping_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(SettlementMappingAccessError):
        service.unconfirm(dictionary.id, uuid4(), owner_id)


def test_actor_other_than_owner_cannot_list_create_update_or_delete() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    stranger_id = uuid4()

    with pytest.raises(DictionaryAccessError):
        service.list_for_dictionary(dictionary.id, stranger_id)
    with pytest.raises(DictionaryAccessError):
        service.create(dictionary.id, stranger_id, _input())

    created = service.create(dictionary.id, owner_id, _input())
    with pytest.raises(DictionaryAccessError):
        service.update(dictionary.id, created.id, stranger_id, _input())
    with pytest.raises(DictionaryAccessError):
        service.delete(dictionary.id, created.id, stranger_id)
    with pytest.raises(DictionaryAccessError):
        service.unconfirm(dictionary.id, created.id, stranger_id)


def test_mappings_are_isolated_between_dictionaries() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary_a = _dictionary(owner_id)
    dictionary_b = _dictionary(owner_id)
    repository.add_dictionary(dictionary_a)
    repository.add_dictionary(dictionary_b)
    service = _service(repository)
    service.create(dictionary_a.id, owner_id, _input())

    assert service.list_for_dictionary(dictionary_b.id, owner_id) == []
    assert len(service.list_for_dictionary(dictionary_a.id, owner_id)) == 1
