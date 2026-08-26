"""Celery entrypoint for queuing OCR across every unscanned page of a
dictionary, kept separate from ``ocr_tasks.py`` (one job per page) -- this
is a different capability: an orchestrating job that walks many pages and
persists draft lexemes itself, no manual per-suggestion accept step.
"""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from tempfile import SpooledTemporaryFile
from typing import BinaryIO, cast
from uuid import UUID, uuid4

from cadmus.config import Settings
from cadmus.identity import IdentityUnitOfWorkFactory
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.identity import create_identity_unit_of_work_factory
from cadmus.infrastructure.lexicography import (
    create_lexicography_unit_of_work_factory,
)
from cadmus.infrastructure.notifications import (
    GmailNotificationChannel,
    TelegramNotificationChannel,
)
from cadmus.infrastructure.object_storage import create_object_storage
from cadmus.infrastructure.ocr import OcrExecutionError, TesseractAltoOcrProvider
from cadmus.infrastructure.sources import create_sources_unit_of_work_factory
from cadmus.lexicography import (
    SCAN_DICTIONARY_TASK_NAME,
    Lexeme,
    LexemeOrigin,
    LexemeSuggestion,
    find_overlapping_lexeme,
    resolve_ocr_language,
    validate_lexeme_fields,
)
from cadmus.lexicography.ports import LexicographyUnitOfWorkFactory
from cadmus.notifications import (
    Notification,
    NotificationRecipient,
    NotificationService,
)
from cadmus.sources import (
    DictionaryAccessError,
    DictionaryPage,
    ObjectNotFoundError,
    ObjectStorage,
    SourcesUnitOfWorkFactory,
)
from cadmus.sources.application import GetDictionaryService
from celery import Task

from cadmus_worker.celery_app import celery_app

logger = logging.getLogger(__name__)

_PAGE_IMAGE_SPOOL_MAX_BYTES = 8 * 1024 * 1024


def _log_task_event(event: str, task_id: str, **fields: object) -> None:
    logger.info(
        json.dumps({"event": event, "task_id": task_id, **fields}, sort_keys=True)
    )


@dataclass(frozen=True)
class _ScanDependencies:
    dictionary_pages: GetDictionaryService
    lexicography_unit_of_work_factory: LexicographyUnitOfWorkFactory
    identity_unit_of_work_factory: IdentityUnitOfWorkFactory
    object_storage: ObjectStorage
    ocr_provider: TesseractAltoOcrProvider
    notification_service: NotificationService


@lru_cache(maxsize=1)
def _scan_dependencies() -> _ScanDependencies:
    settings = Settings()
    engine = create_database_engine(settings)
    sources_unit_of_work_factory: SourcesUnitOfWorkFactory = (
        create_sources_unit_of_work_factory(engine)
    )
    return _ScanDependencies(
        dictionary_pages=GetDictionaryService(sources_unit_of_work_factory),
        lexicography_unit_of_work_factory=create_lexicography_unit_of_work_factory(
            engine
        ),
        identity_unit_of_work_factory=create_identity_unit_of_work_factory(engine),
        object_storage=create_object_storage(settings),
        notification_service=NotificationService(
            channels=[
                GmailNotificationChannel(settings),
                TelegramNotificationChannel(settings),
            ]
        ),
        ocr_provider=TesseractAltoOcrProvider(
            timeout_seconds=settings.ocr_task_timeout_seconds
        ),
    )


