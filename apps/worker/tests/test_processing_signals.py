"""The Celery signal handlers that keep the processing-task registry current."""

from dataclasses import dataclass, field
from typing import Any

import pytest
from cadmus_worker import celery_app as celery_module


@dataclass
class FakeRecorder:
    running: list[str] = field(default_factory=list)
    succeeded: list[tuple[str, dict[str, Any] | None]] = field(default_factory=list)
    failed: list[tuple[str, str | None]] = field(default_factory=list)
    explode: bool = False

    def mark_running(self, celery_task_id: str) -> None:
        if self.explode:
            raise RuntimeError("registry unavailable")
        self.running.append(celery_task_id)

    def mark_succeeded(
        self, celery_task_id: str, result: dict[str, Any] | None = None
    ) -> None:
        if self.explode:
            raise RuntimeError("registry unavailable")
        self.succeeded.append((celery_task_id, result))

    def mark_failed(self, celery_task_id: str, error: str | None) -> None:
        if self.explode:
            raise RuntimeError("registry unavailable")
        self.failed.append((celery_task_id, error))


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> FakeRecorder:
    fake = FakeRecorder()
    monkeypatch.setattr(celery_module, "_status_recorder", lambda: fake)
    return fake


def test_prerun_marks_running(recorder: FakeRecorder) -> None:
    celery_module._record_task_started(task_id="celery-1")
    assert recorder.running == ["celery-1"]


def test_postrun_success_records_the_result_dict(recorder: FakeRecorder) -> None:
    celery_module._record_task_finished(
        task_id="celery-1", retval={"created_lexemes": 3}, state="SUCCESS"
    )
    assert recorder.succeeded == [("celery-1", {"created_lexemes": 3})]


def test_postrun_treats_an_app_level_failure_dict_as_failed(
    recorder: FakeRecorder,
) -> None:
    celery_module._record_task_finished(
        task_id="celery-1",
        retval={"status": "failed", "error": "dictionary not found"},
        state="SUCCESS",
    )
    assert recorder.failed == [("celery-1", "dictionary not found")]
    assert recorder.succeeded == []


def test_postrun_ignores_non_success_states(recorder: FakeRecorder) -> None:
    celery_module._record_task_finished(
        task_id="celery-1", retval=None, state="FAILURE"
    )
    assert recorder.succeeded == []
    assert recorder.failed == []


def test_failure_signal_records_the_exception(recorder: FakeRecorder) -> None:
    celery_module._record_task_failed(
        task_id="celery-1", exception=ValueError("bad input")
    )
    assert recorder.failed == [("celery-1", "ValueError: bad input")]


def test_revoked_signal_records_a_cancellation(recorder: FakeRecorder) -> None:
    class Request:
        id = "celery-9"

    celery_module._record_task_revoked(request=Request())
    assert recorder.failed and recorder.failed[0][0] == "celery-9"


def test_handlers_swallow_registry_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        celery_module, "_status_recorder", lambda: FakeRecorder(explode=True)
    )
    # None of these may raise -- monitoring must never disturb the task.
    celery_module._record_task_started(task_id="celery-1")
    celery_module._record_task_finished(task_id="celery-1", retval={}, state="SUCCESS")
    celery_module._record_task_failed(task_id="celery-1", exception=RuntimeError("x"))


def test_handlers_are_noops_without_a_task_id(recorder: FakeRecorder) -> None:
    celery_module._record_task_started(task_id=None)
    celery_module._record_task_finished(task_id=None, retval={}, state="SUCCESS")
    celery_module._record_task_failed(task_id=None)
    celery_module._record_task_revoked(request=None)
    assert recorder.running == []
    assert recorder.succeeded == []
    assert recorder.failed == []
