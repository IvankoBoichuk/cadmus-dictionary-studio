import pytest
from cadmus_worker.import_vesum import (
    _normalize_release_tag,
    _release_asset_from_payload,
)


def test_normalize_release_tag_accepts_version_or_tag() -> None:
    assert _normalize_release_tag("6.8.5") == "v6.8.5"
    assert _normalize_release_tag("v6.8.5") == "v6.8.5"


def test_release_asset_uses_github_digest() -> None:
    asset = _release_asset_from_payload(
        {
            "tag_name": "v6.8.5",
            "assets": [
                {
                    "name": "dict_corp_vis.txt.bz2",
                    "browser_download_url": (
                        "https://github.com/brown-uk/dict_uk/releases/"
                        "download/v6.8.5/dict_corp_vis.txt.bz2"
                    ),
                    "digest": (
                        "sha256:"
                        "e33803783ac138e6f3af2cf0e9428ba146c0ecfda7f5c41fe83ae00c7af24be9"
                    ),
                }
            ],
        }
    )

    assert asset.version == "6.8.5"
    assert asset.tag == "v6.8.5"
    assert asset.sha256 == (
        "e33803783ac138e6f3af2cf0e9428ba146c0ecfda7f5c41fe83ae00c7af24be9"
    )


def test_release_asset_requires_sha256_digest() -> None:
    with pytest.raises(RuntimeError, match="SHA-256"):
        _release_asset_from_payload(
            {
                "tag_name": "v6.8.5",
                "assets": [
                    {
                        "name": "dict_corp_vis.txt.bz2",
                        "browser_download_url": "https://example.test/vis.bz2",
                        "digest": None,
                    }
                ],
            }
        )
