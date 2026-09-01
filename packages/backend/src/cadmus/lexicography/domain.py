"""Lexicography domain objects and invariants (BH-54: manual lexeme selection)."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
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


class LexemeStatus(StrEnum):
    """A lexeme's structural-decomposition progress (BH-113).

    ``DRAFT`` is the state ALTO/OCR (or a manual selection) leaves a lexeme
    in. ``READY_TO_PROCESS`` and ``READY_TO_REVIEW`` mark it as being (or
    having finished) further broken down into smaller structural data.
    ``COMPLETE`` is the only status set exclusively by an explicit user
    action, never automatically, and is the sole status that locks the
    lexeme against further edits (BH-107/BH-113: a lexeme stays editable in
    every other status).
    """

    DRAFT = "draft"
    READY_TO_PROCESS = "ready_to_process"
    READY_TO_REVIEW = "ready_to_review"
    COMPLETE = "complete"


class LexemeNotEditableError(ValueError):
    """BH-113: raised when editing/deleting a lexeme whose status is COMPLETE."""

    def __init__(self, dictionary_id: UUID, lexeme_id: UUID) -> None:
        super().__init__(f"lexeme {lexeme_id} is complete and can no longer be edited")
        self.dictionary_id = dictionary_id
        self.lexeme_id = lexeme_id


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
    status: LexemeStatus = LexemeStatus.DRAFT
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
    status: LexemeStatus | None = None,
) -> list[str]:
    """List which editable fields actually differ, for the BH-56 audit trail.

    ``status`` is ``None`` when the caller isn't requesting a status change
    at all (BH-113) -- distinct from any real ``LexemeStatus`` value, which
    ``Lexeme.status`` always has.
    """
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
    changed = [
        field for field in _EDITABLE_FIELDS if getattr(before, field) != after[field]
    ]
    if status is not None and status != before.status:
        changed.append("status")
    return changed


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


@dataclass(frozen=True)
class ArticleSchemaGenerationSnapshot:
    """Current observable state of a background schema-generation task.

    Unlike ``OcrSuggestionTaskSnapshot``, this never carries the generated
    schema itself -- the worker task persists it directly as a new
    ``ArticleSchema`` version (status ``READY``/``FAILED``) as soon as the
    AI provider call returns, mirroring ``DictionaryScanSnapshot``.
    """

    task_id: str
    status: OcrSuggestionStatus
    schema_id: UUID | None = None
    error: str | None = None


@dataclass(frozen=True)
class EntryExtractionSnapshot:
    """Current observable state of a background entry field-extraction task.

    Like ``DictionaryScanSnapshot``, this never carries the extracted
    fields themselves -- the worker task persists each one directly as an
    ``EntryField`` row (``origin=EntryFieldOrigin.MODEL``) as it goes.
    """

    task_id: str
    status: OcrSuggestionStatus
    created_fields: int = 0
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


class SchemaGenerationStatus(StrEnum):
    """Lifecycle of one AI-generated article schema version (BH-148)."""

    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


class EntryStatus(StrEnum):
    """A dictionary entry's structural-extraction progress (BH-148).

    Mirrors ``LexemeStatus``: ``DRAFT`` is the state extraction leaves an
    entry in, ``READY_TO_REVIEW`` marks it as awaiting editor review, and
    ``COMPLETE`` is set only by an explicit user action after the entry
    passes ``validate_entry_against_schema``.
    """

    DRAFT = "draft"
    READY_TO_REVIEW = "ready_to_review"
    COMPLETE = "complete"


class EntryFieldRole(StrEnum):
    """Semantic role of one structured field extracted from an article."""

    HEADWORD = "headword"
    PART_OF_SPEECH = "part_of_speech"
    MEANING = "meaning"
    EXAMPLE = "example"
    SYNONYM = "synonym"
    ABBREVIATION = "abbreviation"
    GEOGRAPHIC_LABEL = "geographic_label"
    OTHER = "other"


class EntryFieldOrigin(StrEnum):
    """How an entry field's value came to exist (ADR-0004 provenance model).

    ``MODEL`` is AI-extracted per the dictionary's active ``ArticleSchema``
    (a proposal, per AGENTS.md, until an editor reviews it). ``RULE`` is a
    deterministic match against the dictionary's own abbreviation/settlement
    reference data (BH-29/BH-30), not an AI call. ``MANUAL`` is a field an
    editor typed or edited by hand -- editing any field flips its origin to
    ``MANUAL`` and stamps the editor as ``updated_by``.
    """

    MODEL = "model"
    RULE = "rule"
    MANUAL = "manual"


class ArticleSchemaValidationError(ValueError):
    """Field-addressable BH-148 article schema validation errors."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("article schema is invalid")
        self.errors = dict(errors)


