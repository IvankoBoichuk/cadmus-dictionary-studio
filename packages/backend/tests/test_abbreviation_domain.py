from cadmus.sources import AbbreviationCategory
from cadmus.sources.domain import (
    abbreviation_duplicate_key,
    validate_abbreviation_fields,
)


def _errors(**overrides: object) -> dict[str, str]:
    defaults: dict[str, object] = {
        "abbreviation": "розм.",
        "full_form": "розмовне",
        "language_code": "uk",
        "note": None,
        "unresolved": False,
        "variants": (),
    }
    defaults.update(overrides)
    return validate_abbreviation_fields(**defaults)  # type: ignore[arg-type]


def test_valid_resolved_entry_has_no_errors() -> None:
    assert _errors() == {}


def test_blank_abbreviation_is_rejected() -> None:
    assert "abbreviation" in _errors(abbreviation="   ")


def test_abbreviation_over_64_characters_is_rejected() -> None:
    assert "abbreviation" in _errors(abbreviation="a" * 65)


def test_missing_full_form_is_rejected_when_not_unresolved() -> None:
    assert "full_form" in _errors(full_form=None)


def test_missing_full_form_is_allowed_when_unresolved() -> None:
    assert _errors(full_form=None, unresolved=True) == {}


def test_full_form_over_512_characters_is_rejected() -> None:
    assert "full_form" in _errors(full_form="a" * 513)


def test_unknown_language_code_is_rejected() -> None:
    assert "language_code" in _errors(language_code="zz")


def test_language_code_is_optional() -> None:
    assert _errors(language_code=None) == {}


def test_note_over_2000_characters_is_rejected() -> None:
    assert "note" in _errors(note="a" * 2001)


def test_blank_variant_is_rejected() -> None:
    assert "variants" in _errors(variants=("valid", "   "))


def test_variant_over_255_characters_is_rejected() -> None:
    assert "variants" in _errors(variants=("a" * 256,))


def test_duplicate_key_normalizes_whitespace() -> None:
    key = abbreviation_duplicate_key(AbbreviationCategory.GRAMMAR, "uk", "  розм. ")
    assert key == (AbbreviationCategory.GRAMMAR, "uk", "розм.")


def test_duplicate_key_is_case_sensitive() -> None:
    lower = abbreviation_duplicate_key(AbbreviationCategory.GRAMMAR, "uk", "тис.")
    upper = abbreviation_duplicate_key(AbbreviationCategory.GRAMMAR, "uk", "Тис.")
    assert lower != upper
