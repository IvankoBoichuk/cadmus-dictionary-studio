"""Real S3-compatible storage contract test against isolated MinIO."""

from io import BytesIO
from pathlib import Path
from uuid import uuid4

import pytest
from cadmus.config import Settings
from cadmus.infrastructure.object_storage import create_object_storage
from cadmus.sources import ObjectNotFoundError

pytestmark = pytest.mark.integration


def test_fixture_can_be_uploaded_read_and_deleted() -> None:
    fixture = Path("fixtures/object-storage/round-trip.txt").read_bytes()
    key = f"integration/{uuid4()}/round-trip.txt"
    storage = create_object_storage(Settings())

    try:
        storage.upload(key, BytesIO(fixture), len(fixture), "text/plain")
        downloaded = BytesIO()
        storage.download(key, downloaded)
        assert downloaded.getvalue() == fixture
    finally:
        storage.delete(key)

    with pytest.raises(ObjectNotFoundError):
        storage.download(key, BytesIO())