def _scan_one_page(
    deps: _ScanDependencies,
    page: DictionaryPage,
    language: str,
    dictionary_id: UUID,
    actor_id: UUID,
    task_id: str,
) -> int:
    """OCR one page and persist surviving suggestions as draft lexemes.

    Never raises: a single bad page (missing image, Tesseract failure,
    timeout) is logged and skipped so it can't halt the rest of the queue.
    """
    spooled_file: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(
        max_size=_PAGE_IMAGE_SPOOL_MAX_BYTES
    )
    buffer = cast(BinaryIO, spooled_file)
    suggestions: list[LexemeSuggestion] = []
    try:
        try:
            deps.object_storage.download(page.processed_asset_key, buffer)
        except ObjectNotFoundError:
            _log_task_event(
                "dictionary_scan_page_image_missing", task_id, page_id=str(page.id)
            )
            return 0
        buffer.seek(0)
        image_bytes = buffer.read()
        try:
            suggestions = deps.ocr_provider.suggest_words(image_bytes, language)
        except OcrExecutionError as error:
            _log_task_event(
                "dictionary_scan_page_ocr_failed",
                task_id,
                page_id=str(page.id),
                error=str(error),
            )
            return 0
    finally:
        buffer.close()

    if not suggestions:
        return 0

    now = datetime.now(UTC)
    created = 0
    with deps.lexicography_unit_of_work_factory() as unit_of_work:
        existing = unit_of_work.lexicography.list_lexemes_for_page(page.id)
        for suggestion in suggestions:
            if (
                find_overlapping_lexeme(
                    x=suggestion.x,
                    y=suggestion.y,
                    width=suggestion.width,
                    height=suggestion.height,
                    existing=existing,
                )
                is not None
            ):
                continue
            errors = validate_lexeme_fields(
                source_text=suggestion.source_text,
                x=suggestion.x,
                y=suggestion.y,
                width=suggestion.width,
                height=suggestion.height,
                page_width=page.width,
                page_height=page.height,
            )
            if errors:
                continue
            lexeme = Lexeme(
                id=uuid4(),
                dictionary_id=dictionary_id,
                page_id=page.id,
                source_text=suggestion.source_text.strip(),
                x=suggestion.x,
                y=suggestion.y,
                width=suggestion.width,
                height=suggestion.height,
                origin=LexemeOrigin.OCR,
                created_at=now,
                created_by=actor_id,
                updated_at=now,
                updated_by=actor_id,
            )
            unit_of_work.lexicography.add_lexeme(lexeme)
            existing.append(lexeme)
            created += 1
        if created:
            unit_of_work.commit()
    return created


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name=SCAN_DICTIONARY_TASK_NAME,
    soft_time_limit=3600,
    time_limit=3660,
)
def scan_dictionary_pages(
    task: Task, dictionary_id: str, actor_id: str
) -> dict[str, object]:
    """Run OCR on every unscanned page of a dictionary, in viewer order,
    creating a draft lexeme (``LexemeOrigin.OCR``) per surviving suggestion.

    A page already carrying at least one lexeme is skipped -- mirrors
    BH-57's own "processed" definition, so re-running the queue is safe and
    only fills gaps rather than duplicating a reviewer's manual work.
    """
    task_id = str(task.request.id)
    deps = _scan_dependencies()
    dictionary_uuid = UUID(dictionary_id)
    actor_uuid = UUID(actor_id)

    try:
        dictionary = deps.dictionary_pages.get(dictionary_uuid, actor_uuid)
        pages = deps.dictionary_pages.list_viewable_pages(dictionary_uuid, actor_uuid)
    except DictionaryAccessError:
        _log_task_event("dictionary_scan_not_found", task_id)
        return {"status": "failed", "error": "dictionary not found"}

    language = resolve_ocr_language(
        [language.language_code for language in dictionary.languages]
    )

    with deps.lexicography_unit_of_work_factory() as unit_of_work:
        already_processed = unit_of_work.lexicography.list_page_ids_with_lexemes(
            dictionary_uuid
        )

    total_pages = len(pages)
    processed_pages = 0
    created_lexemes = 0
    _log_task_event("dictionary_scan_started", task_id, total_pages=total_pages)

    for page in pages:
        if page.id not in already_processed:
            created_lexemes += _scan_one_page(
                deps, page, language, dictionary_uuid, actor_uuid, task_id
            )
        processed_pages += 1
        task.update_state(
            state="PROGRESS",
            meta={
                "processed_pages": processed_pages,
                "total_pages": total_pages,
                "created_lexemes": created_lexemes,
            },
        )

    _log_task_event(
        "dictionary_scan_succeeded",
        task_id,
        processed_pages=processed_pages,
        created_lexemes=created_lexemes,
    )
    _notify_scan_complete(
        deps,
        actor_uuid,
        dictionary.title or "Без назви",
        processed_pages,
        created_lexemes,
        task_id,
    )
    return {
        "status": "succeeded",
        "processed_pages": processed_pages,
        "total_pages": total_pages,
        "created_lexemes": created_lexemes,
    }


def _build_scan_notification(
    dictionary_title: str, processed_pages: int, created_lexemes: int
) -> Notification:
    return Notification(
        subject="Оцифрування словника завершено",
        body=(
            f"Оцифрування словника «{dictionary_title}» завершено.\n\n"
            f"Оброблено сторінок: {processed_pages}\n"
            f"Створено чорнових лексем: {created_lexemes}"
        ),
    )


def _notify_scan_complete(
    deps: _ScanDependencies,
    owner_id: UUID,
    dictionary_title: str,
    processed_pages: int,
    created_lexemes: int,
    task_id: str,
) -> None:
    """Best-effort: a notification problem must never fail a finished scan."""
    try:
        with deps.identity_unit_of_work_factory() as unit_of_work:
            owner = unit_of_work.users.get_user(owner_id)
        if owner is None:
            return
        recipient = NotificationRecipient(
            email=owner.email, telegram_chat_id=owner.telegram_chat_id
        )
        notification = _build_scan_notification(
            dictionary_title, processed_pages, created_lexemes
        )
        failed_channels = deps.notification_service.notify(recipient, notification)
        if failed_channels:
            _log_task_event(
                "dictionary_scan_notification_failed",
                task_id,
                channels=failed_channels,
            )
    except Exception:  # notifying is a side-channel, never fatal to a finished scan
        logger.exception(
            "dictionary_scan_notification_error task_id=%s owner_id=%s",
            task_id,
            owner_id,
        )
