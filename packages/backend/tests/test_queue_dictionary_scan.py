"""Whole-dictionary OCR scan queue: application behavior."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import TracebackType
from typing import cast
from uuid import UUID, uuid4

import pytest
from cadmus.lexicography import (
    DictionaryScanSnapshot,
    LexemeAccessError,
    OcrSuggestionStatus,
    QueueDictionaryScanService,
)
from cadmus.sources import (
    Dictionary,
    DictionaryPageRange,
    DictionaryStatus,
    GetDictionaryService,
    SourceFile,
    SourcesRepository,
)

NOW = datetime(2026, 8, 23, 12, 0, tzinfo=UTC)


@dataclass
class MemorySourcesRepository:
    """A minimal fake covering only what ``GetDictionaryService`` needs here."""

    dictionaries: dict[UUID, Dictionary] = field(default_factory=dict)
    source_files: dict[UUID, SourceFile] = field(default_factory=dict)
    page_ranges: dict[UUID, list[DictionaryPageRange]] = field(default_factory=dict)

    def get_dictionary(self, dictionary_id: UUID) -> Dictionary | None:
        return self.dictionaries.get(dictionary_id)

    def get_source_file(self, dictionary_id: UUID) -> SourceFile | None:
        return self.source_files.get(dictionary_id)


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
class FakeDictionaryScanQueue:
    snapshot: DictionaryScanSnapshot | None = None
    enqueued: tuple[UUID, UUID] | None = None
    returned_task_id: str = "scan-task-123"

    def enqueue_scan(self, dictionary_id: UUID, actor_id: UUID) -> str:
        self.enqueued = (dictionary_id, actor_id)
        return self.returned_task_id

    def get_scan_task(self, task_id: str) -> DictionaryScanSnapshot:
        assert self.snapshot is not None
        return self.snapshot


def _dictionary(owner_id: UUID) -> Dictionary:
    return Dictionary(
        id=uuid4(),
        owner_id=owner_id,
        status=DictionaryStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        updated_by=owner_id,
    )


class Fixture:
    def __init__(self) -> None:
        self.owner_id = uuid4()
        self.sources_repository = MemorySourcesRepository()
        self.dictionary = _dictionary(self.owner_id)
        self.sources_repository.dictionaries[self.dictionary.id] = self.dictionary

        self.dictionary_pages = GetDictionaryService(
            unit_of_work_factory=lambda: MemorySourcesUnitOfWork(
                self.sources_repository
            )
        )
        self.queue = FakeDictionaryScanQueue()
        self.service = QueueDictionaryScanService(
            dictionary_pages=self.dictionary_pages,
            queue=self.queue,
        )


def test_enqueue_passes_the_dictionary_and_actor_id() -> None:
    fixture = Fixture()

    task_id = fixture.service.enqueue(fixture.dictionary.id, fixture.owner_id)

    assert task_id == fixture.queue.returned_task_id
    assert fixture.queue.enqueued == (fixture.dictionary.id, fixture.owner_id)


def test_enqueue_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.service.enqueue(fixture.dictionary.id, uuid4())


def test_enqueue_unknown_dictionary_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.service.enqueue(uuid4(), fixture.owner_id)


def test_get_task_passes_through_running_progress() -> None:
    fixture = Fixture()
    fixture.queue.snapshot = DictionaryScanSnapshot(
        task_id="t1",
        status=OcrSuggestionStatus.RUNNING,
        processed_pages=3,
        total_pages=10,
        created_lexemes=7,
    )

    snapshot = fixture.service.get_task(fixture.dictionary.id, fixture.owner_id, "t1")

    assert snapshot.status is OcrSuggestionStatus.RUNNING
    assert snapshot.processed_pages == 3
    assert snapshot.total_pages == 10
    assert snapshot.created_lexemes == 7


def test_get_task_passes_through_failure() -> None:
    fixture = Fixture()
    fixture.queue.snapshot = DictionaryScanSnapshot(
        task_id="t1", status=OcrSuggestionStatus.FAILED, error="boom"
    )

    snapshot = fixture.service.get_task(fixture.dictionary.id, fixture.owner_id, "t1")

    assert snapshot.status is OcrSuggestionStatus.FAILED
    assert snapshot.error == "boom"


def test_get_task_actor_other_than_owner_raises_access_error() -> None:
    fixture = Fixture()

    with pytest.raises(LexemeAccessError):
        fixture.service.get_task(fixture.dictionary.id, uuid4(), "t1")