class ArticleSchemaAccessError(LookupError):
    """Raised for a missing article schema or one outside the given dictionary."""

    def __init__(self, schema_id: UUID) -> None:
        super().__init__(f"article schema {schema_id} is not accessible")
        self.schema_id = schema_id


class EntryValidationError(ValueError):
    """Field-addressable BH-148 dictionary entry validation errors."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("entry is invalid")
        self.errors = dict(errors)


class EntryAccessError(LookupError):
    """Raised for a missing entry or one outside the given dictionary."""

    def __init__(self, entry_id: UUID) -> None:
        super().__init__(f"entry {entry_id} is not accessible")
        self.entry_id = entry_id


class DuplicateEntryError(ValueError):
    """Raised when a lexeme has already been promoted to an entry."""

    def __init__(self, existing_id: UUID, lexeme_id: UUID) -> None:
        super().__init__("this lexeme has already been promoted to an entry")
        self.existing_id = existing_id
        self.lexeme_id = lexeme_id


class EntryFieldValidationError(ValueError):
    """Field-addressable BH-148 entry field validation errors."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("entry field is invalid")
        self.errors = dict(errors)


class EntryFieldAccessError(LookupError):
    """Raised for a missing entry field or one outside the given entry."""

    def __init__(self, field_id: UUID) -> None:
        super().__init__(f"entry field {field_id} is not accessible")
        self.field_id = field_id


@dataclass
class ArticleSchema:
    """One AI-generated (or manually edited) version of a dictionary's
    article structure (BH-148).

    ``definition`` is a JSON field tree stored as
    ``{"fields": [{"name", "role", "type", "repeatable", "required",
    "children"}, ...]}``, recursively nested via each node's ``"children"``
    to support repeating and nested elements (e.g. several ``meaning``
    nodes, each with its own ``example``/``synonym`` children). Only one
    version per dictionary is ever ``activated_at``-set at a time; older
    versions remain as history.
    """

    id: UUID
    dictionary_id: UUID
    version: int
    status: SchemaGenerationStatus
    source_description: str
    definition: dict[str, Any]
    created_at: datetime
    created_by: UUID
    raw_provider_response: dict[str, Any] | None = None
    provider_name: str | None = None
    error_message: str | None = None
    activated_at: datetime | None = None
    activated_by: UUID | None = None


@dataclass
class DictionaryEntry:
    """The semantic dictionary article (ADR-0006), promoted from a
    ``COMPLETE`` ``Lexeme`` (BH-148).

    ``lexeme_id`` is a unique reference to its one source lexeme -- a
    lexeme may be promoted at most once (``DuplicateEntryError``).
    ``schema_id`` records which ``ArticleSchema`` version, if any, was
    active when this entry's fields were last extracted.
    """

    id: UUID
    dictionary_id: UUID
    lexeme_id: UUID
    headword: str
    status: EntryStatus
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
    schema_id: UUID | None = None


