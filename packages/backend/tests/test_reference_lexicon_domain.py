from uuid import uuid4

import pytest
from cadmus.reference_lexicon import (
    VesumParseError,
    normalize_ukrainian_text,
    parse_vesum_line,
)


def test_normalize_ukrainian_text_preserves_source_independently() -> None:
    source = "  П'ЄСА  "
    assert normalize_ukrainian_text(source) == "п'єса"
    assert source == "  П'ЄСА  "


def test_parse_vesum_line_extracts_form_lemma_pos_and_morphology() -> None:
    lexicon_id = uuid4()
    record = parse_vesum_line(
        "заавансованого заавансований adjp:pasv:perf:m:v_rod",
        lexicon_id,
    )

    assert record is not None
    assert record.lemma.lemma == "заавансований"
    assert record.lemma.part_of_speech == "adjp"
    assert record.lemma.key_tags == ["pasv", "perf"]
    assert record.word_form.form == "заавансованого"
    assert record.word_form.morphology == "adjp:pasv:perf:m:v_rod"
    assert record.word_form.lemma_id == record.lemma.id


def test_adjective_gender_is_not_a_lemma_discriminator() -> None:
    lexicon_id = uuid4()
    masculine = parse_vesum_line("білий білий adj:m:v_naz", lexicon_id)
    feminine = parse_vesum_line("біла білий adj:f:v_naz", lexicon_id)

    assert masculine is not None
    assert feminine is not None
    assert masculine.lemma.id == feminine.lemma.id


def test_noun_gender_remains_a_lemma_discriminator() -> None:
    lexicon_id = uuid4()
    masculine = parse_vesum_line("сирота сирота noun:anim:m:v_naz", lexicon_id)
    feminine = parse_vesum_line("сирота сирота noun:anim:f:v_naz", lexicon_id)

    assert masculine is not None
    assert feminine is not None
    assert masculine.lemma.id != feminine.lemma.id


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
    assert record.lemma.is_standard is False
    assert record.word_form.is_standard is False


def test_standard_vesum_row_is_marked_standard() -> None:
    record = parse_vesum_line(
        "господар господар noun:anim:m:v_naz",
        uuid4(),
    )

    assert record is not None
    assert record.lemma.is_standard is True


def test_malformed_vesum_row_fails_instead_of_silently_dropping_data() -> None:
    with pytest.raises(VesumParseError, match="expected 3 VESUM columns"):
        parse_vesum_line("only two-columns", uuid4())
