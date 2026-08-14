from io import BytesIO
from unittest.mock import Mock, patch

import pytest
from cadmus.config import Settings
from cadmus.infrastructure.object_storage import (
    MinioObjectStorage,
    initialize_object_storage,
)
from cadmus.sources import ObjectNotFoundError, ObjectStorage
from minio import Minio
from minio.error import S3Error


class Response(BytesIO):
    def __init__(self, value: bytes) -> None:
        super().__init__(value)
        self.released = False

    def release_conn(self) -> None:
        self.released = True


def test_minio_adapter_satisfies_application_contract() -> None:
    client = Mock(spec=Minio)
    storage: ObjectStorage = MinioObjectStorage(client, "source-artifacts")
    source = BytesIO(b"source fixture")

    storage.upload("fixtures/source.txt", source, 14, "text/plain")

    client.put_object.assert_called_once_with(
        "source-artifacts",
        "fixtures/source.txt",
        source,
        14,
        content_type="text/plain",
    )


def test_download_streams_content_and_releases_connection() -> None:
    response = Response(b"source fixture")
    client = Mock(spec=Minio)
    client.get_object.return_value = response
    storage = MinioObjectStorage(client, "source-artifacts")
    destination = BytesIO()

    storage.download("fixtures/source.txt", destination)

    assert destination.getvalue() == b"source fixture"
    assert response.closed
    assert response.released


def test_delete_is_delegated_to_configured_bucket() -> None:
    client = Mock(spec=Minio)
    storage = MinioObjectStorage(client, "source-artifacts")

    storage.delete("fixtures/source.txt")

    client.remove_object.assert_called_once_with(
        "source-artifacts", "fixtures/source.txt"
    )


def test_missing_object_is_translated_to_application_error() -> None:
    client = Mock(spec=Minio)
    client.get_object.side_effect = S3Error(
        Mock(),
        "NoSuchKey",
        "missing",
        "/source-artifacts/missing.txt",
        "request-id",
        "host-id",
    )
    storage = MinioObjectStorage(client, "source-artifacts")

    with pytest.raises(ObjectNotFoundError):
        storage.download("missing.txt", BytesIO())


@patch("cadmus.infrastructure.object_storage.Minio")
def test_bucket_initialization_is_idempotent(minio_class: Mock) -> None:
    client = minio_class.return_value
    client.bucket_exists.side_effect = [False, True]
    settings = Settings(object_storage_bucket="source-artifacts")

    initialize_object_storage(settings)
    initialize_object_storage(settings)

    assert client.bucket_exists.call_count == 2
    client.make_bucket.assert_called_once_with("source-artifacts")
