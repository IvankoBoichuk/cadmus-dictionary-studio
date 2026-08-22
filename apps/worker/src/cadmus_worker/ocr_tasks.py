"""Thin Celery entrypoint for OCR word suggestions (ALTO), kept separate from
``tasks.py`` -- one capability per file, matching ``source_pages_queue.py``/
``source_inspection_queue.py`` already being separate from each other.
"""

import json
import logging
from dataclasses import asdict, dataclass
from functools import lru_cache
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, cast
from uuid import UUID

import cadmus.infrastructure.identity  # noqa: F401 -- registers `users` for FKs
from cadmus.config import Settings
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.object_storage import create_object_storage
from cadmus.infrastructure.ocr import OcrExecutionError, TesseractAltoOcrProvider
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.lexicography import SUGGEST_LEXEMES_TASK_NAME
from cadmus.sources import ObjectNotFoundError, ObjectStorage, SourcesUnitOfWorkFactory
from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from cadmus_worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_PAGE_IMAGE_SPOOL_MAX_BYTES = 8 * 1024 * 1024


def _log_task_event(event: str, task_id: str) -> None:
    logger.info(json.dumps({"event": event, "task_id": task_id}, sort_keys=True))


@dataclass(frozen=True)
class _OcrSuggestionDependencies:
    unit_of_work_factory: SourcesUnitOfWorkFactory
    object_storage: ObjectStorage
    ocr_provider: TesseractAltoOcrProvider


@lru_cache(maxsize=1)
def _ocr_suggestion_dependencies() -> _OcrSuggestionDependencies:
    settings = Settings()
    engine = create_database_engine(settings)
    return _OcrSuggestionDependencies(
        unit_of_work_factory=create_sources_unit_of_work_factory(engine),
        object_storage=create_object_storage(settings),
        ocr_provider=TesseractAltoOcrProvider(
            timeout_seconds=settings.ocr_task_timeout_seconds
        ),
    )


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=SUGGEST_LEXEMES_TASK_NAME,
    soft_time_limit=25,
    time_limit=30,
)
def suggest_lexemes(
    task: Task, source_file_id: str, page_id: str, language: str
) -> dict[str, object]:
    """Run Tesseract/ALTO on one already-rendered page image.

    Suggestions are returned as the task's own Celery result (JSON) and
    never written to Postgres -- see ``CeleryOcrSuggestionQueue``/
    ``SuggestLexemesService`` for how the API reads this back.
    """
    task_id = str(task.request.id)
    _log_task_event("ocr_suggestions_started", task_id)
    dependencies = _ocr_suggestion_dependencies()

    with dependencies.unit_of_work_factory() as unit_of_work:
        page = unit_of_work.sources.get_page_by_id(UUID(page_id))
    if page is None or str(page.source_file_id) != source_file_id:
        _log_task_event("ocr_suggestions_page_missing", task_id)
        return {"status": "failed", "error": "page not found"}

    spooled_file: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
        max_size=_PAGE_IMAGE_SPOOL_MAX_BYTES
    )
    buffer = cast(BinaryIO, spooled_file)
    try:
        try:
            dependencies.object_storage.download(page.processed_asset_key, buffer)
        except ObjectNotFoundError:
            _log_task_event("ocr_suggestions_image_missing", task_id)
            return {"status": "failed", "error": "page image is missing"}

        buffer.seek(0)
        image_bytes = buffer.read()
        try:
            suggestions = dependencies.ocr_provider.suggest_words(image_bytes, language)
        except OcrExecutionError as error:
            _log_task_event("ocr_suggestions_failed", task_id)
            return {"status": "failed", "error": str(error)}
        except SoftTimeLimitExceeded:
            _log_task_event("ocr_suggestions_timed_out", task_id)
            return {"status": "failed", "error": "OCR exceeded the time limit"}
    finally:
        buffer.close()

    _log_task_event("ocr_suggestions_succeeded", task_id)
    return {
        "status": "succeeded",
        "suggestions": [asdict(suggestion) for suggestion in suggestions],
    }
