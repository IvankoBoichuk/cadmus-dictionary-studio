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

    Only ``MANUAL`` exists yet: BH-54 lexemes are drawn by hand before OCR
    runs. ``ocr``/``rule``/``model`` are reserved for later Stories that
    derive lexemes from automated recognition, per the provenance model.
    """

    MANUAL = "manual"


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


@dataclass
class Lexeme:
    """One manually selected word/fragment on a dictionary page (BH-54).

    A future precursor to a ``headword``/entry; ``x``/``y``/``width``/
    ``height`` are pixel coordinates relative to the page's rendered image
    (top-left origin), matching ``DictionaryPage.width``/``height``.
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
