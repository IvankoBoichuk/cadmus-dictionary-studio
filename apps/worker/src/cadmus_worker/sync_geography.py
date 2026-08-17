"""One-off CLI: sync geography reference data from decentralization.ua.

Run via ``make sync-geography``. Triggered manually only (no Celery task, no
scheduled beat) -- see ADR-0007 for why this stays a plain, human-invoked
command rather than an HTTP-triggerable endpoint or a scheduled job.

Exits non-zero only when an entity type's sync outright fails
(``GeographySyncStatus.FAILED``); a partial sync (some records parsed
successfully, others didn't) is not treated as a hard failure.
"""

import sys

from cadmus.config import Settings
from cadmus.geography import GeographySyncStatus, SyncGeographyService, SyncSummary
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.geography import create_geography_unit_of_work_factory
from cadmus.infrastructure.geography_client import create_decentralization_api_client


def _run_sync(service: SyncGeographyService) -> SyncSummary:
    return service.sync_all()


def _format_summary(summary: SyncSummary) -> str:
    lines = ["geography sync summary:"]
    for label, run in (
        ("areas", summary.areas),
        ("regions", summary.regions),
        ("communities", summary.communities),
    ):
        lines.append(
            f"  {label}: status={run.status.value} "
            f"synced={run.records_synced} failed={run.records_failed}"
            + (f" error={run.error_message!r}" if run.error_message else "")
        )
    return "\n".join(lines)


def _has_failed_run(summary: SyncSummary) -> bool:
    return any(
        run.status is GeographySyncStatus.FAILED
        for run in (summary.areas, summary.regions, summary.communities)
    )


def main() -> None:
    settings = Settings()
    engine = create_database_engine(settings)
    unit_of_work_factory = create_geography_unit_of_work_factory(engine)
    client = create_decentralization_api_client(settings)
    service = SyncGeographyService(unit_of_work_factory, client)

    summary = _run_sync(service)
    print(_format_summary(summary))

    if _has_failed_run(summary):
        sys.exit(1)


if __name__ == "__main__":
    main()
