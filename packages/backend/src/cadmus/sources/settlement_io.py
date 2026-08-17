"""BH-30 settlement mapping bulk import and export.

Documented import/export format, identical in shape for CSV and JSON so an
export can be re-imported unchanged. Only the four fields below are ever
accepted on import -- ``settlement_id`` and ``status`` are never part of a
bulk import row, since matching a modern settlement (AC8) and confirming it
(AC9, AC10) are deliberately one-at-a-time, human-in-the-loop actions.
Every imported row is created with ``status=unresolved``, regardless of what
(if anything) an export previously recorded there.

* ``source_label``            -- required; the historical/original label,
  stored verbatim (AC7).
* ``source_note``              -- optional.
* ``modern_settlement_name``   -- optional, free text (not a search match).
* ``settlement_category``      -- optional, free text.

CSV files require a header row matching the field names above. JSON files
are a top-level array of objects with the same fields. Export additionally
includes ``status`` and the confirmed-hierarchy snapshot fields
(``area_name``, ``region_name``, ``community_name``, ``external_community_id``,
``katottg``, ``koatuu``) as read-only informational columns; these are
ignored on import.
"""

import csv
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from io import StringIO
from uuid import UUID, uuid4

from cadmus.sources.abbreviation_io import ImportFormat, UnparsableImportFileError
from cadmus.sources.application import SettlementMappingInput
from cadmus.sources.domain import (
    DictionaryAccessError,
    DictionarySettlementMapping,
    SettlementMappingStatus,
    settlement_mapping_duplicate_key,
    validate_settlement_mapping_fields,
)
from cadmus.sources.ports import SourcesUnitOfWorkFactory

CSV_FIELDS: tuple[str, ...] = (
    "source_label",
    "source_note",
    "modern_settlement_name",
    "settlement_category",
    "status",
    "area_name",
    "region_name",
    "community_name",
    "external_community_id",
    "katottg",
    "koatuu",
)

_DUPLICATE_IN_FILE_ERROR = {"source_label": "Такий запис уже є в цьому файлі імпорту."}
_DUPLICATE_IN_DICTIONARY_ERROR = {
    "source_label": "Така географічна позначка вже існує в словнику."
}


@dataclass(frozen=True)
class SettlementMappingImportRowResult:
    """One previewed or committed import row."""

    row_number: int
    input: SettlementMappingInput | None
    errors: dict[str, str]
    duplicate_of: UUID | None = None


@dataclass(frozen=True)
class SettlementMappingImportOutcome:
    """Result of a commit: what was actually persisted vs. skipped."""

    imported: list[DictionarySettlementMapping]
    skipped: list[SettlementMappingImportRowResult]


