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
    DeleteDictionaryService,
    Dictionary,
    DictionaryAccessError,
    DictionaryEvent,
    DictionaryLanguage,
    DictionaryPage,
    DictionarySettlementMapping,
    DictionaryStatus,
    GetDictionaryService,
    InspectionStatus,
    SourceFile,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
OWNER_ID = uuid4()
OTHER_OWNER_ID = uuid4()


def _dictionary(owner_id: UUID = OWNER_ID, **overrides: object) -> Dictionary:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "owner_id": owner_id,
        "status": DictionaryStatus.DRAFT,
        "created_at": NOW,
        "updated_at": NOW,
        "updated_by": owner_id,
    }
    defaults.update(overrides)
    return Dictionary(**defaults)  # type: ignore[arg-type]


def _source_file(dictionary_id: UUID, **overrides: object) -> SourceFile:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "dictionary_id": dictionary_id,
        "original_filename": "dictionary.pdf",
        "mime_type": "application/pdf",
        "byte_size": 1024,
        "checksum_sha256": "a" * 64,
        "storage_key": f"sources/{dictionary_id}.pdf",
        "uploaded_at": NOW,
        "uploaded_by": OWNER_ID,
        "inspection_status": InspectionStatus.VERIFIED,
        "page_count": 1,
    }
    defaults.update(overrides)
    return SourceFile(**defaults)  # type: ignore[arg-type]


def _page(source_file_id: UUID, page_index: int = 0) -> DictionaryPage:
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
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    pages: dict[UUID, list[DictionaryPage]] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        return next(
            (f for f in self.source_files.values() if f.dictionary_id == dictionary_id),
            None,
        )

    def get_source_file_by_id(self, source_file_id: UUID) -> SourceFile | None:
        return self.source_files.get(source_file_id)

    def find_duplicate_source(
        self, owner_id: UUID, checksum_sha256: str
    ) -> Dictionary | None:
        raise AssertionError("not used by list/delete tests")

    def add_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def update_dictionary(self, dictionary: Dictionary) -> None:
        self.dictionaries[dictionary.id] = dictionary

    def add_source_file(self, source_file: SourceFile) -> None:
        self.source_files[source_file.id] = source_file

    def update_source_file(self, source_file: SourceFile) -> None:
        self.source_files[source_file.id] = source_file

    def replace_contributors(
        self, dictionary_id: UUID, contributors: Sequence[Contributor]
    ) -> None:
        raise AssertionError("not used by list/delete tests")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by list/delete tests")

    def add_event(self, event: DictionaryEvent) -> None:
        raise AssertionError("not used by list/delete tests")

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by list/delete tests")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by list/delete tests")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        return next(
            (
                page
                for page in self.pages.get(source_file_id, [])
                if page.page_index == page_index
            ),
            None,
        )

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        return sorted(
            (d for d in self.dictionaries.values() if d.owner_id == owner_id),
            key=lambda d: d.updated_at,
            reverse=True,
        )

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        self.dictionaries.pop(dictionary_id, None)
        for source_file_id in [
            f.id for f in self.source_files.values() if f.dictionary_id == dictionary_id
        ]:
            self.source_files.pop(source_file_id, None)
            self.pages.pop(source_file_id, None)

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by list/delete tests")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by list/delete tests")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by list/delete tests")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by list/delete tests")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by list/delete tests")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by list/delete tests")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by list/delete tests")

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        raise AssertionError("not used by list/delete tests")

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by list/delete tests")

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        settlement_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by list/delete tests")

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by list/delete tests")

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by list/delete tests")

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError("not used by list/delete tests")


