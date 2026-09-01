"""Celery worker composition root."""

import logging
from collections.abc import Callable
from functools import lru_cache

from cadmus.config import Settings
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.processing import create_processing_unit_of_work_factory
from cadmus.processing import ProcessingTaskStatusRecorder
from celery import Celery
from celery.signals import (
    after_setup_logger,
    task_failure,
    task_postrun,
    task_prerun,
    task_revoked,
)

logger = logging.getLogger(__name__)


@after_setup_logger.connect  # type: ignore[untyped-decorator]
def suppress_task_result_logging(**_: object) -> None:
    """Keep Celery success logs from echoing potentially untrusted task results."""
    logging.getLogger("celery.app.trace").setLevel(logging.WARNING)


@lru_cache(maxsize=1)
def _status_recorder() -> ProcessingTaskStatusRecorder:
    engine = create_database_engine(Settings())
    return ProcessingTaskStatusRecorder(create_processing_unit_of_work_factory(engine))


def _describe_exception(exception: BaseException | None) -> str:
    if exception is None:
        return "Задача завершилася помилкою."
    return f"{type(exception).__name__}: {exception}"


def _record_safely(what: str, task_id: object, apply: Callable[[], None]) -> None:
    """Run one registry write. The task registry is a best-effort side
    channel: a deployment may not have provisioned it, so a failure here is
    logged at debug and swallowed -- it must never disturb the task."""
    try:
        apply()
    except Exception:  # pragma: no cover - defensive, exercised via debug logs
        logger.debug("could not %s for task %s", what, task_id, exc_info=True)


@task_prerun.connect  # type: ignore[untyped-decorator]
def _record_task_started(task_id: str | None = None, **_: object) -> None:
    """Flip a tracked task's registry row to ``running`` (no-op if untracked)."""
    if not task_id:
        return
    _record_safely(
        "mark running", task_id, lambda: _status_recorder().mark_running(str(task_id))
    )


@task_postrun.connect  # type: ignore[untyped-decorator]
def _record_task_finished(
    task_id: str | None = None,
    retval: object = None,
    state: str | None = None,
    **_: object,
) -> None:
    """Record a terminal state from the task's return value.

    Cadmus workers report an application-level failure by returning
    ``{"status": "failed", "error": ...}`` rather than raising, so a
    ``SUCCESS`` Celery state can still mean the job did not do its work.
    Raised exceptions are handled by ``task_failure`` instead.
    """
    if not task_id or state != "SUCCESS":
        return

    def apply() -> None:
        recorder = _status_recorder()
        if isinstance(retval, dict) and retval.get("status") == "failed":
            error = retval.get("error")
            recorder.mark_failed(
                str(task_id), str(error) if error is not None else None
            )
        else:
            recorder.mark_succeeded(
                str(task_id), retval if isinstance(retval, dict) else None
            )

    _record_safely("record result", task_id, apply)


@task_failure.connect  # type: ignore[untyped-decorator]
def _record_task_failed(
    task_id: str | None = None,
    exception: BaseException | None = None,
    **_: object,
) -> None:
    if not task_id:
        return
    _record_safely(
        "mark failed",
        task_id,
        lambda: _status_recorder().mark_failed(
            str(task_id), _describe_exception(exception)
        ),
    )


@task_revoked.connect  # type: ignore[untyped-decorator]
def _record_task_revoked(request: object = None, **_: object) -> None:
    task_id = getattr(request, "id", None)
    if not task_id:
        return
    _record_safely(
        "mark revoked",
        task_id,
        lambda: _status_recorder().mark_failed(str(task_id), "Задачу скасовано."),
    )


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Create the worker with explicit, JSON-only transport configuration."""
    app_settings = settings if settings is not None else Settings()
    app = Celery(
        "cadmus-worker",
        broker=app_settings.celery_broker_url(),
        backend=app_settings.celery_result_backend_url(),
        include=[
            "cadmus_worker.tasks",
            "cadmus_worker.ocr_tasks",
            "cadmus_worker.bulk_scan_tasks",
            "cadmus_worker.article_schema_tasks",
            "cadmus_worker.entry_extraction_tasks",
        ],
    )
    app.conf.update(
        accept_content=["json"],
        broker_connection_retry=True,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"socket_connect_timeout": 2},
        result_backend_transport_options={"socket_connect_timeout": 2},
        result_expires=3600,
        result_serializer="json",
        task_serializer="json",
        task_soft_time_limit=30,
        task_time_limit=60,
        task_track_started=True,
    )
    return app


celery_app = create_celery_app()
