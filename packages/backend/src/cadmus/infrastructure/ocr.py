"""Tesseract/ALTO OCR word-suggestion infrastructure.

Worker-only boundary: parses Tesseract's native ALTO XML output into
``LexemeSuggestion`` values and hands suggestion jobs to Celery. Domain and
application code never import this module directly (see
``packages/backend/AGENTS.md``: "Domain code must not import ... OCR
SDKs").
"""

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final
from uuid import UUID
from xml.etree import ElementTree

from celery import Celery, states
from kombu.exceptions import OperationalError
from redis.exceptions import RedisError

from cadmus.lexicography.domain import DictionaryScanSnapshot as _ScanSnapshot
from cadmus.lexicography.domain import (
    LexemeSuggestion,
    OcrSuggestionStatus,
)
from cadmus.lexicography.domain import OcrSuggestionTaskSnapshot as _Snapshot
from cadmus.lexicography.ports import (
    SCAN_DICTIONARY_TASK_NAME,
    SUGGEST_LEXEMES_TASK_NAME,
    DictionaryScanQueueUnavailableError,
    OcrSuggestionQueueUnavailableError,
)

_QUEUE_ERRORS: Final = (OperationalError, RedisError, OSError)


class OcrExecutionError(RuntimeError):
    """Raised when the Tesseract subprocess fails, times out, or its output
    cannot be parsed."""


def parse_alto_entries(xml_bytes: bytes) -> list[LexemeSuggestion]:
    """Parse Tesseract's ALTO XML into pixel-coordinate dictionary-entry suggestions.

    Groups words by ALTO's ``TextBlock`` element rather than suggesting
    every individual ``String`` word: a dictionary entry is typographically
    a paragraph (a bolded headword followed by its definition, separated
    from the next entry by a blank line), and Tesseract's own layout
    analysis already segments a page into blocks along those same
    paragraph breaks -- confirmed empirically against real scanned pages,
    where each ``TextBlock`` lines up with one dictionary entry. Matches
    elements by local name (stripping any ``{namespace}`` prefix) rather
    than a hardcoded ALTO namespace URI, since Tesseract's exact ALTO
    schema version varies by build. ALTO's ``HPOS``/``VPOS``/``WIDTH``/
    ``HEIGHT`` are already pixel-based against the source image, matching
    ``Lexeme``'s coordinate convention -- no unit conversion.
    """
    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError as error:
        raise OcrExecutionError(f"could not parse ALTO output: {error}") from error

    suggestions: list[LexemeSuggestion] = []
    for block in root.iter():
        if _local_name(block.tag) != "TextBlock":
            continue
        try:
            x = float(block.get("HPOS", ""))
            y = float(block.get("VPOS", ""))
            width = float(block.get("WIDTH", ""))
            height = float(block.get("HEIGHT", ""))
        except ValueError:
            continue
        if width <= 0 or height <= 0:
            continue

        words: list[str] = []
        confidences: list[float] = []
        for line in block:
            if _local_name(line.tag) != "TextLine":
                continue
            for string in line:
                if _local_name(string.tag) != "String":
                    continue
                content = string.get("CONTENT", "").strip()
                if not content:
                    continue
                words.append(content)
                confidences.append(_parse_confidence(string.get("WC")))
        if not words:
            continue

        suggestions.append(
            LexemeSuggestion(
                source_text=" ".join(words),
                x=x,
                y=y,
                width=width,
                height=height,
                confidence=sum(confidences) / len(confidences),
            )
        )
    return suggestions


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_confidence(raw: str | None) -> float:
    if raw is None:
        return 1.0
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return max(0.0, min(1.0, value))


class TesseractAltoOcrProvider:
    """Runs the ``tesseract`` CLI in ALTO output mode on one page image."""

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    def suggest_words(
        self, image_bytes: bytes, language: str
    ) -> list[LexemeSuggestion]:
        with TemporaryDirectory(prefix="cadmus-ocr-") as tmp_dir:
            image_path = Path(tmp_dir) / "page.png"
            output_base = Path(tmp_dir) / "output"
            image_path.write_bytes(image_bytes)
            try:
                subprocess.run(
                    [
                        "tesseract",
                        str(image_path),
                        str(output_base),
                        "-l",
                        language,
                        "alto",
                    ],
                    timeout=self._timeout_seconds,
                    capture_output=True,
                    check=True,
                )
            except subprocess.TimeoutExpired as error:
                raise OcrExecutionError("tesseract timed out") from error
            except subprocess.CalledProcessError as error:
                stderr = error.stderr.decode("utf-8", errors="replace")
                raise OcrExecutionError(
                    f"tesseract failed: {stderr.strip()}"
                ) from error
            except FileNotFoundError as error:
                raise OcrExecutionError("tesseract is not installed") from error

            xml_path = output_base.with_suffix(".xml")
            try:
                xml_bytes = xml_path.read_bytes()
            except FileNotFoundError as error:
                raise OcrExecutionError(
                    "tesseract did not produce ALTO output"
                ) from error
            return parse_alto_entries(xml_bytes)


