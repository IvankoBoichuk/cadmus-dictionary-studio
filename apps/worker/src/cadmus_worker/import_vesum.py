"""One-shot importer for a pinned VESUM GitHub release asset."""

import argparse
import bz2
import hashlib
import json
from dataclasses import dataclass
from io import TextIOWrapper
from tempfile import TemporaryFile
from typing import BinaryIO, TypedDict, cast
from urllib.parse import quote
from urllib.request import Request, urlopen

from cadmus.config import Settings
from cadmus.infrastructure.database import create_database_engine
from cadmus.infrastructure.reference_lexicon import (
    create_reference_lexicon_unit_of_work_factory,
)
from cadmus.reference_lexicon import VESUM_RELEASE_ASSET_NAME, VesumImportService

_GITHUB_RELEASE_API = "https://api.github.com/repos/brown-uk/dict_uk/releases/tags"
_USER_AGENT = "cadmus-dictionary-studio/vesum-import"
_DOWNLOAD_CHUNK_BYTES = 1024 * 1024


class _ReleaseAssetPayload(TypedDict):
    name: str
    browser_download_url: str
    digest: str | None


class _ReleasePayload(TypedDict):
    tag_name: str
    assets: list[_ReleaseAssetPayload]


@dataclass(frozen=True)
class VesumReleaseAsset:
    tag: str
    version: str
    download_url: str
    sha256: str


def _normalize_release_tag(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("VESUM release is required")
    return stripped if stripped.startswith("v") else f"v{stripped}"


def _release_asset_from_payload(payload: _ReleasePayload) -> VesumReleaseAsset:
    tag = _normalize_release_tag(payload["tag_name"])
    for asset in payload["assets"]:
        if asset["name"] != VESUM_RELEASE_ASSET_NAME:
            continue
        digest = asset.get("digest")
        if digest is None or not digest.startswith("sha256:"):
            raise RuntimeError("VESUM release asset has no SHA-256 digest")
        sha256 = digest.removeprefix("sha256:").lower()
        if len(sha256) != 64:
            raise RuntimeError("VESUM release asset has an invalid SHA-256 digest")
        return VesumReleaseAsset(
            tag=tag,
            version=tag.removeprefix("v"),
            download_url=asset["browser_download_url"],
            sha256=sha256,
        )
    raise RuntimeError(
        f"VESUM release does not contain {VESUM_RELEASE_ASSET_NAME}"
    )


def _resolve_release_asset(release: str) -> VesumReleaseAsset:
    tag = _normalize_release_tag(release)
    request = Request(
        f"{_GITHUB_RELEASE_API}/{quote(tag)}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urlopen(request, timeout=60) as response:
        payload = cast(
            _ReleasePayload,
            json.loads(response.read().decode("utf-8")),
        )
    return _release_asset_from_payload(payload)


def _download_verified_asset(asset: VesumReleaseAsset) -> BinaryIO:
    compressed = TemporaryFile(mode="w+b")
    digest = hashlib.sha256()
    try:
        request = Request(
            asset.download_url,
            headers={"User-Agent": _USER_AGENT},
        )
        with urlopen(request, timeout=120) as response:
            while chunk := response.read(_DOWNLOAD_CHUNK_BYTES):
                compressed.write(chunk)
                digest.update(chunk)

        actual = digest.hexdigest()
        if actual != asset.sha256:
            raise RuntimeError(
                "VESUM release asset checksum mismatch: "
                f"expected {asset.sha256}, got {actual}"
            )
        compressed.seek(0)
        return compressed
    except BaseException:
        compressed.close()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download and import VESUM dict_corp_vis.txt.bz2 from a pinned "
            "GitHub release"
        )
    )
    parser.add_argument(
        "--release",
        required=True,
        help="VESUM release tag or version, e.g. v6.8.5 or 6.8.5",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    asset = _resolve_release_asset(args.release)

    settings = Settings()
    engine = create_database_engine(settings)
    service = VesumImportService(
        create_reference_lexicon_unit_of_work_factory(engine)
    )

    compressed = _download_verified_asset(asset)
    try:
        with bz2.BZ2File(compressed, mode="rb") as decompressed:
            with TextIOWrapper(decompressed, encoding="utf-8") as lines:
                summary = service.import_visual_lines(
                    lines,
                    version=asset.version,
                    checksum=asset.sha256,
                    source_url=asset.download_url,
                )
    finally:
        if not compressed.closed:
            compressed.close()

    print(
        "VESUM import complete: "
        f"version={summary.version} rows={summary.rows_imported} "
        f"blank={summary.blank_rows} sha256={asset.sha256} "
        f"lexicon_id={summary.lexicon_id}"
    )


if __name__ == "__main__":
    main()
