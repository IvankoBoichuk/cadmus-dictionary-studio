from datetime import UTC, datetime
from uuid import uuid4

import pytest
from cadmus.geography import GeographyEntityType, GeographySyncStatus, SyncSummary
from cadmus.geography.domain import SyncRun
from cadmus_worker.sync_geography import _format_summary, _has_failed_run

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _run(
    entity_type: GeographyEntityType,
    status: GeographySyncStatus,
    **overrides: object,
) -> SyncRun:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "entity_type": entity_type,
        "source": "decentralization.ua",
        "started_at": NOW,
        "status": status,
        "records_synced": 1,
        "records_failed": 0,
        "completed_at": NOW,
    }
    defaults.update(overrides)
    return SyncRun(**defaults)  # type: ignore[arg-type]


def _summary(**overrides: SyncRun) -> SyncSummary:
    defaults: dict[str, SyncRun] = {
        "areas": _run(GeographyEntityType.AREA, GeographySyncStatus.SUCCEEDED),
        "regions": _run(GeographyEntityType.REGION, GeographySyncStatus.SUCCEEDED),
        "communities": _run(
            GeographyEntityType.COMMUNITY, GeographySyncStatus.SUCCEEDED
        ),
    }
    defaults.update(overrides)
    return SyncSummary(**defaults)


def test_format_summary_lists_each_entity_type() -> None:
    summary = _summary()

    text = _format_summary(summary)

    assert "areas: status=succeeded synced=1 failed=0" in text
    assert "regions: status=succeeded" in text
    assert "communities: status=succeeded" in text


def test_format_summary_includes_error_message_when_present() -> None:
    summary = _summary(
        communities=_run(
            GeographyEntityType.COMMUNITY,
            GeographySyncStatus.FAILED,
            records_synced=0,
            error_message="boom",
        )
    )

    text = _format_summary(summary)

    assert "error='boom'" in text


@pytest.mark.parametrize(
    "status", [GeographySyncStatus.SUCCEEDED, GeographySyncStatus.PARTIAL]
)
def test_has_failed_run_is_false_for_succeeded_and_partial(
    status: GeographySyncStatus,
) -> None:
    summary = _summary(communities=_run(GeographyEntityType.COMMUNITY, status))

    assert _has_failed_run(summary) is False


def test_has_failed_run_is_true_when_any_entity_type_failed() -> None:
    summary = _summary(
        regions=_run(GeographyEntityType.REGION, GeographySyncStatus.FAILED)
    )

    assert _has_failed_run(summary) is True
