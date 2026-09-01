"""``dedupe_extracted_fields`` -- collapsing an AI extraction result's noise."""

from datetime import UTC, datetime
from uuid import uuid4

from cadmus.lexicography import (
    ArticleSchema,
    EntryFieldRole,
    ExtractedField,
    SchemaGenerationStatus,
    dedupe_extracted_fields,
)

NOW = datetime(2026, 9, 1, tzinfo=UTC)


def _schema(fields: list[dict[str, object]]) -> ArticleSchema:
    return ArticleSchema(
        id=uuid4(),
        dictionary_id=uuid4(),
        version=1,
        status=SchemaGenerationStatus.READY,
        source_description="",
        definition={"fields": fields},
        created_at=NOW,
        created_by=uuid4(),
    )


def _item(path: str, value: str, confidence: float) -> ExtractedField:
    return ExtractedField(path, EntryFieldRole.OTHER, value, confidence)


def test_collapses_exact_repeats_keeping_the_highest_confidence() -> None:
    schema = _schema([{"name": "district", "role": "other", "repeatable": True}])
    out = dedupe_extracted_fields(
        schema,
        [
            _item("district", "Сок.", 0.80),
            _item("district", " сок. ", 0.90),
            _item("district", "Сок.", 0.70),
        ],
    )
    assert [(o.value, o.confidence) for o in out] == [("Сок.", 0.90)]


def test_repeatable_node_keeps_distinct_values_in_order() -> None:
    schema = _schema([{"name": "district", "role": "other", "repeatable": True}])
    out = dedupe_extracted_fields(
        schema,
        [
            _item("district", "Сок.", 0.9),
            _item("district", "Кельм.", 0.9),
            _item("district", "Сок.", 0.9),
        ],
    )
    assert [o.value for o in out] == ["Сок.", "Кельм."]


def test_non_repeatable_node_keeps_only_its_best_value() -> None:
    schema = _schema([{"name": "headword", "role": "headword", "repeatable": False}])
    out = dedupe_extracted_fields(
        schema,
        [
            _item("headword", "перший", 0.80),
            _item("headword", "другий", 0.95),
            _item("headword", "третій", 0.90),
        ],
    )
    assert [o.value for o in out] == ["другий"]


def test_unknown_path_is_left_untouched() -> None:
    schema = _schema([{"name": "headword", "role": "headword"}])
    out = dedupe_extracted_fields(
        schema,
        [_item("mystery[3].leaf", "a", 0.5), _item("mystery[3].leaf", "b", 0.4)],
    )
    assert [o.value for o in out] == ["a", "b"]
