"""Framework-free reference-lexicon domain model and VESUM parser."""

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import NAMESPACE_URL, UUID, uuid5

VESUM_CODE = "vesum"
VESUM_NAME = "Великий електронний словник української мови"
VESUM_LANGUAGE_CODE = "uk"
VESUM_SOURCE_URL = "https://github.com/brown-uk/dict_uk"
VESUM_LICENSE_ID = "CC-BY-NC-SA-4.0"

# Matches the exclusions used by dict_uk's own getSpellWords task. We keep
# every record for research, but only records without these tags are offered
# as literary-standard equivalents by default.
NON_STANDARD_TAGS = frozenset(
    {"bad", "subst", "alt", "arch", "slang", "vulg", "obsc", "rare"}
)

# Tags documented by VESUM as lemma-disambiguating, plus stable grammatical
# properties needed to avoid collapsing homographic lemmas.
_LEMMA_KEY_TAGS = frozenset(
    {
        "anim",
        "inanim",
        "unanim",
        "fname",
        "lname",
        "pname",
        "prop",
        "geo",
        "m",
        "f",
        "n",
        "ns",
        "np",
        "nv",
        "imperf",
        "perf",
        "rev",
        "actv",
        "pasv",
        "pron",
        "pers",
        "refl",
        "pos",
        "dem",
        "def",
        "int",
        "rel",
        "neg",
        "ind",
        "gen",
        "emph",
    }
)
_XP_RE = re.compile(r"^xp[1-9]$")


class VesumParseError(ValueError):
    """Raised when a generated VESUM flat row violates its three-column format."""


class ReferenceMatchType(StrEnum):
    """Why a reference lemma matched a user's search query."""

    LEMMA = "lemma"
    WORD_FORM = "word_form"


@dataclass
class ReferenceLexicon:
    """One versioned external lexical reference dataset."""

    id: UUID
    code: str
    name: str
    language_code: str
    version: str
    source_url: str
    license_id: str
    source_commit: str | None
    checksum: str
    imported_at: datetime
    is_active: bool = True


@dataclass
class ReferenceLemma:
    """A lemma imported from a reference lexicon, independent of Cadmus sources."""

    id: UUID
    lexicon_id: UUID
    external_key: str
    lemma: str
    normalized_lemma: str
    part_of_speech: str
    key_tags: list[str]
    is_standard: bool
    is_active: bool = True


@dataclass
class ReferenceWordForm:
    """One inflected or derived VESUM form pointing to its reference lemma."""

    id: UUID
    lemma_id: UUID
    form: str
    normalized_form: str
    morphology: str
    is_standard: bool
    is_active: bool = True


@dataclass(frozen=True)
class ReferenceLemmaMatch:
    """A search result with the form that caused the match, if applicable."""

    lemma: ReferenceLemma
    match_type: ReferenceMatchType
    matched_form: str | None = None


@dataclass(frozen=True)
class VesumRecord:
    """Normalized representation of one dict_corp_lt.txt row."""

    lemma: ReferenceLemma
    word_form: ReferenceWordForm


def normalize_ukrainian_text(value: str) -> str:
    """Normalize for lookup without changing the imported source spelling."""

    normalized = unicodedata.normalize("NFC", value.strip())
    normalized = normalized.replace("’", "'").replace("ʼ", "'")
    return " ".join(normalized.split()).casefold()


def reference_lexicon_id(code: str) -> UUID:
    """Stable ID so a re-import updates the same logical provider."""

    return uuid5(NAMESPACE_URL, f"cadmus:reference-lexicon:{code}")


def _lemma_key_tags(tags: list[str]) -> list[str]:
    selected = {
        tag
        for tag in tags[1:]
        if tag in _LEMMA_KEY_TAGS or _XP_RE.fullmatch(tag) is not None
    }
    return sorted(selected)


def _is_standard(tags: list[str]) -> bool:
    return not any(tag in NON_STANDARD_TAGS for tag in tags)


def parse_vesum_line(line: str, lexicon_id: UUID) -> VesumRecord | None:
    """Parse VESUM generated word lemma tagStr flat format.

    Upstream DicEntry.toFlatString emits exactly three whitespace-separated
    columns. Blank lines are ignored; malformed rows fail the import rather
    than silently losing morphology.
    """

    raw = line.strip()
    if not raw:
        return None
    parts = raw.split()
    if len(parts) != 3:
        raise VesumParseError(
            f"expected 3 VESUM columns (word lemma tags), got {len(parts)}"
        )

    form, lemma_text, morphology = parts
    tags = morphology.split(":")
    if not tags or not tags[0]:
        raise VesumParseError("VESUM row has no part-of-speech tag")

    normalized_lemma = normalize_ukrainian_text(lemma_text)
    normalized_form = normalize_ukrainian_text(form)
    pos = tags[0]
    key_tags = _lemma_key_tags(tags)
    external_key = "|".join((normalized_lemma, pos, ",".join(key_tags)))
    lemma_id = uuid5(lexicon_id, f"lemma:{external_key}")
    standard = _is_standard(tags)

    lemma = ReferenceLemma(
        id=lemma_id,
        lexicon_id=lexicon_id,
        external_key=external_key,
        lemma=lemma_text,
        normalized_lemma=normalized_lemma,
        part_of_speech=pos,
        key_tags=key_tags,
        is_standard=standard,
    )
    word_form = ReferenceWordForm(
        id=uuid5(lemma_id, f"form:{normalized_form}|{morphology}"),
        lemma_id=lemma_id,
        form=form,
        normalized_form=normalized_form,
        morphology=morphology,
        is_standard=standard,
    )
    return VesumRecord(lemma=lemma, word_form=word_form)
