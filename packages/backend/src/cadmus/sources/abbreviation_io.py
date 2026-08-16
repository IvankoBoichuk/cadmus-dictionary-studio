"""BH-29 abbreviation bulk import (AC5, AC6) and export (AC9).

Documented import/export format, identical in shape for CSV and JSON so an
export can be re-imported unchanged:

* ``abbreviation``   -- required.
* ``full_form``      -- required unless ``unresolved`` is true.
* ``category``       -- required; one of ``part_of_speech``, ``grammar``,
  ``usage``, ``geography``, ``source``, ``other``.
* ``language_code``  -- optional ISO 639-1 code.
* ``variants``       -- optional; CSV cell uses ``;``-separated values, JSON
  uses an array of strings.
* ``note``           -- optional.
* ``unresolved``     -- optional, defaults to false; CSV uses ``true``/``false``.

CSV files require a header row matching the field names above. JSON files are
a top-level array of objects with the same fields.
"""

import csv
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from typing import Literal
from uuid import UUID, uuid4

from cadmus.sources.application import AbbreviationInput
from cadmus.sources.domain import (
    Abbreviation,
    AbbreviationCategory,
    AbbreviationVariant,
    DictionaryAccessError,
    abbreviation_duplicate_key,
    validate_abbreviation_fields,
)
from cadmus.sources.ports import SourcesUnitOfWorkFactory

CSV_FIELDS: tuple[str, ...] = (
    "abbreviation",
    "full_form",
    "category",
    "language_code",
    "variants",
    "note",
    "unresolved",
)

ImportFormat = Literal["csv", "json"]

_DUPLICATE_IN_FILE_ERROR = {"abbreviation": "Такий запис уже є в цьому файлі імпорту."}
_DUPLICATE_IN_DICTIONARY_ERROR = {
    "abbreviation": "Таке скорочення вже існує в словнику."
}


class UnparsableImportFileError(ValueError):
    """Raised when the uploaded bytes are not well-formed CSV or JSON."""


@dataclass(frozen=True)
class AbbreviationImportRowResult:
    """One previewed or committed import row (AC5)."""

    row_number: int
    input: AbbreviationInput | None
    errors: dict[str, str]
    duplicate_of: UUID | None = None


@dataclass(frozen=True)
class AbbreviationImportOutcome:
    """Result of a commit: what was actually persisted vs. skipped (AC6)."""

    imported: list[Abbreviation]
    skipped: list[AbbreviationImportRowResult]


def parse_abbreviations_import(
    raw: bytes, import_format: ImportFormat
) -> list[dict[str, object]]:
    """Parse raw bytes into loosely-typed row dicts.

    Only raises on genuinely unparsable input (bad encoding, malformed JSON,
    missing CSV header); per-row content problems are reported later as
    per-row validation errors, never as a fatal parse failure.
    """
    if import_format == "json":
        return _parse_json(raw)
    return _parse_csv(raw)


def _parse_json(raw: bytes) -> list[dict[str, object]]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UnparsableImportFileError(f"invalid JSON: {error}") from error
    if not isinstance(payload, list):
        raise UnparsableImportFileError("JSON import must be a top-level array")
    return [entry if isinstance(entry, dict) else {} for entry in payload]


