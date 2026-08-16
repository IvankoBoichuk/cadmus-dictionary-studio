"""Thin Celery entrypoints calling processing and sources application functions."""

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from io import BytesIO
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, cast
from uuid import UUID, uuid4

import cadmus.infrastructure.identity  # noqa: F401 -- registers `users` for FKs
from cadmus.config import Settings
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.object_storage import create_object_storage
from cadmus.infrastructure.source_pages_queue import CeleryPagesQueue
from cadmus.infrastructure.sources import (
    PyPdfInspector,
    PypdfiumPageRenderer,
    create_sources_unit_of_work_factory,
)
from cadmus.processing import TEST_TASK_NAME, execute_test_task
from cadmus.sources import (
    INSPECT_SOURCE_TASK_NAME,
    SPLIT_PAGES_TASK_NAME,
    CompleteSourceInspectionService,
    DictionaryPage,
    InvalidPdfError,
    ObjectNotFoundError,
    ObjectStorage,
    PdfInspector,
    PdfPageRenderer,
    RecordPageSplitService,
    SourcePagesQueue,
    SourcePagesQueueUnavailableError,
    SourcesUnitOfWorkFactory,
)
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from cadmus_worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_INSPECTION_SPOOL_MAX_BYTES = 64 * 1024 * 1024
_SPLIT_SPOOL_MAX_BYTES = 64 * 1024 * 1024


def _log_task_event(event: str, task_id: str) -> None:
    logger.info(json.dumps({"event": event, "task_id": task_id}, sort_keys=True))


@celery_app.task(bind=True, name=TEST_TASK_NAME)  # type: ignore[untyped-decorator]
def run_test_task(task: Task, value: str) -> dict[str, str]:
    """Run the deterministic infrastructure smoke task."""
    task_id = str(task.request.id)
    _log_task_event("test_task_started", task_id)
    result = execute_test_task(value)
    _log_task_event("test_task_succeeded", task_id)
    return result


@dataclass(frozen=True)
class _InspectionDependencies:
    unit_of_work_factory: SourcesUnitOfWorkFactory
    object_storage: ObjectStorage
    inspector: PdfInspector
    completion_service: CompleteSourceInspectionService
    pages_queue: SourcePagesQueue


@lru_cache(maxsize=1)
def _inspection_dependencies() -> _InspectionDependencies:
    settings = Settings()
    engine = create_database_engine(settings)
    unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    return _InspectionDependencies(
        unit_of_work_factory=unit_of_work_factory,
        object_storage=create_object_storage(settings),
        inspector=PyPdfInspector(),
        completion_service=CompleteSourceInspectionService(unit_of_work_factory),
        pages_queue=CeleryPagesQueue(celery_app),
    )


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=INSPECT_SOURCE_TASK_NAME,
    soft_time_limit=25,
    time_limit=45,
)
def inspect_dictionary_source(task: Task, source_file_id: str) -> dict[str, str]:
    """Extract page count from a stored PDF, or mark it as failed.

    Only this worker process ever performs a structural PDF parse; the API
    process only did cheap signature/size/checksum checks before storing it.
    """
    task_id = str(task.request.id)
    _log_task_event("source_inspection_started", task_id)
    dependencies = _inspection_dependencies()
    file_id = UUID(source_file_id)

    with dependencies.unit_of_work_factory() as unit_of_work:
        source_file = unit_of_work.sources.get_source_file_by_id(file_id)
    if source_file is None:
        _log_task_event("source_inspection_skipped_missing", task_id)
        return {"status": "skipped"}

    spooled_file: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
        max_size=_INSPECTION_SPOOL_MAX_BYTES
    )
    buffer = cast(BinaryIO, spooled_file)
    try:
        try:
            dependencies.object_storage.download(source_file.storage_key, buffer)
        except ObjectNotFoundError:
            dependencies.completion_service.complete(
                file_id, error="Stored PDF object is missing."
            )
            _log_task_event("source_inspection_failed", task_id)
            return {"status": "failed"}

        buffer.seek(0)
        try:
            page_count = dependencies.inspector.page_count(buffer)
        except InvalidPdfError as error:
            dependencies.completion_service.complete(file_id, error=str(error))
            _log_task_event("source_inspection_failed", task_id)
            return {"status": "failed"}
        except SoftTimeLimitExceeded:
            dependencies.completion_service.complete(
                file_id, error="PDF inspection exceeded the time limit."
            )
            _log_task_event("source_inspection_timed_out", task_id)
            return {"status": "failed"}
    finally:
        buffer.close()

    dependencies.completion_service.complete(file_id, page_count=page_count)
    _log_task_event("source_inspection_succeeded", task_id)
    try:
        dependencies.pages_queue.enqueue_split(file_id)
    except SourcePagesQueueUnavailableError:
        logger.warning("page split queue unavailable; leaving pages pending")
    return {"status": "verified", "page_count": str(page_count)}