@dataclass
class EntryFragment:
    """The physical location of one part of an entry on one page (ADR-0006).

    An entry may have several fragments across pages, for an article split
    by a page break; box fields mirror ``Lexeme``'s convention (pixel
    coordinates, top-left origin, optional second box). ``recognized_text``
    is the immutable source text this fragment's fields are spans over --
    it is never mutated or trimmed, so any text a field doesn't cover
    remains visible to a reviewer by construction.
    """

    id: UUID
    entry_id: UUID
    page_id: UUID
    x: float
    y: float
    width: float
    height: float
    reading_order: int
    recognized_text: str
    x2: float | None = None
    y2: float | None = None
    width2: float | None = None
    height2: float | None = None


@dataclass
class EntryField:
    """One structured field extracted (or manually added) from an entry
    fragment (BH-148), with full ADR-0004 provenance.

    Two, independently optional kinds of source span: ``source_start``/
    ``source_end`` are character offsets into the fragment's
    ``recognized_text`` (set by the manual-add flow, which lets an editor
    type/select text directly); ``x``/``y``/``width``/``height`` are a real
    page-pixel bounding box (set by ALTO segment-based extraction --
    BH-148 experimental variant 1 -- as the union of the OCR segments the
    field was extracted from). A field may have either, both, or neither.
    ``parent_field_id`` lets fields nest (e.g. an ``example`` under a
    ``meaning``) and repeat (several fields sharing the same
    ``parent_field_id`` and role, ordered by ``position``). ``field_path``
    is a human-readable locator into the owning ``ArticleSchema.definition``
    tree (e.g. ``"senses[0].examples[1]"``).
    """

    id: UUID
    entry_id: UUID
    fragment_id: UUID
    field_path: str
    role: EntryFieldRole
    position: int
    source_text: str
    origin: EntryFieldOrigin
    created_at: datetime
    created_by: UUID
    updated_at: datetime
    updated_by: UUID
    parent_field_id: UUID | None = None
    normalized_text: str | None = None
    confidence: float | None = None
    processing_run_id: UUID | None = None
    source_start: int | None = None
    source_end: int | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None


@dataclass(frozen=True)
class GeneratedSchema:
    """One AI provider's proposed article field tree, not yet an ``ArticleSchema``.

    Ephemeral by design: never persisted directly -- the application layer
    wraps it into a new ``ArticleSchema`` version.
    """

    definition: dict[str, Any]
    raw_response: dict[str, Any]
    provider_name: str


@dataclass(frozen=True)
class FragmentSegment:
    """One OCR-recognized word within a fragment's region (BH-148 ALTO
    segmentation, experimental), positioned in the same page-pixel
    coordinate space as ``EntryFragment``/``Lexeme`` boxes.

    ``index`` is this segment's position in the ordered list handed to
    ``AiSchemaProvider.extract_fields`` -- the AI references a contiguous
    range of these instead of guessing character offsets into a flat
    string, which gives each extracted field a real bounding box instead
    of just a text span.
    """

    index: int
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float


@dataclass(frozen=True)
class ExtractedField:
    """One AI provider's proposed structured field, not yet an ``EntryField``.

    Ephemeral by design: never persisted directly -- the application layer
    wraps it into a new ``EntryField`` row (``origin=EntryFieldOrigin.MODEL``).

    ``segment_start``/``segment_end`` are an inclusive index range into the
    ``FragmentSegment`` list the provider was given -- the field's text and
    bounding box are derived by the caller from the segments they cover.
    """

    field_path: str
    role: EntryFieldRole
    value: str
    segment_start: int
    segment_end: int
    confidence: float


