from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from types import TracebackType
from typing import BinaryIO
from uuid import UUID, uuid4

import pytest
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
    DictionaryStatus,
    DuplicateSourceError,
    InspectionStatus,
    InvalidUploadError,
    SourceFile,
    SourceInspectionQueueUnavailableError,
    UploadDictionaryService,
    UploadTooLargeError,
)

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
VALID_PDF_BYTES = b"%PDF-1.4\n%mock pdf body for upload-layer tests\n%%EOF"


@dataclass
class MemorySourcesRepository:
    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    events: list[DictionaryEvent] = field(default_factory=list)

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
        for source_file in self.source_files.values():
            if source_file.checksum_sha256 != checksum_sha256:
                continue
            dictionary = self.dictionaries.get(source_file.dictionary_id)
            if dictionary is not None and dictionary.owner_id == owner_id:
                return dictionary
        return None

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
        raise AssertionError("not used by upload")

    def replace_languages(
        self, dictionary_id: UUID, languages: Sequence[DictionaryLanguage]
    ) -> None:
        raise AssertionError("not used by upload")

    def add_event(self, event: DictionaryEvent) -> None:
        self.events.append(event)

    def replace_pages(
        self, source_file_id: UUID, pages: Sequence[DictionaryPage]
    ) -> None:
        raise AssertionError("not used by upload")

    def list_source_files_pending_page_split(self) -> list[SourceFile]:
        raise AssertionError("not used by upload")

    def get_page(self, source_file_id: UUID, page_index: int) -> DictionaryPage | None:
        raise AssertionError("not used by upload")

    def list_dictionaries_for_owner(self, owner_id: UUID) -> list[Dictionary]:
        raise AssertionError("not used by upload")

    def delete_dictionary(self, dictionary_id: UUID) -> None:
        raise AssertionError("not used by upload")

    def list_abbreviations(self, dictionary_id: UUID) -> list[Abbreviation]:
        raise AssertionError("not used by upload")

    def get_abbreviation(
        self, dictionary_id: UUID, abbreviation_id: UUID
    ) -> Abbreviation | None:
        raise AssertionError("not used by upload")

    def find_abbreviation_duplicate(
        self,
        dictionary_id: UUID,
        category: AbbreviationCategory,
        language_code: str | None,
        abbreviation: str,
        exclude_id: UUID | None = None,
    ) -> Abbreviation | None:
        raise AssertionError("not used by upload")

    def add_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by upload")

    def update_abbreviation(self, abbreviation: Abbreviation) -> None:
        raise AssertionError("not used by upload")

    def replace_abbreviation_variants(
        self, abbreviation_id: UUID, variants: Sequence[AbbreviationVariant]
    ) -> None:
        raise AssertionError("not used by upload")

    def delete_abbreviation(self, dictionary_id: UUID, abbreviation_id: UUID) -> None:
        raise AssertionError("not used by upload")

    def list_settlement_mappings(
        self, dictionary_id: UUID
    ) -> list[DictionarySettlementMapping]:
        raise AssertionError("not used by upload")

    def get_settlement_mapping(
        self, dictionary_id: UUID, mapping_id: UUID
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by upload")

    def find_settlement_mapping_duplicate(
        self,
        dictionary_id: UUID,
        source_label_key: str,
        settlement_id: UUID | None = None,
        exclude_id: UUID | None = None,
    ) -> DictionarySettlementMapping | None:
        raise AssertionError("not used by upload")

    def add_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by upload")

    def update_settlement_mapping(self, mapping: DictionarySettlementMapping) -> None:
        raise AssertionError("not used by upload")

    def delete_settlement_mapping(self, dictionary_id: UUID, mapping_id: UUID) -> None:
        raise AssertionError("not used by upload")


class MemorySourcesUnitOfWork:
    """Copy-on-write fake: writes only reach ``shared`` on a successful commit.

    This mirrors the real SQLAlchemy unit of work, where ``session.add()``
    only stages objects and a failed/absent commit leaves the durable store
    untouched (the real adapter also rolls back on ``__exit__`` with an
    exception).
    """

    def __init__(
        self, shared: MemorySourcesRepository, fail_commit: bool = False
    ) -> None:
        self._shared = shared
        self.sources = MemorySourcesRepository(
            dictionaries=dict(shared.dictionaries),
            source_files=dict(shared.source_files),
            events=list(shared.events),
        )
        self.committed = False
        self._fail_commit = fail_commit

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
        if self._fail_commit:
            raise RuntimeError("database is unavailable")
        self._shared.dictionaries = self.sources.dictionaries
        self._shared.source_files = self.sources.source_files
        self._shared.events = self.sources.events
        self.committed = True


@dataclass
class FakeObjectStorage:
    uploaded: dict[str, bytes] = field(default_factory=dict)
    deleted: list[str] = field(default_factory=list)
    fail_upload: bool = False

    def upload(
        self, key: str, source: BinaryIO, length: int, content_type: str
    ) -> None:
        if self.fail_upload:
            raise RuntimeError("object storage is unavailable")
        self.uploaded[key] = source.read()

    def download(self, key: str, destination: BinaryIO) -> None:
        destination.write(self.uploaded[key])

    def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.uploaded.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        for key in [key for key in self.uploaded if key.startswith(prefix)]:
            self.delete(key)


@dataclass
class FakeInspectionQueue:
    enqueued: list[UUID] = field(default_factory=list)
    fail: bool = False

    def enqueue_inspection(self, source_file_id: UUID) -> None:
        if self.fail:
            raise SourceInspectionQueueUnavailableError("queue is unavailable")
        self.enqueued.append(source_file_id)


def _service(
    repository: MemorySourcesRepository | None = None,
    object_storage: FakeObjectStorage | None = None,
    inspection_queue: FakeInspectionQueue | None = None,
    max_upload_size_bytes: int = 1024,
    fail_commit: bool = False,
) -> tuple[
    UploadDictionaryService,
    MemorySourcesRepository,
    FakeObjectStorage,
    FakeInspectionQueue,
]:
    repository = repository or MemorySourcesRepository()
    object_storage = object_storage or FakeObjectStorage()
    inspection_queue = inspection_queue or FakeInspectionQueue()
    service = UploadDictionaryService(
        unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
            repository, fail_commit=fail_commit
        ),
        object_storage=object_storage,
        inspection_queue=inspection_queue,
        max_upload_size_bytes=max_upload_size_bytes,
        clock=lambda: NOW,
    )
    return service, repository, object_storage, inspection_queue


