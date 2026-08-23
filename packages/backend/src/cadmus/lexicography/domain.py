"""Lexicography domain objects and invariants (BH-54: manual lexeme selection)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

MAX_SOURCE_TEXT_LENGTH = 500

DUPLICATE_OVERLAP_RATIO = 0.6
"""Share of the smaller box's area that must overlap to flag a re-selection.

Adjacent words on a printed page sit close together, so any pixel overlap
would false-positive constantly; a majority-area overlap is a much closer
proxy for "the user boxed essentially the same word again" (BH-54 AC6).
"""


class LexemeOrigin(StrEnum):
    """How a lexeme's text and bounding box came to exist (ADR-0004 §9).

    ``MANUAL`` is a lexeme drawn and typed entirely by hand (BH-54).
    ``OCR`` is a Tesseract/ALTO suggestion the user reviewed and accepted
    (see ``LexemeSuggestion``/``SuggestLexemesService``) -- the box and
    text both come from the recognizer, not from the user typing them.
    ``rule``/``model`` are reserved for later Stories, per the provenance
    model.
    """

    MANUAL = "manual"
    OCR = "ocr"


class LexemeValidationError(ValueError):
    """Field-addressable BH-54 lexeme validation errors (AC1, AC2, AC3)."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("lexeme is invalid")
        self.errors = dict(errors)


class LexemeAccessError(LookupError):
    """Raised for a missing dictionary or one the caller does not own.

    Intentionally indistinguishable from "not found", mirroring
    ``sources.DictionaryAccessError``.
    """

    def __init__(self, dictionary_id: UUID) -> None:
        super().__init__(f"dictionary {dictionary_id} is not accessible")
        self.dictionary_id = dictionary_id


class LexemePageNotFoundError(LookupError):
    """Raised when the requested page number isn't a viewable page (BH-53)."""

    def __init__(self, dictionary_id: UUID, page_number: int) -> None:
        super().__init__(f"page {page_number} of dictionary {dictionary_id} not found")
        self.dictionary_id = dictionary_id
        self.page_number = page_number


class DuplicateLexemeError(ValueError):
    """AC6: a new lexeme's box heavily overlaps an existing one on the page."""

    def __init__(self, existing_id: UUID) -> None:
        super().__init__("a lexeme with a heavily overlapping selection already exists")
        self.existing_id = existing_id


class LexemeNotFoundError(LookupError):
    """BH-56: raised for a lexeme that doesn't exist within the dictionary."""

    def __init__(self, dictionary_id: UUID, lexeme_id: UUID) -> None:
        super().__init__(f"lexeme {lexeme_id} not found in dictionary {dictionary_id}")
        self.dictionary_id = dictionary_id
        self.lexeme_id = lexeme_id


class DictionaryNotReadyToScanError(ValueError):
    """BH-58: raised when finishing the scanning stage before any lexeme exists."""

    def __init__(self, dictionary_id: UUID) -> None:
        super().__init__(
            f"dictionary {dictionary_id} has no lexemes yet; scanning isn't finished"
        )
        self.dictionary_id = dictionary_id


class LexemeEventType(StrEnum):
    """BH-56 AC: append-only history of who changed a lexeme, and when."""

    UPDATED = "updated"
    DELETED = "deleted"


@dataclass
class Lexeme:
    """One manually selected word/fragment on a dictionary page (BH-54).

    A future precursor to a ``headword``/entry; ``x``/``y``/``width``/
    ``height`` are pixel coordinates relative to the page's rendered image
    (top-left origin), matching ``DictionaryPage.width``/``height``.

    ``x2``/``y2``/``width2``/``height2`` are an optional second box on the
    *same* page, for an entry that visually splits across a column break
    (the tail of a definition continuing in the next column). Either all
    four are set, or all four are ``None`` -- enforced by
    ``validate_second_box_fields`` and the ``lexeme_second_box_all_or_none``
    check constraint.
    """

    id: UUID
    dictionary_id: UUID
    page_id: UUID
    source_text: str
    x: float
    y: float
    width: float
    height: float
    origin: LexemeOrigin
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    updated_by: UUID
    x2: float | None = None
    y2: float | None = None
    width2: float | None = None
    height2: float | None = None


@dataclass
class LexemeEvent:
    """One append-only BH-56 audit entry for an edited or deleted lexeme.

    ``lexeme_id`` is deliberately not a live foreign key to ``lexemes``: a
    deletion event must outlive the row it describes (ADR-0004 §10: "audit
    trail is append-oriented"), mirroring ``sources.DictionaryEvent``.
    """

    id: UUID
    lexeme_id: UUID
    dictionary_id: UUID
    event_type: LexemeEventType
    actor_user_id: UUID
    occurred_at: datetime
    changed_fields: tuple[str, ...] = ()


_EDITABLE_FIELDS: tuple[str, ...] = (
    "source_text",
    "x",
    "y",
    "width",
    "height",
    "x2",
    "y2",
    "width2",
    "height2",
)


def changed_lexeme_fields(
    before: Lexeme,
    *,
    source_text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    x2: float | None = None,
    y2: float | None = None,
    width2: float | None = None,
    height2: float | None = None,
) -> list[str]:
    """List which editable fields actually differ, for the BH-56 audit trail."""
    after = {
        "source_text": source_text,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "x2": x2,
        "y2": y2,
        "width2": width2,
        "height2": height2,
    }
    return [
        field for field in _EDITABLE_FIELDS if getattr(before, field) != after[field]
    ]


