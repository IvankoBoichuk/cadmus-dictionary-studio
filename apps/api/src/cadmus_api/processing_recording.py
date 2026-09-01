"""Best-effort recording of a freshly queued job into the task registry.

Monitoring must never be able to break the operation it observes, so a
failure to write the ``processing_tasks`` row is logged and swallowed --
the job is already on the queue either way.
"""

import logging
from collections.abc import Mapping
from uuid import UUID

from cadmus.processing import ProcessingTaskKind, ProcessingTaskService

logger = logging.getLogger(__name__)


def record_enqueued_task(
    service: ProcessingTaskService | None,
    *,
    dictionary_id: UUID,
    kind: ProcessingTaskKind,
    celery_task_id: str,
    enqueued_by: UUID,
    target_id: UUID | None = None,
    target_label: str | None = None,
    rerun_params: Mapping[str, object] | None = None,
) -> None:
    if service is None:
        return
    try:
        service.record_enqueued(
            dictionary_id=dictionary_id,
            kind=kind,
            celery_task_id=celery_task_id,
            enqueued_by=enqueued_by,
            target_id=target_id,
            target_label=target_label,
            rerun_params=rerun_params,
        )
    except Exception:
        logger.warning(
            "could not record %s task %s for dictionary %s",
            kind,
            celery_task_id,
            dictionary_id,
            exc_info=True,
        )
