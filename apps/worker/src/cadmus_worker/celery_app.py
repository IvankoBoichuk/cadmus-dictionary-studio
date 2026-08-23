"""Celery worker composition root."""

import logging

from cadmus.config import Settings
from celery import Celery
from celery.signals import after_setup_logger


@after_setup_logger.connect  # type: ignore[untyped-decorator]
def suppress_task_result_logging(**_: object) -> None:
    """Keep Celery success logs from echoing potentially untrusted task results."""
    logging.getLogger("celery.app.trace").setLevel(logging.WARNING)


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