class CeleryOcrSuggestionQueue:
    """Hand OCR suggestion jobs to the worker through Celery.

    Mirrors ``CeleryTaskQueue`` (``task_queue.py``): the suggestion result
    lives in Celery's own Redis result backend, never in Postgres --
    suggestions are ephemeral candidates, not source evidence.
    """

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def enqueue_suggestions(
        self, source_file_id: UUID, page_id: UUID, language: str
    ) -> str:
        try:
            result = self._celery_app.send_task(
                SUGGEST_LEXEMES_TASK_NAME,
                args=[str(source_file_id), str(page_id), language],
                retry=False,
            )
        except _QUEUE_ERRORS as error:
            raise OcrSuggestionQueueUnavailableError(
                "OCR suggestion queue is unavailable"
            ) from error
        return str(result.id)

    def get_suggestions_task(self, task_id: str) -> _Snapshot:
        try:
            result = self._celery_app.AsyncResult(task_id)
            state = result.state
            value = result.result if state == states.SUCCESS else None
        except _QUEUE_ERRORS as error:
            raise OcrSuggestionQueueUnavailableError(
                "OCR suggestion queue is unavailable"
            ) from error

        if state == states.SUCCESS:
            payload = value if isinstance(value, dict) else {}
            if payload.get("status") == "failed":
                return _Snapshot(
                    task_id=task_id,
                    status=OcrSuggestionStatus.FAILED,
                    error=str(payload.get("error", "OCR suggestion task failed")),
                )
            raw_suggestions = payload.get("suggestions", [])
            suggestions = tuple(
                LexemeSuggestion(
                    source_text=item["source_text"],
                    x=item["x"],
                    y=item["y"],
                    width=item["width"],
                    height=item["height"],
                    confidence=item["confidence"],
                )
                for item in raw_suggestions
                if isinstance(item, dict)
            )
            return _Snapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.SUCCEEDED,
                suggestions=suggestions,
            )
        if state in {states.FAILURE, states.REVOKED}:
            return _Snapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.FAILED,
                error="OCR suggestion task failed",
            )
        if state in {states.STARTED, states.RETRY}:
            return _Snapshot(task_id=task_id, status=OcrSuggestionStatus.RUNNING)
        return _Snapshot(task_id=task_id, status=OcrSuggestionStatus.QUEUED)


_PROGRESS_STATE = "PROGRESS"


class CeleryDictionaryScanQueue:
    """Hand a whole-dictionary OCR scan job to the worker through Celery.

    Progress is read back from Celery's own custom task state (the worker
    calls ``task.update_state(state="PROGRESS", meta=...)`` as it walks
    pages) -- no separate Postgres table for job progress.
    """

    def __init__(self, celery_app: Celery) -> None:
        self._celery_app = celery_app

    def enqueue_scan(self, dictionary_id: UUID, actor_id: UUID) -> str:
        try:
            result = self._celery_app.send_task(
                SCAN_DICTIONARY_TASK_NAME,
                args=[str(dictionary_id), str(actor_id)],
                retry=False,
            )
        except _QUEUE_ERRORS as error:
            raise DictionaryScanQueueUnavailableError(
                "dictionary scan queue is unavailable"
            ) from error
        return str(result.id)

    def get_scan_task(self, task_id: str) -> _ScanSnapshot:
        try:
            result = self._celery_app.AsyncResult(task_id)
            state = result.state
            info = result.info if state in {_PROGRESS_STATE, states.SUCCESS} else None
        except _QUEUE_ERRORS as error:
            raise DictionaryScanQueueUnavailableError(
                "dictionary scan queue is unavailable"
            ) from error

        if state == states.SUCCESS:
            payload = info if isinstance(info, dict) else {}
            if payload.get("status") == "failed":
                return _ScanSnapshot(
                    task_id=task_id,
                    status=OcrSuggestionStatus.FAILED,
                    error=str(payload.get("error", "dictionary scan task failed")),
                )
            return _ScanSnapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.SUCCEEDED,
                processed_pages=int(payload.get("processed_pages", 0)),
                total_pages=int(payload.get("total_pages", 0)),
                created_lexemes=int(payload.get("created_lexemes", 0)),
            )
        if state == _PROGRESS_STATE:
            payload = info if isinstance(info, dict) else {}
            return _ScanSnapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.RUNNING,
                processed_pages=int(payload.get("processed_pages", 0)),
                total_pages=int(payload.get("total_pages", 0)),
                created_lexemes=int(payload.get("created_lexemes", 0)),
            )
        if state in {states.FAILURE, states.REVOKED}:
            return _ScanSnapshot(
                task_id=task_id,
                status=OcrSuggestionStatus.FAILED,
                error="dictionary scan task failed",
            )
        if state in {states.STARTED, states.RETRY}:
            return _ScanSnapshot(task_id=task_id, status=OcrSuggestionStatus.RUNNING)
        return _ScanSnapshot(task_id=task_id, status=OcrSuggestionStatus.QUEUED)