def validate_lexeme_fields(
    *,
    source_text: str,
    x: float,
    y: float,
    width: float,
    height: float,
    page_width: int,
    page_height: int,
) -> dict[str, str]:
    """Validate a lexeme's text and bounding box against its page (AC1, AC2, AC3)."""
    errors: dict[str, str] = {}

    if not source_text or not source_text.strip():
        errors["source_text"] = "Вкажіть текст лексеми."
    elif len(source_text) > MAX_SOURCE_TEXT_LENGTH:
        errors["source_text"] = (
            "Текст лексеми занадто довгий "
            f"(максимум {MAX_SOURCE_TEXT_LENGTH} символів)."
        )

    if width <= 0 or height <= 0:
        errors["width"] = "Виділена область має мати додатні ширину та висоту."
    if x < 0 or y < 0:
        errors["x"] = "Виділена область не може виходити за межі сторінки."
    elif width > 0 and height > 0:
        exceeds_bounds = x + width > page_width or y + height > page_height
        if exceeds_bounds:
            errors["width"] = "Виділена область виходить за межі зображення сторінки."

    return errors


def validate_second_box_fields(
    *,
    x2: float | None,
    y2: float | None,
    width2: float | None,
    height2: float | None,
    page_width: int,
    page_height: int,
) -> dict[str, str]:
    """Validate an optional second box: an entry split across a column break.

    All four fields must be provided together, or all omitted -- there is
    no separate text for the second box, it's the same lexeme continuing
    elsewhere on the same page.
    """
    values = (x2, y2, width2, height2)
    if all(value is None for value in values):
        return {}
    if any(value is None for value in values):
        return {
            "x2": (
                "Другу область потрібно вказати повністю, усіма чотирма "
                "полями, або не вказувати зовсім."  # noqa: RUF001
            )
        }

    assert x2 is not None
    assert y2 is not None
    assert width2 is not None
    assert height2 is not None

    errors: dict[str, str] = {}
    if width2 <= 0 or height2 <= 0:
        errors["width2"] = "Друга область має мати додатні ширину та висоту."
    if x2 < 0 or y2 < 0:
        errors["x2"] = "Друга область не може виходити за межі сторінки."
    elif width2 > 0 and height2 > 0:
        exceeds_bounds = x2 + width2 > page_width or y2 + height2 > page_height
        if exceeds_bounds:
            errors["width2"] = "Друга область виходить за межі зображення сторінки."

    return errors


def _overlap_ratio(
    a_x: float,
    a_y: float,
    a_w: float,
    a_h: float,
    b_x: float,
    b_y: float,
    b_w: float,
    b_h: float,
) -> float:
    left = max(a_x, b_x)
    top = max(a_y, b_y)
    right = min(a_x + a_w, b_x + b_w)
    bottom = min(a_y + a_h, b_y + b_h)
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    smaller_area = min(a_w * a_h, b_w * b_h)
    if smaller_area <= 0:
        return 0.0
    return intersection / smaller_area


def find_overlapping_lexeme(
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    existing: Sequence[Lexeme],
) -> Lexeme | None:
    """AC6: find an existing lexeme whose box the candidate mostly re-selects."""
    for lexeme in existing:
        ratio = _overlap_ratio(
            x, y, width, height, lexeme.x, lexeme.y, lexeme.width, lexeme.height
        )
        if ratio >= DUPLICATE_OVERLAP_RATIO:
            return lexeme
    return None


class OcrSuggestionStatus(StrEnum):
    """Transport-neutral state of an in-flight OCR word-suggestion task."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True)
class LexemeSuggestion:
    """One Tesseract/ALTO word candidate for a page, not yet a ``Lexeme``.

    Ephemeral by design: never persisted. ``x``/``y``/``width``/``height``
    are pixel coordinates matching ``DictionaryPage.width``/``height``,
    same convention as ``Lexeme`` -- ALTO's ``HPOS``/``VPOS``/``WIDTH``/
    ``HEIGHT`` are already pixel-based against the source image, so no
    unit conversion happens between OCR output and this type.
    """

    source_text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float


@dataclass(frozen=True)
class OcrSuggestionTaskSnapshot:
    """Current observable state of a background suggestion task."""

    task_id: str
    status: OcrSuggestionStatus
    suggestions: tuple[LexemeSuggestion, ...] | None = None
    error: str | None = None


@dataclass(frozen=True)
class DictionaryScanSnapshot:
    """Current observable state of a background whole-dictionary OCR scan.

    Unlike ``OcrSuggestionTaskSnapshot``, this never carries the
    suggestions themselves -- the scanning task persists each surviving
    suggestion directly as a draft ``Lexeme`` (``LexemeOrigin.OCR``) as it
    goes, so there is nothing left to accept.
    """

    task_id: str
    status: OcrSuggestionStatus
    processed_pages: int = 0
    total_pages: int = 0
    created_lexemes: int = 0
    error: str | None = None


_ISO_TO_TESSERACT_LANGUAGE: dict[str, str] = {
    "uk": "ukr",
    "ru": "rus",
    "pl": "pol",
    "en": "eng",
}
DEFAULT_TESSERACT_LANGUAGE = "ukr+eng"


def resolve_ocr_language(language_codes: Sequence[str]) -> str:
    """Map a dictionary's configured ISO 639-1 codes to a Tesseract ``-l`` value.

    Falls back to ``DEFAULT_TESSERACT_LANGUAGE`` when the dictionary has no
    configured languages, or none of them have an installed Tesseract
    language pack (see ``apps/api/Dockerfile`` for the installed set).
    """
    mapped = [
        _ISO_TO_TESSERACT_LANGUAGE[code]
        for code in language_codes
        if code in _ISO_TO_TESSERACT_LANGUAGE
    ]
    if not mapped:
        return DEFAULT_TESSERACT_LANGUAGE
    # Preserve first-seen order while de-duplicating (dict keys are
    # insertion-ordered), so ``["uk", "uk", "en"]`` -> ``"ukr+eng"``.
    return "+".join(dict.fromkeys(mapped))