def _parse_csv(raw: bytes) -> list[dict[str, object]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise UnparsableImportFileError(f"invalid CSV encoding: {error}") from error
    reader = csv.DictReader(StringIO(text))
    if reader.fieldnames is None:
        raise UnparsableImportFileError("CSV import requires a header row")

    rows: list[dict[str, object]] = []
    for row in reader:
        parsed: dict[str, object] = dict(row)
        variants_cell = parsed.get("variants")
        if isinstance(variants_cell, str):
            parsed["variants"] = [
                part.strip() for part in variants_cell.split(";") if part.strip()
            ]
        unresolved_cell = parsed.get("unresolved")
        if isinstance(unresolved_cell, str):
            parsed["unresolved"] = unresolved_cell.strip().lower() in {
                "true",
                "1",
                "yes",
            }
        rows.append(parsed)
    return rows


def _row_to_input(
    row: dict[str, object],
) -> tuple[AbbreviationInput | None, dict[str, str]]:
    """Type-check one raw row into an :class:`AbbreviationInput`, or errors."""
    abbreviation = row.get("abbreviation")
    if not isinstance(abbreviation, str) or not abbreviation.strip():
        return None, {"abbreviation": "Вкажіть скорочення."}

    category_raw = row.get("category")
    category: AbbreviationCategory | None = None
    if isinstance(category_raw, str) and category_raw.strip():
        try:
            category = AbbreviationCategory(category_raw.strip())
        except ValueError:
            category = None
    if category is None:
        return None, {"category": f"Невідома категорія: {category_raw!r}."}

    full_form = row.get("full_form")
    full_form = full_form if isinstance(full_form, str) and full_form.strip() else None

    language_code = row.get("language_code")
    language_code = (
        language_code
        if isinstance(language_code, str) and language_code.strip()
        else None
    )

    note = row.get("note")
    note = note if isinstance(note, str) and note.strip() else None

    unresolved = bool(row.get("unresolved", False))

    variants_raw = row.get("variants")
    if isinstance(variants_raw, list):
        variants = tuple(
            str(item).strip() for item in variants_raw if str(item).strip()
        )
    else:
        variants = ()

    field_errors = validate_abbreviation_fields(
        abbreviation=abbreviation,
        full_form=full_form,
        language_code=language_code,
        note=note,
        unresolved=unresolved,
        variants=variants,
    )
    if field_errors:
        return None, field_errors

    return (
        AbbreviationInput(
            abbreviation=abbreviation.strip(),
            category=category,
            full_form=full_form,
            language_code=language_code,
            note=note,
            unresolved=unresolved,
            variants=variants,
        ),
        {},
    )


def _build_variants(
    abbreviation_id: UUID, variant_texts: Sequence[str]
) -> list[AbbreviationVariant]:
    return [
        AbbreviationVariant(
            id=uuid4(),
            abbreviation_id=abbreviation_id,
            variant_text=text.strip(),
            position=position,
        )
        for position, text in enumerate(variant_texts)
    ]


class AbbreviationImportService:
    """Preview and commit BH-29 bulk abbreviation imports (AC5, AC6)."""

    def __init__(
        self,
        unit_of_work_factory: SourcesUnitOfWorkFactory,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    def preview(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        raw: bytes,
        import_format: ImportFormat,
    ) -> list[AbbreviationImportRowResult]:
        """Parse and validate a file without persisting anything (AC5)."""
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            if dictionary is None or dictionary.owner_id != actor_id:
                raise DictionaryAccessError(dictionary_id)

            raw_rows = parse_abbreviations_import(raw, import_format)
            results: list[AbbreviationImportRowResult] = []
            seen_keys: set[tuple[AbbreviationCategory, str | None, str]] = set()
            for index, raw_row in enumerate(raw_rows, start=1):
                data, errors = _row_to_input(raw_row)
                if data is None:
                    results.append(AbbreviationImportRowResult(index, None, errors))
                    continue

                key = abbreviation_duplicate_key(
                    data.category, data.language_code, data.abbreviation
                )
                duplicate_of: UUID | None = None
                if key in seen_keys:
                    errors = dict(_DUPLICATE_IN_FILE_ERROR)
                else:
                    existing = unit_of_work.sources.find_abbreviation_duplicate(
                        dictionary_id,
                        data.category,
                        data.language_code,
                        data.abbreviation,
                    )
                    if existing is not None:
                        duplicate_of = existing.id
                        errors = dict(_DUPLICATE_IN_DICTIONARY_ERROR)
                    else:
                        seen_keys.add(key)
                results.append(
                    AbbreviationImportRowResult(index, data, errors, duplicate_of)
                )
            return results

    def commit(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        rows: Sequence[AbbreviationInput],
    ) -> AbbreviationImportOutcome:
        """Persist every still-valid, still-unique row in one transaction (AC6).

        Rows that fail validation or turn out to be duplicates (in-file or
        against the dictionary) at commit time are skipped and reported, not
        silently dropped; every other row is imported.
        """
        now = self._clock()
        imported: list[Abbreviation] = []
        skipped: list[AbbreviationImportRowResult] = []
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            if dictionary is None or dictionary.owner_id != actor_id:
                raise DictionaryAccessError(dictionary_id)

            seen_keys: set[tuple[AbbreviationCategory, str | None, str]] = set()
            for index, data in enumerate(rows, start=1):
                errors = validate_abbreviation_fields(
                    abbreviation=data.abbreviation,
                    full_form=data.full_form,
                    language_code=data.language_code,
                    note=data.note,
                    unresolved=data.unresolved,
                    variants=data.variants,
                )
                if errors:
                    skipped.append(AbbreviationImportRowResult(index, data, errors))
                    continue

                key = abbreviation_duplicate_key(
                    data.category, data.language_code, data.abbreviation
                )
                if key in seen_keys:
                    skipped.append(
                        AbbreviationImportRowResult(
                            index, data, dict(_DUPLICATE_IN_FILE_ERROR)
                        )
                    )
                    continue

                existing = unit_of_work.sources.find_abbreviation_duplicate(
                    dictionary_id, data.category, data.language_code, data.abbreviation
                )
                if existing is not None:
                    skipped.append(
                        AbbreviationImportRowResult(
                            index,
                            data,
                            dict(_DUPLICATE_IN_DICTIONARY_ERROR),
                            duplicate_of=existing.id,
                        )
                    )
                    continue

                seen_keys.add(key)
                abbreviation_id = uuid4()
                abbreviation = Abbreviation(
                    id=abbreviation_id,
                    dictionary_id=dictionary_id,
                    abbreviation=data.abbreviation.strip(),
                    category=data.category,
                    unresolved=data.unresolved,
                    created_at=now,
                    updated_at=now,
                    created_by=actor_id,
                    updated_by=actor_id,
                    full_form=(data.full_form or "").strip() or None,
                    language_code=data.language_code,
                    note=(data.note or "").strip() or None,
                )
                variants = _build_variants(abbreviation_id, data.variants)
                unit_of_work.sources.add_abbreviation(abbreviation)
                unit_of_work.sources.replace_abbreviation_variants(
                    abbreviation_id, variants
                )
                abbreviation.variants = variants
                imported.append(abbreviation)

            unit_of_work.commit()

        return AbbreviationImportOutcome(imported=imported, skipped=skipped)


def export_abbreviations_json(abbreviations: Sequence[Abbreviation]) -> bytes:
    """Serialize abbreviations as a re-importable JSON array (AC9)."""
    payload = [
        {
            "abbreviation": item.abbreviation,
            "full_form": item.full_form,
            "category": item.category.value,
            "language_code": item.language_code,
            "variants": [variant.variant_text for variant in item.variants],
            "note": item.note,
            "unresolved": item.unresolved,
        }
        for item in abbreviations
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_abbreviations_csv(abbreviations: Sequence[Abbreviation]) -> bytes:
    """Serialize abbreviations as a re-importable CSV (AC9)."""
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for item in abbreviations:
        writer.writerow(
            {
                "abbreviation": item.abbreviation,
                "full_form": item.full_form or "",
                "category": item.category.value,
                "language_code": item.language_code or "",
                "variants": ";".join(variant.variant_text for variant in item.variants),
                "note": item.note or "",
                "unresolved": "true" if item.unresolved else "false",
            }
        )
    return buffer.getvalue().encode("utf-8-sig")
