"""Pure text-cleanup helpers for OCR'd entry text: rejoining line-break
hyphenation and collapsing punctuation the presentation formula doubled
(BH-148)."""

from __future__ import annotations

import pytest
from cadmus.lexicography import collapse_repeated_punctuation, dehyphenate_line_breaks

# --------------------------------------------------------------------------- #
# dehyphenate_line_breaks
# --------------------------------------------------------------------------- #


def test_rejoins_a_word_split_with_a_hyphen_and_space() -> None:
    text = "Клинок під пахвою у чоловічій або жіночій сорочці, ко- жусі тощо."  # noqa: RUF001
    cleaned, uncertain = dehyphenate_line_breaks(text)
    assert cleaned == (
        "Клинок під пахвою у чоловічій або жіночій сорочці, кожусі тощо."  # noqa: RUF001
    )
    assert uncertain is True


def test_rejoins_across_a_single_newline() -> None:
    cleaned, _ = dehyphenate_line_breaks("розі-\nрваний рядок")  # noqa: RUF001
    assert cleaned == "розірваний рядок"


def test_leaves_a_real_compound_untouched() -> None:
    cleaned, uncertain = dehyphenate_line_breaks("тим-то отут по-новому")
    assert cleaned == "тим-то отут по-новому"
    assert uncertain is False


def test_leaves_an_inflection_dash_untouched() -> None:
    # A dictionary body's "-і" ending: no letter before the hyphen.  # noqa: RUF003
    cleaned, _ = dehyphenate_line_breaks("АЛТИЦА, -і, ж.")  # noqa: RUF001
    assert cleaned == "АЛТИЦА, -і, ж."  # noqa: RUF001


def test_does_not_join_across_a_blank_line() -> None:
    cleaned, _ = dehyphenate_line_breaks("кінець рядка сло-\n\nнове слово")  # noqa: RUF001
    assert cleaned == "кінець рядка сло-\n\nнове слово"  # noqa: RUF001


def test_resolver_keeps_the_hyphen_for_a_known_compound() -> None:
    def resolve(joined: str, hyphenated: str) -> str:
        assert joined == "військовополітичний"
        assert hyphenated == "військово-політичний"
        return "keep"

    cleaned, uncertain = dehyphenate_line_breaks(
        "текст військово- політичний тут", resolve=resolve
    )
    assert cleaned == "текст військово-політичний тут"
    assert uncertain is False


def test_resolver_join_decision_is_not_flagged_uncertain() -> None:
    cleaned, uncertain = dehyphenate_line_breaks(
        "ко- жусі", resolve=lambda joined, hyphenated: "join"
    )
    assert cleaned == "кожусі"
    assert uncertain is False


def test_resolver_unknown_joins_and_flags() -> None:
    cleaned, uncertain = dehyphenate_line_breaks(
        "ко- жусі", resolve=lambda joined, hyphenated: "unknown"
    )
    assert cleaned == "кожусі"
    assert uncertain is True


def test_no_hyphenation_is_a_cheap_noop() -> None:
    assert dehyphenate_line_breaks("звичайний рядок без переносів") == (
        "звичайний рядок без переносів",
        False,
    )


# --------------------------------------------------------------------------- #
# collapse_repeated_punctuation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ж..", "ж."),
        ("Хот..", "Хот."),
        ("Кіцм., Глиб., Нов., Хот.. Файну", "Кіцм., Глиб., Нов., Хот. Файну"),
        ("одне,, друге", "одне, друге"),
        ("а;; б", "а; б"),  # noqa: RUF001
        ("текст:: щось", "текст: щось"),
    ],
)
def test_collapses_a_doubled_delimiter(raw: str, expected: str) -> None:
    assert collapse_repeated_punctuation(raw) == expected


def test_keeps_an_ellipsis() -> None:
    assert collapse_repeated_punctuation("тощо...") == "тощо..."
    assert collapse_repeated_punctuation("тощо....") == "тощо..."


def test_leaves_mixed_neighbours_alone() -> None:
    assert collapse_repeated_punctuation("(Атаки Хот.).") == "(Атаки Хот.)."
    assert collapse_repeated_punctuation("слово.,") == "слово.,"
