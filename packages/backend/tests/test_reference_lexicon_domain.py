from uuid import uuid4

import pytest
from cadmus.reference_lexicon import (
    VesumParseError,
    VesumVisualParser,
    normalize_ukrainian_text,
    parse_morphology,
    parse_vesum_line,
)


def test_normalize_ukrainian_text_preserves_source_independently() -> None:
    source = "  П'ЄСА  "
    assert normalize_ukrainian_text(source) == "п'єса"
    assert source == "  П'ЄСА  "


def test_parse_morphology_extracts_documented_grammatical_features() -> None:
    tags, features = parse_morphology("adjp:pasv:perf:m:v_rod:alt")

    assert tags == ["adjp", "pasv", "perf", "m", "v_rod", "alt"]
    assert features == {
        "case": "v_rod",
        "gender": "m",
        "aspect": "perf",
        "voice": "pasv",
        "qualifiers": ["alt"],
    }


def test_parse_morphology_keeps_governed_and_unknown_tags() -> None:
    tags, features = parse_morphology("prep:rv_rod:rv_zna:future_tag")

    assert tags == ["prep", "rv_rod", "rv_zna", "future_tag"]
    assert features["governed_cases"] == ["rv_rod", "rv_zna"]
    assert features["other_tags"] == ["future_tag"]


def test_visual_parser_groups_indented_forms_under_lemma() -> None:
    lexicon_id = uuid4()
    parser = VesumVisualParser(lexicon_id)

    head = parser.parse_line(
        "заавансований adjp:pasv:perf:m:v_naz\n",
        line_number=1,
    )
    form = parser.parse_line(
        "  заавансованого adjp:pasv:perf:m:v_rod\n",
        line_number=2,
    )

    assert head is not None
    assert form is not None
    assert head.lemma.lemma == "заавансований"
    assert form.lemma.id == head.lemma.id
    assert form.word_form.form == "заавансованого"
    assert form.word_form.morphology_features["case"] == "v_rod"


def test_visual_parser_uses_lemma_row_for_lemma_identity() -> None:
    lexicon_id = uuid4()
    parser = VesumVisualParser(lexicon_id)

    head = parser.parse_line("білий adj:m:v_naz\n")
    feminine = parser.parse_line("  біла adj:f:v_naz\n")

    assert head is not None
    assert feminine is not None
    assert feminine.lemma.id == head.lemma.id


def test_visual_parser_rejects_form_before_lemma() -> None:
    parser = VesumVisualParser(uuid4())

    with pytest.raises(VesumParseError, match="before its lemma"):
        parser.parse_line("  форми noun:inanim:f:v_rod\n", line_number=1)


def test_flat_parser_remains_available_for_compatibility() -> None:
    record = parse_vesum_line(
        "господаря господар noun:anim:m:v_rod",
        uuid4(),
    )

    assert record is not None
    assert record.lemma.lemma == "господар"
    assert record.word_form.morphology_tags == [
        "noun",
        "anim",
        "m",
        "v_rod",
    ]


@pytest.mark.parametrize(
    "tag",
    ["bad", "subst", "alt", "arch", "slang", "vulg", "obsc", "rare"],
)
def test_non_standard_vesum_tags_are_retained_but_not_standard(tag: str) -> None:
    record = parse_vesum_line(
        f"форма лема noun:inanim:f:v_naz:{tag}",
        uuid4(),
    )

    assert record is not None
    assert record.word_form.is_standard is False
    assert tag in record.word_form.morphology_tags


def test_standard_vesum_row_is_marked_standard() -> None:
    record = parse_vesum_line(
        "господар господар noun:anim:m:v_naz",
        uuid4(),
    )

    assert record is not None
    assert record.lemma.is_standard is True
    assert record.word_form.is_standard is True
