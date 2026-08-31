"""One-shot CLI for importing a pinned VESUM dict_corp_lt.txt snapshot."""

import argparse
import hashlib
from pathlib import Path

from cadmus.config import Settings
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.reference_lexicon import (
    create_reference_lexicon_unit_of_work_factory,
)
from cadmus.reference_lexicon import VesumImportService


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import VESUM out/dict_corp_lt.txt into the Cadmus reference cache"
    )
    parser.add_argument("file", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source-commit")
    return parser


def main() -> None:
    args = _parser().parse_args()
    path: Path = args.file
    if not path.is_file():
        raise SystemExit(f"VESUM file does not exist: {path}")

    settings = Settings()
    engine = create_database_engine(settings)
    service = VesumImportService(create_reference_lexicon_unit_of_work_factory(engine))

    with path.open("r", encoding="utf-8") as lines:
        summary = service.import_lines(
            lines,
            version=args.version,
            source_commit=args.source_commit,
            checksum=_checksum(path),
        )

    print(
        "VESUM import complete: "
        f"version={summary.version} rows={summary.rows_imported} "
        f"blank={summary.blank_rows} lexicon_id={summary.lexicon_id}"
    )


if __name__ == "__main__":
    main()