class MemorySourcesUnitOfWork:
    def __init__(self, shared: MemorySourcesRepository) -> None:
        self._shared = shared
        self.sources = MemorySourcesRepository(
            dictionaries=dict(shared.dictionaries),
            source_files=dict(shared.source_files),
            pages={k: list(v) for k, v in shared.pages.items()},
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
        self._shared.dictionaries = self.sources.dictionaries
        self._shared.source_files = self.sources.source_files
        self._shared.pages = self.sources.pages
        self.committed = True


@dataclass
class FakeObjectStorage:
    deleted_keys: list[str] = field(default_factory=list)
    deleted_prefixes: list[str] = field(default_factory=list)
    fail: bool = False

    def upload(self, key: str, source: object, length: int, content_type: str) -> None:
        raise AssertionError("not used by list/delete tests")

    def download(self, key: str, destination: object) -> None:
        raise AssertionError("not used by list/delete tests")

    def delete(self, key: str) -> None:
        if self.fail:
            raise RuntimeError("object storage is unavailable")
        self.deleted_keys.append(key)

    def delete_prefix(self, prefix: str) -> None:
        if self.fail:
            raise RuntimeError("object storage is unavailable")
        self.deleted_prefixes.append(prefix)


def test_list_for_owner_returns_only_the_owners_dictionaries_with_source_files() -> (
    None
):
    repository = MemorySourcesRepository()
    mine = _dictionary()
    theirs = _dictionary(owner_id=OTHER_OWNER_ID)
    repository.dictionaries[mine.id] = mine
    repository.dictionaries[theirs.id] = theirs
    my_source = _source_file(mine.id)
    repository.source_files[my_source.id] = my_source
    service = GetDictionaryService(lambda: MemorySourcesUnitOfWork(repository))

    entries = service.list_for_owner(OWNER_ID)

    assert [entry.dictionary.id for entry in entries] == [mine.id]
    assert entries[0].source_file is not None
    assert entries[0].source_file.id == my_source.id


def test_list_for_owner_is_empty_when_the_owner_has_no_dictionaries() -> None:
    repository = MemorySourcesRepository()
    service = GetDictionaryService(lambda: MemorySourcesUnitOfWork(repository))

    assert service.list_for_owner(OWNER_ID) == []


def test_get_first_page_returns_the_page_at_index_zero() -> None:
    repository = MemorySourcesRepository()
    dictionary = _dictionary()
    repository.dictionaries[dictionary.id] = dictionary
    source_file = _source_file(dictionary.id)
    repository.source_files[source_file.id] = source_file
    first_page = _page(source_file.id, page_index=0)
    repository.pages[source_file.id] = [first_page, _page(source_file.id, page_index=1)]
    service = GetDictionaryService(lambda: MemorySourcesUnitOfWork(repository))

    assert service.get_first_page(dictionary.id, OWNER_ID) == first_page


def test_get_first_page_is_none_before_splitting_completes() -> None:
    repository = MemorySourcesRepository()
    dictionary = _dictionary()
    repository.dictionaries[dictionary.id] = dictionary
    source_file = _source_file(dictionary.id)
    repository.source_files[source_file.id] = source_file
    service = GetDictionaryService(lambda: MemorySourcesUnitOfWork(repository))

    assert service.get_first_page(dictionary.id, OWNER_ID) is None


def test_get_first_page_not_owned_raises_access_error() -> None:
    repository = MemorySourcesRepository()
    dictionary = _dictionary(owner_id=OTHER_OWNER_ID)
    repository.dictionaries[dictionary.id] = dictionary
    service = GetDictionaryService(lambda: MemorySourcesUnitOfWork(repository))

    try:
        service.get_first_page(dictionary.id, OWNER_ID)
    except DictionaryAccessError:
        pass
    else:
        raise AssertionError("expected DictionaryAccessError")


def test_delete_removes_the_dictionary_row_and_both_storage_locations() -> None:
    repository = MemorySourcesRepository()
    dictionary = _dictionary()
    repository.dictionaries[dictionary.id] = dictionary
    source_file = _source_file(dictionary.id)
    repository.source_files[source_file.id] = source_file
    object_storage = FakeObjectStorage()
    service = DeleteDictionaryService(
        lambda: MemorySourcesUnitOfWork(repository), object_storage
    )

    service.delete(dictionary.id, OWNER_ID)

    assert dictionary.id not in repository.dictionaries
    assert object_storage.deleted_keys == [source_file.storage_key]
    assert object_storage.deleted_prefixes == [f"sources/{dictionary.id}/pages/"]


def test_delete_removes_the_row_even_when_there_is_no_source_file() -> None:
    repository = MemorySourcesRepository()
    dictionary = _dictionary()
    repository.dictionaries[dictionary.id] = dictionary
    object_storage = FakeObjectStorage()
    service = DeleteDictionaryService(
        lambda: MemorySourcesUnitOfWork(repository), object_storage
    )

    service.delete(dictionary.id, OWNER_ID)

    assert dictionary.id not in repository.dictionaries
    assert object_storage.deleted_keys == []
    assert object_storage.deleted_prefixes == []


def test_delete_still_removes_the_row_when_storage_cleanup_fails() -> None:
    repository = MemorySourcesRepository()
    dictionary = _dictionary()
    repository.dictionaries[dictionary.id] = dictionary
    source_file = _source_file(dictionary.id)
    repository.source_files[source_file.id] = source_file
    object_storage = FakeObjectStorage(fail=True)
    service = DeleteDictionaryService(
        lambda: MemorySourcesUnitOfWork(repository), object_storage
    )

    service.delete(dictionary.id, OWNER_ID)

    assert dictionary.id not in repository.dictionaries


def test_delete_not_owned_raises_access_error_without_deleting() -> None:
    repository = MemorySourcesRepository()
    dictionary = _dictionary(owner_id=OTHER_OWNER_ID)
    repository.dictionaries[dictionary.id] = dictionary
    object_storage = FakeObjectStorage()
    service = DeleteDictionaryService(
        lambda: MemorySourcesUnitOfWork(repository), object_storage
    )

    try:
        service.delete(dictionary.id, OWNER_ID)
    except DictionaryAccessError:
        pass
    else:
        raise AssertionError("expected DictionaryAccessError")
    assert dictionary.id in repository.dictionaries
