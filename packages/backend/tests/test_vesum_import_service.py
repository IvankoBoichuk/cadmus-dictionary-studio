"""VesumImportService.import_visual_lines: batching, bulk-load hooks, summary."""

from types import TracebackType
from typing import cast
from uuid import UUID

import pytest
from cadmus.reference_lexicon import (
    ReferenceLexiconUnitOfWork,
    VesumImportService,
)
from cadmus.reference_lexicon.domain import ReferenceLexicon, VesumRecord


class RecordingRepository:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.lexicon: ReferenceLexicon | None = None
        self.deactivated: list[UUID] = []
        self.batches: list[int] = []

    def upsert_lexicon(self, lexicon: ReferenceLexicon) -> None:
        self.calls.append("upsert_lexicon")
        self.lexicon = lexicon

    def deactivate_content(self, lexicon_id: UUID) -> None:
        self.calls.append("deactivate_content")
        self.deactivated.append(lexicon_id)

    def begin_bulk_load(self) -> None:
        self.calls.append("begin_bulk_load")

    def finish_bulk_load(self) -> None:
        self.calls.append("finish_bulk_load")

    def upsert_records(self, records: list[VesumRecord]) -> None:
        self.calls.append("upsert_records")
        self.batches.append(len(records))


class RecordingUnitOfWork:
    def __init__(self, repository: RecordingRepository) -> None:
        self.reference_lexicon = repository
        self.committed = False

    def __enter__(self) -> "RecordingUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    def commit(self) -> None:
        self.reference_lexicon.calls.append("commit")
        self.committed = True


def _make(batch_size: int = 5_000) -> tuple[VesumImportService, RecordingRepository]:
    repo = RecordingRepository()
    uow = RecordingUnitOfWork(repo)
    service = VesumImportService(
        cast(
            "type[ReferenceLexiconUnitOfWork]",
            lambda: cast(ReferenceLexiconUnitOfWork, uow),
        ),
        batch_size=batch_size,
    )
    return service, repo


_LINES = [
    "білий adj:m:v_naz\n",
    "  біла adj:f:v_naz\n",
    "  біле adj:n:v_naz\n",
    "\n",
    "чорний adj:m:v_naz\n",
    "  чорна adj:f:v_naz\n",
]


def test_import_runs_bulk_load_hooks_around_the_batches_then_commits() -> None:
    service, repo = _make()

    summary = service.import_visual_lines(
        iter(_LINES), version="6.8.5", checksum="a" * 64
    )

    assert repo.calls == [
        "upsert_lexicon",
        "deactivate_content",
        "begin_bulk_load",
        "upsert_records",
        "finish_bulk_load",
        "commit",
    ]
    assert summary.rows_read == 6
    assert summary.rows_imported == 5
    assert summary.blank_rows == 1
    assert repo.lexicon is not None and repo.lexicon.version == "6.8.5"


def test_import_flushes_full_batches_and_a_final_partial_batch() -> None:
    service, repo = _make(batch_size=2)

    service.import_visual_lines(iter(_LINES), version="6.8.5", checksum="a" * 64)

    assert repo.batches == [2, 2, 1]
    assert repo.calls.index("begin_bulk_load") < repo.calls.index("upsert_records")
    assert repo.calls.index("upsert_records") < repo.calls.index("finish_bulk_load")
    assert repo.calls[-1] == "commit"


@pytest.mark.parametrize(
    ("version", "checksum"),
    [("", "a" * 64), ("6.8.5", "  ")],
)
def test_import_rejects_missing_version_or_checksum(
    version: str, checksum: str
) -> None:
    service, _repo = _make()
    with pytest.raises(ValueError):
        service.import_visual_lines(iter(_LINES), version=version, checksum=checksum)