@dataclass(frozen=True)
class _PageSplitDependencies:
    unit_of_work_factory: SourcesUnitOfWorkFactory
    object_storage: ObjectStorage
    renderer: PdfPageRenderer
    result_service: RecordPageSplitService


@lru_cache(maxsize=1)
def _page_split_dependencies() -> _PageSplitDependencies:
    settings = Settings()
    engine = create_database_engine(settings)
    unit_of_work_factory = create_sources_unit_of_work_factory(engine)
    return _PageSplitDependencies(
        unit_of_work_factory=unit_of_work_factory,
        object_storage=create_object_storage(settings),
        renderer=PypdfiumPageRenderer(),
        result_service=RecordPageSplitService(unit_of_work_factory),
    )


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=SPLIT_PAGES_TASK_NAME,
    soft_time_limit=1500,
    time_limit=1800,
)
def split_dictionary_pages(task: Task, source_file_id: str) -> dict[str, str]:
    """Render every page of a stored PDF to an image, or mark the split failed.

    Only this worker process ever rasterizes pages; it downloads the PDF
    that ``inspect_dictionary_source`` already verified is well-formed.
    """
    task_id = str(task.request.id)
    _log_task_event("page_split_started", task_id)
    dependencies = _page_split_dependencies()
    file_id = UUID(source_file_id)

    with dependencies.unit_of_work_factory() as unit_of_work:
        source_file = unit_of_work.sources.get_source_file_by_id(file_id)
    if source_file is None:
        _log_task_event("page_split_skipped_missing", task_id)
        return {"status": "skipped"}

    spooled_file: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
        max_size=_SPLIT_SPOOL_MAX_BYTES
    )
    buffer = cast(BinaryIO, spooled_file)
    try:
        try:
            dependencies.object_storage.download(source_file.storage_key, buffer)
        except ObjectNotFoundError:
            dependencies.result_service.record_failure(
                file_id, "Stored PDF object is missing."
            )
            _log_task_event("page_split_failed", task_id)
            return {"status": "failed"}

        buffer.seek(0)
        pages: list[DictionaryPage] = []
        try:
            for rendered in dependencies.renderer.render_pages(buffer):
                key = (
                    f"sources/{source_file.dictionary_id}/pages/"
                    f"{rendered.page_index:05d}.png"
                )
                dependencies.object_storage.upload(
                    key,
                    BytesIO(rendered.content),
                    len(rendered.content),
                    "image/png",
                )
                pages.append(
                    DictionaryPage(
                        id=uuid4(),
                        source_file_id=file_id,
                        page_index=rendered.page_index,
                        processed_asset_key=key,
                        width=rendered.width,
                        height=rendered.height,
                        checksum_sha256=hashlib.sha256(rendered.content).hexdigest(),
                        created_at=datetime.now(UTC),
                    )
                )
        except InvalidPdfError as error:
            dependencies.result_service.record_failure(file_id, str(error))
            _log_task_event("page_split_failed", task_id)
            return {"status": "failed"}
        except SoftTimeLimitExceeded:
            dependencies.result_service.record_failure(
                file_id, "Page splitting exceeded the time limit."
            )
            _log_task_event("page_split_timed_out", task_id)
            return {"status": "failed"}
    finally:
        buffer.close()

    dependencies.result_service.record_success(file_id, pages)
    _log_task_event("page_split_succeeded", task_id)
    return {"status": "completed", "page_count": str(len(pages))}
