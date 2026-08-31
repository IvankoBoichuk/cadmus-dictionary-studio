"""Framework-free reference-lexicon domain model and VESUM parsers."""

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
VESUM_RELEASE_ASSET_NAME = "dict_corp_vis.txt.bz2"

type MorphologyFeatureValue = str | bool | list[str]
type MorphologyFeatures = dict[str, MorphologyFeatureValue]

NON_STANDARD_TAGS = frozenset(
    {"bad", "subst", "alt", "arch", "slang", "vulg", "obsc", "rare"}
)

_NOUN_KEY_TAGS = frozenset(
    {
        "anim",
        "inanim",
        "unanim",
        "fname",
        "lname",
        "pname",
        "geo",
    }
)
_VERB_KEY_TAGS = frozenset({"imperf", "perf", "rev"})
_ADVP_KEY_TAGS = frozenset({"imperf", "perf"})
_PRONOUN_KEY_TAGS = frozenset(
    {
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

_CASE_TAGS = frozenset({"v_naz", "v_rod", "v_dav", "v_zna", "v_oru", "v_mis", "v_kly"})
_NUMBER_TAGS = frozenset({"s", "p"})
_GENDER_TAGS = frozenset({"m", "f", "n"})
_ANIMACY_TAGS = frozenset({"anim", "inanim", "unanim"})
_ASPECT_TAGS = frozenset({"imperf", "perf"})
_VOICE_TAGS = frozenset({"actv", "pasv"})
_TENSE_TAGS = frozenset({"futr", "past", "pres"})
_PERSON_TAGS = frozenset({"1", "2", "3"})
_DEGREE_TAGS = frozenset({"compb", "compc", "comps"})
_PRONOUN_TYPE_TAGS = frozenset(
    {"pers", "refl", "pos", "dem", "def", "int", "rel", "neg", "ind", "gen", "emph"}
)
_ACCUSATIVE_ANIMACY_TAGS = frozenset({"ranim", "rinanim"})
_QUALIFIER_TAGS = frozenset(
    {
        "abbr",
        "bad",
        "err",
        "subst",
        "rare",
        "coll",
        "arch",
        "slang",
        "alt",
        "vulg",
        "obsc",
        "up92",
        "up19",
        "var",
        "foreign",
        "insert",
        "predic",
        "prop",
        "geo",
        "short",
        "long",
    }
)


class VesumParseError(ValueError):
    """Raised when a VESUM release row violates its documented format."""


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
    morphology_tags: list[str]
    morphology_features: MorphologyFeatures
    is_standard: bool
    is_active: bool = True


@dataclass(frozen=True)
class ReferenceLemmaMatch:
    """A search result with morphology for the form that caused the match."""

    lemma: ReferenceLemma
    match_type: ReferenceMatchType
    matched_form: str | None = None
    matched_form_morphology: str | None = None
    matched_form_tags: list[str] | None = None
    matched_form_features: MorphologyFeatures | None = None


@dataclass(frozen=True)
class VesumRecord:
    """One VESUM form normalized for reference-lexicon persistence."""

    lemma: ReferenceLemma
    word_form: ReferenceWordForm


def normalize_ukrainian_text(value: str) -> str:
    """Normalize for lookup without changing the imported source spelling."""

    normalized = unicodedata.normalize("NFC", value.strip())
    normalized = normalized.replace("’", "'").replace("ʼ", "'")  # noqa: RUF001
    return " ".join(normalized.split()).casefold()


def reference_lexicon_id(code: str) -> UUID:
    """Stable ID so a re-import updates the same logical provider."""

    return uuid5(NAMESPACE_URL, f"cadmus:reference-lexicon:{code}")


def _lemma_key_tags(tags: list[str]) -> list[str]:
    pos = tags[0]
    allowed: frozenset[str]
    if pos == "noun":
        allowed = _NOUN_KEY_TAGS
    elif pos == "verb":
        allowed = _VERB_KEY_TAGS
    elif pos == "advp":
        allowed = _ADVP_KEY_TAGS
    else:
        allowed = frozenset()

    selected = {
        tag
        for tag in tags[1:]
        if tag in allowed
        or tag in _PRONOUN_KEY_TAGS
        or _XP_RE.fullmatch(tag) is not None
    }
    return sorted(selected)


def _is_standard(tags: list[str]) -> bool:
    return not any(tag in NON_STANDARD_TAGS for tag in tags)


def _first_tag(tags: list[str], candidates: frozenset[str]) -> str | None:
    return next((tag for tag in tags if tag in candidates), None)


def parse_morphology(morphology: str) -> tuple[list[str], MorphologyFeatures]:
    """Parse stable VESUM features and preserve all raw tags."""

    tags = morphology.split(":")
    if not tags or not tags[0]:
        raise VesumParseError("VESUM row has no part-of-speech tag")

    feature_tags = tags[1:]
    features: MorphologyFeatures = {}
    classified: set[str] = set()

    groups = (
        ("case", _CASE_TAGS),
        ("number", _NUMBER_TAGS),
        ("gender", _GENDER_TAGS),
        ("animacy", _ANIMACY_TAGS),
        ("aspect", _ASPECT_TAGS),
        ("voice", _VOICE_TAGS),
        ("tense", _TENSE_TAGS),
        ("person", _PERSON_TAGS),
        ("degree", _DEGREE_TAGS),
        ("pronoun_type", _PRONOUN_TYPE_TAGS),
        ("accusative_animacy", _ACCUSATIVE_ANIMACY_TAGS),
    )
    for key, candidates in groups:
        value = _first_tag(feature_tags, candidates)
        if value is not None:
            features[key] = value
            classified.add(value)

    if "inf" in feature_tags:
        features["verb_form"] = "inf"
        classified.add("inf")
    elif "impers" in feature_tags:
        features["verb_form"] = "impers"
        classified.add("impers")

    if "impr" in feature_tags:
        features["mood"] = "impr"
        classified.add("impr")

    if "pron" in feature_tags:
        features["is_pronoun"] = True
        classified.add("pron")

    governed_cases = [tag for tag in feature_tags if tag.startswith("rv_")]
    if governed_cases:
        features["governed_cases"] = governed_cases
        classified.update(governed_cases)

    qualifiers = [tag for tag in feature_tags if tag in _QUALIFIER_TAGS]
    if qualifiers:
        features["qualifiers"] = qualifiers
        classified.update(qualifiers)

    other_tags = [tag for tag in feature_tags if tag not in classified]
    if other_tags:
        features["other_tags"] = other_tags

    return tags, features


def _build_lemma(
    lemma_text: str,
    morphology: str,
    lexicon_id: UUID,
) -> ReferenceLemma:
    tags, _features = parse_morphology(morphology)
    normalized_lemma = normalize_ukrainian_text(lemma_text)
    pos = tags[0]
    key_tags = _lemma_key_tags(tags)
    external_key = "|".join((normalized_lemma, pos, ",".join(key_tags)))
    lemma_id = uuid5(lexicon_id, f"lemma:{external_key}")
    return ReferenceLemma(
        id=lemma_id,
        lexicon_id=lexicon_id,
        external_key=external_key,
        lemma=lemma_text,
        normalized_lemma=normalized_lemma,
        part_of_speech=pos,
        key_tags=key_tags,
        is_standard=_is_standard(tags),
    )


def _build_word_form(
    lemma: ReferenceLemma,
    form: str,
    morphology: str,
) -> ReferenceWordForm:
    tags, features = parse_morphology(morphology)
    normalized_form = normalize_ukrainian_text(form)
    return ReferenceWordForm(
        id=uuid5(lemma.id, f"form:{normalized_form}|{morphology}"),
        lemma_id=lemma.id,
        form=form,
        normalized_form=normalized_form,
        morphology=morphology,
        morphology_tags=tags,
        morphology_features=features,
        is_standard=_is_standard(tags),
    )


def parse_vesum_line(line: str, lexicon_id: UUID) -> VesumRecord | None:
    """Parse the legacy generated flat word/lemma/tag format."""

    raw = line.strip()
    if not raw:
        return None
    parts = raw.split()
    if len(parts) != 3:
        raise VesumParseError(
            f"expected 3 VESUM columns (word lemma tags), got {len(parts)}"
        )
    form, lemma_text, morphology = parts
    lemma = _build_lemma(lemma_text, morphology, lexicon_id)
    return VesumRecord(
        lemma=lemma,
        word_form=_build_word_form(lemma, form, morphology),
    )


class VesumVisualParser:
    """Stateful parser for release dict_corp_vis.txt grouped-by-lemma rows."""

    def __init__(self, lexicon_id: UUID) -> None:
        self._lexicon_id = lexicon_id
        self._current_lemma: ReferenceLemma | None = None

    def parse_line(
        self,
        line: str,
        *,
        line_number: int | None = None,
    ) -> VesumRecord | None:
        raw = line.rstrip("\r\n")
        if not raw.strip():
            return None

        is_word_form = raw.startswith("  ")
        content = raw.strip()
        parts = content.split(maxsplit=1)
        prefix = f"line {line_number}: " if line_number is not None else ""
        if len(parts) != 2:
            raise VesumParseError(
                f"{prefix}expected VESUM visual row 'word morphology'"
            )
        form, morphology = parts

        if not is_word_form:
            self._current_lemma = _build_lemma(
                form,
                morphology,
                self._lexicon_id,
            )
        elif self._current_lemma is None:
            raise VesumParseError(
                f"{prefix}word-form row appeared before its lemma row"
            )

        lemma = self._current_lemma
        if lemma is None:
            raise VesumParseError(f"{prefix}could not resolve VESUM lemma")

        return VesumRecord(
            lemma=lemma,
            word_form=_build_word_form(lemma, form, morphology),
        )