def _walk_schema_nodes(nodes: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flatten a schema definition tree (depth-first) for validation."""
    flattened: list[dict[str, Any]] = []
    for node in nodes:
        flattened.append(node)
        children: Sequence[dict[str, Any]] = node.get("children") or []
        flattened.extend(_walk_schema_nodes(children))
    return flattened


_BOOLEAN_LITERALS = {"так", "ні", "true", "false", "1", "0", "yes", "no"}


def _field_path_leaf(field_path: str) -> str:
    """Last segment of a ``field_path`` with any ``[index]`` suffixes removed
    (``"senses[0].examples[1]"`` -> ``"examples"``)."""
    last = field_path.split(".")[-1]
    bracket = last.find("[")
    return last[:bracket] if bracket != -1 else last


def resolve_schema_node(
    definition: dict[str, Any], field_path: str
) -> dict[str, Any] | None:
    """Find the schema node an ``EntryField.field_path`` points at, matched by
    the node ``name`` of the path's leaf segment. Returns ``None`` when the
    path has no counterpart in the schema (e.g. a hand-typed custom path)."""
    leaf = _field_path_leaf(field_path)
    if not leaf:
        return None
    for node in _walk_schema_nodes(definition.get("fields", [])):
        if node.get("name") == leaf:
            return node
    return None


def validate_field_value(node: dict[str, Any], value: str) -> str | None:
    """Check one entry field's text against the typed constraints of its
    schema ``node``. Returns an error message, or ``None`` when the value fits
    (or the node's type carries no value constraint)."""
    node_type = node.get("type")
    text = value.strip()
    if not text:
        return None
    if node_type == "enum":
        options = node.get("options") or []
        if text not in options:
            return f"«{value}» не входить до списку допустимих значень."
        return None
    if node_type == "number":
        try:
            Decimal(text)
        except (InvalidOperation, ValueError):
            return "Значення має бути числом."
        return None
    if node_type == "boolean":
        if text.casefold() not in _BOOLEAN_LITERALS:
            return "Значення має бути «так» або «ні»."  # noqa: RUF001
        return None
    if node_type == "date":
        try:
            date.fromisoformat(text)
        except ValueError:
            return "Значення має бути датою у форматі РРРР-ММ-ДД."  # noqa: RUF001
        return None
    return None


def validate_entry_against_schema(
    entry: DictionaryEntry,
    fields: Sequence[EntryField],
    schema: ArticleSchema,
) -> dict[str, str]:
    """Check every required, non-repeatable node in ``schema`` has at least
    one matching field, keyed by ``field_path`` (BH-148 AC: "each field has
    a type and provenance" / "the result passes canonical schema
    validation"). Returns an empty dict when the entry is valid.

    ``entry`` is accepted for symmetry with the rest of the module's
    validation helpers and for future entry-level checks; it plays no part
    in today's per-field check.
    """
    del entry
    errors: dict[str, str] = {}
    present_paths = {field.field_path for field in fields}
    for node in _walk_schema_nodes(schema.definition.get("fields", [])):
        if not node.get("required"):
            continue
        path = node.get("name")
        if not path:
            continue
        if node.get("repeatable"):
            has_match = any(
                candidate == path or candidate.startswith(f"{path}[")
                for candidate in present_paths
            )
        else:
            has_match = path in present_paths
        if not has_match:
            errors[str(path)] = f"Обов'язкове поле «{path}» не заповнене."

    for field in fields:
        field_node = resolve_schema_node(schema.definition, field.field_path)
        if field_node is None:
            continue
        value = (
            field.normalized_text
            if field.normalized_text is not None
            else field.source_text
        )
        message = validate_field_value(field_node, value)
        if message is not None:
            errors[field.field_path] = message
    return errors


SCHEMA_FIELD_TYPES = (
    "string",
    "number",
    "boolean",
    "date",
    "enum",
    "list",
    "group",
)
SCHEMA_TYPES_WITH_OPTIONS = ("enum",)
"""Field types whose node carries an ``options`` list of allowed string values."""
MAX_SCHEMA_DEPTH = 3
"""A hand-edited schema mirrors the AI tool-schema's three levels (top field ->
mid child -> leaf grandchild); see ``infrastructure/ai_schema.py``."""


def _validate_schema_node(
    node: Any, path: str, depth: int, errors: dict[str, str]
) -> None:
    if not isinstance(node, dict):
        errors[path] = "Поле схеми має бути об'єктом."  # noqa: RUF001
        return
    name = node.get("name")
    if not isinstance(name, str) or not name.strip():
        errors[f"{path}.name"] = "Вкажіть назву поля."
    if node.get("role") not in {role.value for role in EntryFieldRole}:
        errors[f"{path}.role"] = "Оберіть коректну роль поля."
    node_type = node.get("type")
    if node_type not in SCHEMA_FIELD_TYPES:
        message = "Оберіть коректний тип поля."
        errors[f"{path}.type"] = message
    if node_type in SCHEMA_TYPES_WITH_OPTIONS:
        options = node.get("options")
        cleaned = (
            [item.strip() for item in options if isinstance(item, str)]
            if isinstance(options, list)
            else []
        )
        cleaned = [item for item in cleaned if item]
        if not isinstance(options, list) or not cleaned:
            errors[f"{path}.options"] = "Додайте щонайменше одне значення переліку."
        elif len(set(cleaned)) != len(cleaned):
            errors[f"{path}.options"] = "Значення переліку не мають повторюватися."
    for flag in ("repeatable", "required"):
        if flag in node and not isinstance(node[flag], bool):
            errors[f"{path}.{flag}"] = "Значення має бути булевим (так / ні)."
    children = node.get("children")
    if children in (None, [], ()):
        return
    if depth >= MAX_SCHEMA_DEPTH:
        errors[f"{path}.children"] = (
            f"Схема підтримує щонайбільше {MAX_SCHEMA_DEPTH} рівні вкладеності."
        )
        return
    _validate_schema_nodes(children, f"{path}.children", depth + 1, errors)


def _validate_schema_nodes(
    nodes: Any, path: str, depth: int, errors: dict[str, str]
) -> None:
    if not isinstance(nodes, list):
        errors[path] = "Список полів має бути масивом."
        return
    seen: set[str] = set()
    for index, node in enumerate(nodes):
        node_path = f"{path}[{index}]"
        _validate_schema_node(node, node_path, depth, errors)
        name = node.get("name") if isinstance(node, dict) else None
        if isinstance(name, str) and name.strip():
            if name.strip() in seen:
                errors[f"{node_path}.name"] = (
                    f"Назва «{name.strip()}» повторюється на цьому рівні."
                )
            seen.add(name.strip())


def validate_schema_definition(definition: Any) -> dict[str, str]:
    """Structural validation for a hand-edited BH-148 article-schema
    ``definition`` (``{"fields": [Node, ...]}``, Node = ``{name, role, type,
    repeatable, required, children}``). Errors are keyed by a path such as
    ``fields[0].children[1].role``; an empty dict means the schema is valid.
    """
    if not isinstance(definition, dict):
        message = "Схема має бути об'єктом з полем «fields»."  # noqa: RUF001
        return {"definition": message}
    fields = definition.get("fields")
    if not isinstance(fields, list) or not fields:
        return {"fields": "Додайте щонайменше одне поле."}
    errors: dict[str, str] = {}
    _validate_schema_nodes(fields, "fields", 1, errors)
    return errors


def normalize_schema_definition(definition: dict[str, Any]) -> dict[str, Any]:
    """Fill defaults so a hand-edited tree is stored like a generated one:
    every node carries ``name/role/type/repeatable/required/children``, with
    ``children`` recursively normalized and dropped past ``MAX_SCHEMA_DEPTH``.
    Assumes ``definition`` already passed ``validate_schema_definition``.
    """

    def _node(raw: dict[str, Any], depth: int) -> dict[str, Any]:
        children = raw.get("children") or []
        nested = (
            [_node(child, depth + 1) for child in children]
            if depth < MAX_SCHEMA_DEPTH and isinstance(children, list)
            else []
        )
        options: list[str] = []
        if raw["type"] in SCHEMA_TYPES_WITH_OPTIONS:
            options = [
                str(item).strip()
                for item in raw.get("options") or []
                if str(item).strip()
            ]
        return {
            "name": str(raw.get("name", "")).strip(),
            "role": raw["role"],
            "type": raw["type"],
            "options": options,
            "repeatable": bool(raw.get("repeatable", False)),
            "required": bool(raw.get("required", False)),
            "children": nested,
        }

    return {"fields": [_node(node, 1) for node in definition.get("fields") or []]}
