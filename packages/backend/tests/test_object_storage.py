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


def test_delete_prefix_bulk_removes_every_listed_object() -> None:
    client = Mock(spec=Minio)
    client.list_objects.return_value = [
        Mock(object_name="sources/dict-1/pages/00000.png"),
        Mock(object_name="sources/dict-1/pages/00001.png"),
    ]
    client.remove_objects.return_value = iter([])
    storage = MinioObjectStorage(client, "source-artifacts")

    storage.delete_prefix("sources/dict-1/pages/")

    client.list_objects.assert_called_once_with(
        "source-artifacts", prefix="sources/dict-1/pages/", recursive=True
    )
    bucket, delete_requests = client.remove_objects.call_args.args
    assert bucket == "source-artifacts"
    assert [request.name for request in delete_requests] == [
        "sources/dict-1/pages/00000.png",
        "sources/dict-1/pages/00001.png",
    ]


def test_delete_prefix_is_a_no_op_for_an_empty_prefix() -> None:
    client = Mock(spec=Minio)
    client.list_objects.return_value = []
    client.remove_objects.return_value = iter([])
    storage = MinioObjectStorage(client, "source-artifacts")

    storage.delete_prefix("sources/missing/pages/")

    bucket, delete_requests = client.remove_objects.call_args.args
    assert bucket == "source-artifacts"
    assert list(delete_requests) == []


def test_delete_prefix_raises_when_the_bulk_delete_reports_errors() -> None:
    client = Mock(spec=Minio)
    client.list_objects.return_value = [Mock(object_name="sources/dict-1/pages/x.png")]
    client.remove_objects.return_value = iter([Mock()])
    storage = MinioObjectStorage(client, "source-artifacts")

    with pytest.raises(RuntimeError):
        storage.delete_prefix("sources/dict-1/pages/")


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