def test_successful_upload_creates_draft_and_stores_technical_metadata() -> None:
    service, repository, object_storage, inspection_queue = _service()
    owner_id = uuid4()

    outcome = service.upload(
        owner_id, "Словник.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
    )

    assert outcome.dictionary.status is DictionaryStatus.DRAFT
    assert outcome.dictionary.owner_id == owner_id
    assert outcome.source_file.original_filename == "Словник.pdf"
    assert outcome.source_file.mime_type == "application/pdf"
    assert outcome.source_file.byte_size == len(VALID_PDF_BYTES)
    assert outcome.source_file.inspection_status is InspectionStatus.PENDING
    assert outcome.source_file.page_count is None
    assert outcome.missing_required_fields == ["title", "languages", "legal_status"]

    stored_key = outcome.source_file.storage_key
    assert object_storage.uploaded[stored_key] == VALID_PDF_BYTES
    assert repository.dictionaries[outcome.dictionary.id] is outcome.dictionary
    assert inspection_queue.enqueued == [outcome.source_file.id]
    event_types = [event.event_type for event in repository.events]
    assert event_types == ["created", "source_uploaded"]


def test_upload_rejects_non_pdf_extension() -> None:
    service, *_ = _service()

    with pytest.raises(InvalidUploadError) as error:
        service.upload(
            uuid4(), "dictionary.txt", "application/pdf", BytesIO(VALID_PDF_BYTES)
        )
    assert error.value.field == "file"


def test_upload_rejects_mismatched_declared_content_type() -> None:
    service, *_ = _service()

    with pytest.raises(InvalidUploadError):
        service.upload(uuid4(), "dictionary.pdf", "image/png", BytesIO(VALID_PDF_BYTES))


def test_upload_rejects_spoofed_file_with_wrong_signature() -> None:
    service, *_ = _service()
    spoofed = b"this is not really a pdf file, just renamed"

    with pytest.raises(InvalidUploadError):
        service.upload(uuid4(), "dictionary.pdf", "application/pdf", BytesIO(spoofed))


def test_upload_rejects_files_over_the_configured_size_limit() -> None:
    service, repository, object_storage, _ = _service(max_upload_size_bytes=8)

    with pytest.raises(UploadTooLargeError):
        service.upload(
            uuid4(), "dictionary.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
        )

    assert repository.dictionaries == {}
    assert object_storage.uploaded == {}


def test_upload_rejects_empty_file() -> None:
    service, *_ = _service()

    with pytest.raises(InvalidUploadError):
        service.upload(uuid4(), "dictionary.pdf", "application/pdf", BytesIO(b""))


def test_duplicate_checksum_is_rejected_without_creating_a_new_copy() -> None:
    service, repository, object_storage, _ = _service()
    owner_id = uuid4()
    first = service.upload(
        owner_id, "first.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
    )

    with pytest.raises(DuplicateSourceError) as error:
        service.upload(
            owner_id, "again.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
        )

    assert error.value.dictionary_id == first.dictionary.id
    assert len(repository.dictionaries) == 1
    assert len(object_storage.uploaded) == 1


def test_duplicate_detection_is_scoped_to_the_calling_owner() -> None:
    service, repository, _, _ = _service()
    other_owner_upload = service.upload(
        uuid4(), "first.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
    )

    outcome = service.upload(
        uuid4(), "same-content.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
    )

    assert outcome.dictionary.id != other_owner_upload.dictionary.id
    assert len(repository.dictionaries) == 2


def test_storage_failure_leaves_no_partially_created_draft() -> None:
    object_storage = FakeObjectStorage(fail_upload=True)
    service, repository, _, _ = _service(object_storage=object_storage)

    with pytest.raises(RuntimeError):
        service.upload(
            uuid4(), "dictionary.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
        )

    assert repository.dictionaries == {}


def test_database_failure_after_storage_success_deletes_the_orphaned_object() -> None:
    repository = MemorySourcesRepository()
    object_storage = FakeObjectStorage()
    service, _, _, _ = _service(
        repository=repository, object_storage=object_storage, fail_commit=True
    )

    with pytest.raises(RuntimeError):
        service.upload(
            uuid4(), "dictionary.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
        )

    assert repository.dictionaries == {}
    assert object_storage.uploaded == {}
    assert len(object_storage.deleted) == 1


def test_inspection_queue_unavailability_does_not_fail_the_upload() -> None:
    inspection_queue = FakeInspectionQueue(fail=True)
    service, repository, _, _ = _service(inspection_queue=inspection_queue)

    outcome = service.upload(
        uuid4(), "dictionary.pdf", "application/pdf", BytesIO(VALID_PDF_BYTES)
    )

    stored = repository.source_files[outcome.source_file.id]
    assert stored.inspection_status is InspectionStatus.PENDING
