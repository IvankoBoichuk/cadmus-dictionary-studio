"""Use cases for versioned external lexical reference data."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from cadmus.reference_lexicon.domain import (
    VESUM_CODE,
    VESUM_LANGUAGE_CODE,
    VESUM_LICENSE_ID,
    VESUM_NAME,
    VESUM_SOURCE_URL,
    ReferenceLemma,
    ReferenceLemmaMatch,
    ReferenceLexicon,
    VesumParseError,
    VesumRecord,
    normalize_ukrainian_text,
    parse_vesum_line,
    reference_lexicon_id,
)
from cadmus.reference_lexicon.ports import ReferenceLexiconUnitOfWorkFactory


class ReferenceLexiconNotFoundError(LookupError):
    """Raised when the requested reference provider has not been imported."""


class ReferenceLemmaNotFoundError(LookupError):
    """Raised when a reference lemma does not exist or is inactive."""


@dataclass(frozen=True)
class VesumImportSummary:
    """Counters for one atomic VESUM import."""

    lexicon_id: UUID
    version: str
    rows_read: int
    rows_imported: int
    blank_rows: int


class ReferenceLexiconQueryService:
    """Read-only lookup against the latest successfully imported reference data."""

    def __init__(self, unit_of_work_factory: ReferenceLexiconUnitOfWorkFactory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def get_lexicon(self, code: str) -> ReferenceLexicon:
        with self._unit_of_work_factory() as unit_of_work:
            lexicon = unit_of_work.reference_lexicon.get_lexicon_by_code(code)
        if lexicon is None or not lexicon.is_active:
            raise ReferenceLexiconNotFoundError(code)
        return lexicon

    def get_lemma(self, lemma_id: UUID) -> ReferenceLemma:
        with self._unit_of_work_factory() as unit_of_work:
            lemma = unit_of_work.reference_lexicon.get_lemma(lemma_id)
        if lemma is None or not lemma.is_active:
            raise ReferenceLemmaNotFoundError(str(lemma_id))
        return lemma

    def search(
        self,
        code: str,
        query: str,
        *,
        standard_only: bool = True,
        limit: int = 20,
    ) -> list[ReferenceLemmaMatch]:
        lexicon = self.get_lexicon(code)
        normalized_query = normalize_ukrainian_text(query)
        if not normalized_query:
            return []
        safe_limit = max(1, min(limit, 100))
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.reference_lexicon.search_lemmas(
                lexicon_id=lexicon.id,
                query=normalized_query,
                standard_only=standard_only,
                limit=safe_limit,
            )


class VesumImportService:
    """Atomically replace the active VESUM snapshot from dict_corp_lt.txt.

    Old rows are deactivated rather than deleted so already-confirmed Cadmus
    links retain referential integrity across upstream versions. Deterministic
    UUIDs reactivate unchanged lemmas and forms on the next import.
    """

    def __init__(
        self,
        unit_of_work_factory: ReferenceLexiconUnitOfWorkFactory,
        *,
        batch_size: int = 5_000,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self._unit_of_work_factory = unit_of_work_factory
        self._batch_size = batch_size

    def import_lines(
        self,
        lines: Iterable[str],
        *,
        version: str,
        checksum: str,
        source_commit: str | None = None,
        imported_at: datetime | None = None,
    ) -> VesumImportSummary:
        if not version.strip():
            raise ValueError("VESUM version is required")
        if not checksum.strip():
            raise ValueError("source checksum is required")

        lexicon_id = reference_lexicon_id(VESUM_CODE)
        snapshot = ReferenceLexicon(
            id=lexicon_id,
            code=VESUM_CODE,
            name=VESUM_NAME,
            language_code=VESUM_LANGUAGE_CODE,
            version=version.strip(),
            source_url=VESUM_SOURCE_URL,
            license_id=VESUM_LICENSE_ID,
            source_commit=source_commit.strip() if source_commit else None,
            checksum=checksum.strip().lower(),
            imported_at=imported_at or datetime.now(UTC),
            is_active=True,
        )

        rows_read = 0
        rows_imported = 0
        blank_rows = 0
        batch: list[VesumRecord] = []

        with self._unit_of_work_factory() as unit_of_work:
            unit_of_work.reference_lexicon.upsert_lexicon(snapshot)
            unit_of_work.reference_lexicon.deactivate_content(lexicon_id)

            for line_number, line in enumerate(lines, start=1):
                rows_read += 1
                try:
                    record = parse_vesum_line(line, lexicon_id)
                except VesumParseError as error:
                    raise VesumParseError(f"line {line_number}: {error}") from error
                if record is None:
                    blank_rows += 1
                    continue
                batch.append(record)
                rows_imported += 1
                if len(batch) >= self._batch_size:
                    unit_of_work.reference_lexicon.upsert_records(batch)
                    batch.clear()

            if batch:
                unit_of_work.reference_lexicon.upsert_records(batch)
            unit_of_work.commit()

        return VesumImportSummary(
            lexicon_id=lexicon_id,
            version=snapshot.version,
            rows_read=rows_read,
            rows_imported=rows_imported,
            blank_rows=blank_rows,
        )