def parse_settlement_mappings_import(
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
    return [dict(row) for row in reader]


def _row_to_input(
    row: dict[str, object],
) -> tuple[SettlementMappingInput | None, dict[str, str]]:
    """Type-check one raw row into a :class:`SettlementMappingInput`, or errors.

    ``settlement_id`` is always ``None`` and ``status`` is always
    ``UNRESOLVED`` for an imported row -- any ``status``/hierarchy columns
    present in the raw row (e.g. from a re-imported export) are ignored.
    """
    source_label = row.get("source_label")
    if not isinstance(source_label, str) or not source_label.strip():
        return None, {"source_label": "Вкажіть географічну позначку з оригіналу."}

    source_note = row.get("source_note")
    source_note = (
        source_note if isinstance(source_note, str) and source_note.strip() else None
    )

    modern_settlement_name = row.get("modern_settlement_name")
    modern_settlement_name = (
        modern_settlement_name
        if isinstance(modern_settlement_name, str) and modern_settlement_name.strip()
        else None
    )

    settlement_category = row.get("settlement_category")
    settlement_category = (
        settlement_category
        if isinstance(settlement_category, str) and settlement_category.strip()
        else None
    )

    field_errors = validate_settlement_mapping_fields(
        source_label=source_label,
        source_note=source_note,
        modern_settlement_name=modern_settlement_name,
    )
    if field_errors:
        return None, field_errors

    return (
        SettlementMappingInput(
            source_label=source_label.strip(),
            source_note=source_note,
            modern_settlement_name=modern_settlement_name,
            settlement_category=settlement_category,
            settlement_id=None,
            status=SettlementMappingStatus.UNRESOLVED,
        ),
        {},
    )


class SettlementMappingImportService:
    """Preview and commit BH-30 bulk settlement mapping imports."""

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
    ) -> list[SettlementMappingImportRowResult]:
        """Parse and validate a file without persisting anything."""
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            if dictionary is None or dictionary.owner_id != actor_id:
                raise DictionaryAccessError(dictionary_id)

            raw_rows = parse_settlement_mappings_import(raw, import_format)
            results: list[SettlementMappingImportRowResult] = []
            seen_keys: set[str] = set()
            for index, raw_row in enumerate(raw_rows, start=1):
                data, errors = _row_to_input(raw_row)
                if data is None:
                    results.append(
                        SettlementMappingImportRowResult(index, None, errors)
                    )
                    continue

                key = settlement_mapping_duplicate_key(data.source_label)
                duplicate_of: UUID | None = None
                if key in seen_keys:
                    errors = dict(_DUPLICATE_IN_FILE_ERROR)
                else:
                    existing = unit_of_work.sources.find_settlement_mapping_duplicate(
                        dictionary_id, key
                    )
                    if existing is not None:
                        duplicate_of = existing.id
                        errors = dict(_DUPLICATE_IN_DICTIONARY_ERROR)
                    else:
                        seen_keys.add(key)
                results.append(
                    SettlementMappingImportRowResult(index, data, errors, duplicate_of)
                )
            return results

    def commit(
        self,
        dictionary_id: UUID,
        actor_id: UUID,
        rows: Sequence[SettlementMappingInput],
    ) -> SettlementMappingImportOutcome:
        """Persist every still-valid, still-unique row in one transaction.

        Rows that fail validation or turn out to be duplicates (in-file or
        against the dictionary) at commit time are skipped and reported, not
        silently dropped; every other row is imported as ``unresolved``.
        """
        now = self._clock()
        imported: list[DictionarySettlementMapping] = []
        skipped: list[SettlementMappingImportRowResult] = []
        with self._unit_of_work_factory() as unit_of_work:
            dictionary = unit_of_work.sources.get_dictionary(dictionary_id)
            if dictionary is None or dictionary.owner_id != actor_id:
                raise DictionaryAccessError(dictionary_id)

            seen_keys: set[str] = set()
            for index, data in enumerate(rows, start=1):
                errors = validate_settlement_mapping_fields(
                    source_label=data.source_label,
                    source_note=data.source_note,
                    modern_settlement_name=data.modern_settlement_name,
                )
                if errors:
                    skipped.append(
                        SettlementMappingImportRowResult(index, data, errors)
                    )
                    continue

                key = settlement_mapping_duplicate_key(data.source_label)
                if key in seen_keys:
                    skipped.append(
                        SettlementMappingImportRowResult(
                            index, data, dict(_DUPLICATE_IN_FILE_ERROR)
                        )
                    )
                    continue

                existing = unit_of_work.sources.find_settlement_mapping_duplicate(
                    dictionary_id, key
                )
                if existing is not None:
                    skipped.append(
                        SettlementMappingImportRowResult(
                            index,
                            data,
                            dict(_DUPLICATE_IN_DICTIONARY_ERROR),
                            duplicate_of=existing.id,
                        )
                    )
                    continue

                seen_keys.add(key)
                mapping = DictionarySettlementMapping(
                    id=uuid4(),
                    dictionary_id=dictionary_id,
                    source_label=data.source_label.strip(),
                    status=SettlementMappingStatus.UNRESOLVED,
                    created_at=now,
                    updated_at=now,
                    created_by=actor_id,
                    updated_by=actor_id,
                    source_note=(data.source_note or "").strip() or None,
                    modern_settlement_name=(data.modern_settlement_name or "").strip()
                    or None,
                    settlement_category=data.settlement_category,
                )
                unit_of_work.sources.add_settlement_mapping(mapping)
                imported.append(mapping)

            unit_of_work.commit()

        return SettlementMappingImportOutcome(imported=imported, skipped=skipped)


def export_settlement_mappings_json(
    mappings: Sequence[DictionarySettlementMapping],
) -> bytes:
    """Serialize mappings as a re-importable JSON array.

    Only the four import fields round-trip; ``status`` and the hierarchy
    snapshot are included as read-only informational fields.
    """
    payload = [
        {
            "source_label": item.source_label,
            "source_note": item.source_note,
            "modern_settlement_name": item.modern_settlement_name,
            "settlement_category": item.settlement_category,
            "status": item.status.value,
            "area_name": item.area_name,
            "region_name": item.region_name,
            "community_name": item.community_name,
            "external_community_id": item.external_community_id,
            "katottg": item.katottg,
            "koatuu": item.koatuu,
        }
        for item in mappings
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_settlement_mappings_csv(
    mappings: Sequence[DictionarySettlementMapping],
) -> bytes:
    """Serialize mappings as a re-importable CSV.

    Only the four import fields round-trip; ``status`` and the hierarchy
    snapshot are included as read-only informational columns.
    """
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for item in mappings:
        writer.writerow(
            {
                "source_label": item.source_label,
                "source_note": item.source_note or "",
                "modern_settlement_name": item.modern_settlement_name or "",
                "settlement_category": item.settlement_category or "",
                "status": item.status.value,
                "area_name": item.area_name or "",
                "region_name": item.region_name or "",
                "community_name": item.community_name or "",
                "external_community_id": item.external_community_id or "",
                "katottg": item.katottg or "",
                "koatuu": item.koatuu or "",
            }
        )
    return buffer.getvalue().encode("utf-8-sig")
