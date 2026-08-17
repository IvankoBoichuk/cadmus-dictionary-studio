from cadmus.sources import (
    settlement_mapping_duplicate_key,
    validate_settlement_mapping_fields,
)


def _errors(**overrides: object) -> dict[str, str]:
    defaults: dict[str, object] = {
        "source_label": "Іванівка",
        "source_note": None,
        "modern_settlement_name": None,
    }
    defaults.update(overrides)
    return validate_settlement_mapping_fields(**defaults)  # type: ignore[arg-type]


def test_valid_mapping_has_no_errors() -> None:
    assert _errors() == {}


def test_empty_source_label_is_rejected() -> None:
    errors = _errors(source_label="")
    assert "source_label" in errors


def test_blank_source_label_is_rejected() -> None:
    errors = _errors(source_label="   ")
    assert "source_label" in errors


def test_too_long_source_label_is_rejected() -> None:
    errors = _errors(source_label="a" * 513)
    assert "source_label" in errors


def test_max_length_source_label_is_accepted() -> None:
    errors = _errors(source_label="a" * 512)
    assert "source_label" not in errors


def test_too_long_source_note_is_rejected() -> None:
    errors = _errors(source_note="a" * 2001)
    assert "source_note" in errors


def test_max_length_source_note_is_accepted() -> None:
    errors = _errors(source_note="a" * 2000)
    assert "source_note" not in errors


def test_too_long_modern_settlement_name_is_rejected() -> None:
    errors = _errors(modern_settlement_name="a" * 256)
    assert "modern_settlement_name" in errors


def test_max_length_modern_settlement_name_is_accepted() -> None:
    errors = _errors(modern_settlement_name="a" * 255)
    assert "modern_settlement_name" not in errors


def test_duplicate_key_trims_whitespace() -> None:
    assert settlement_mapping_duplicate_key("  Іванівка  ") == "Іванівка"


def test_duplicate_key_does_not_case_fold() -> None:
    upper = settlement_mapping_duplicate_key("Іванівка")
    lower = settlement_mapping_duplicate_key("іванівка")
    assert upper != lower
