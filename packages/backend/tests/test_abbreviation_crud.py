from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID, uuid4

import pytest
from cadmus.sources import (
    Abbreviation,
    AbbreviationAccessError,
    AbbreviationCategory,
    AbbreviationCrudService,
    AbbreviationInput,
    AbbreviationValidationError,
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
    DuplicateAbbreviationError,
    SourceFile,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 8, 16, 13, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    abbreviations: dict[UUID, Abbreviation] = field(default_factory=dict)
    variants: dict[UUID, list[AbbreviationVariant]] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def get_source_file_by_id(self, source_file_id: UUID) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def find_duplicate_source(self, owner_id: UUID, checksum_sha256: str) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def update_source_file(self, source_file: SourceFile) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by abbreviation CRUD")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by abbreviation CRUD")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by abbreviation CRUD")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        return [
            self._with_variants(item)
            for item in self.abbreviations.values()
            if item.dictionary_id == dictionary_id
        ]

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        item = self.abbreviations.get(abbreviation_id)
        if item is None or item.dictionary_id != dictionary_id:
            return None
        return self._with_variants(item)

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        for item in self.abbreviations.values():
            if (
                item.dictionary_id == dictionary_id
                and item.category == category
                and item.language_code == language_code
                and item.abbreviation == abbreviation.strip()
                and item.id != exclude_id
            ):
                return item
        return None

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        self.abbreviations[abbreviation.id] = abbreviation

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        self.abbreviations[abbreviation.id] = abbreviation

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        self.variants[abbreviation_id] = list(variants)

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        item = self.abbreviations.get(abbreviation_id)
        if item is not None and item.dictionary_id == dictionary_id:
            del self.abbreviations[abbreviation_id]
            self.variants.pop(abbreviation_id, None)

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        raise AssertionError("not used by abbreviation CRUD")

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by abbreviation CRUD")

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        settlement_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by abbreviation CRUD")

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def list_page_ranges(self, dictionary_id: UUID) -> list[DictionaryPageRange]:
        raise AssertionError("not used by abbreviation CRUD")

    def replace_page_ranges(
        self, dictionary_id: UUID, ranges: Sequence[DictionaryPageRange]
    ) -> None:
        raise AssertionError("not used by abbreviation CRUD")

    def _with_variants(self, item: Abbreviation) -> Abbreviation:
        item.variants = list(self.variants.get(item.id, []))
        return item


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
    repository: MemorySourcesRepository, clock: datetime = NOW
) -> AbbreviationCrudService:
    return AbbreviationCrudService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(repository),
        clock=lambda: clock,
    )


def _input(**overrides: object) -> AbbreviationInput:
    defaults: dict[str, object] = {
        "abbreviation": "розм.",
        "category": AbbreviationCategory.USAGE,
        "full_form": "розмовне",
        "language_code": "uk",
        "note": None,
        "unresolved": False,
        "variants": (),
    }
    defaults.update(overrides)
    return AbbreviationInput(**defaults)  # type: ignore[arg-type]


def test_create_stores_a_structured_abbreviation() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    created = service.create(dictionary.id, owner_id, _input())

    assert created.abbreviation == "розм."
    assert created.category is AbbreviationCategory.USAGE
    assert created.full_form == "розмовне"


def test_unresolved_entry_can_be_saved_without_full_form() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    created = service.create(
        dictionary.id, owner_id, _input(full_form=None, unresolved=True)
    )

    assert created.full_form is None
    assert created.unresolved is True


def test_resolved_entry_without_full_form_is_rejected() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(AbbreviationValidationError) as error:
        service.create(dictionary.id, owner_id, _input(full_form=None))
    assert "full_form" in error.value.errors


def test_variants_are_stored_ordered() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    created = service.create(
        dictionary.id, owner_id, _input(variants=("розмовне.", "розм"))
    )

    assert [v.variant_text for v in created.variants] == ["розмовне.", "розм"]
    assert [v.position for v in created.variants] == [0, 1]


def test_duplicate_abbreviation_same_category_and_language_is_rejected() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    service.create(dictionary.id, owner_id, _input())

    with pytest.raises(DuplicateAbbreviationError):
        service.create(dictionary.id, owner_id, _input())


def test_same_abbreviation_in_a_different_category_is_allowed() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    service.create(dictionary.id, owner_id, _input())

    created = service.create(
        dictionary.id, owner_id, _input(category=AbbreviationCategory.GRAMMAR)
    )
    assert created.category is AbbreviationCategory.GRAMMAR


def test_same_abbreviation_in_a_different_language_is_allowed() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    service.create(dictionary.id, owner_id, _input())

    created = service.create(dictionary.id, owner_id, _input(language_code="en"))
    assert created.language_code == "en"


def test_update_can_change_fields_without_conflicting_with_itself() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository, clock=NOW)
    created = service.create(dictionary.id, owner_id, _input())

    later_service = _service(repository, clock=LATER)
    updated = later_service.update(
        dictionary.id, created.id, owner_id, _input(note="уточнення")
    )

    assert updated.note == "уточнення"
    assert updated.updated_at == LATER


def test_update_rejects_a_duplicate_of_another_entry() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)
    first = service.create(dictionary.id, owner_id, _input())
    second = service.create(
        dictionary.id, owner_id, _input(category=AbbreviationCategory.GRAMMAR)
    )

    with pytest.raises(DuplicateAbbreviationError):
        service.update(
            dictionary.id,
            second.id,
            owner_id,
            _input(category=AbbreviationCategory.USAGE),
        )
    assert first.category is AbbreviationCategory.USAGE


def test_update_missing_abbreviation_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(AbbreviationAccessError):
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


def test_delete_missing_abbreviation_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    owner_id = uuid4()
    dictionary = _dictionary(owner_id)
    repository.add_dictionary(dictionary)
    service = _service(repository)

    with pytest.raises(AbbreviationAccessError):
        service.delete(dictionary.id, uuid4(), owner_id)


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


def test_abbreviations_are_isolated_between_dictionaries() -> None:
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
