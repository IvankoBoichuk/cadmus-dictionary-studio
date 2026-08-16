"""S3-compatible object-storage adapter implemented with the MinIO SDK."""

from shutil import copyfileobj
from typing import BinaryIO

from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from cadmus.config import Settings
from cadmus.sources import ObjectNotFoundError


class MinioObjectStorage:
    """Store binary streams in one configured S3-compatible bucket."""

    def __init__(self, client: Minio, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    def upload(
        self,
        key: str,
        source: BinaryIO,
        length: int,
        content_type: str,
    ) -> None:
        """Upload a stream without buffering the complete object in memory."""
        self._client.put_object(
            self._bucket,
            key,
            source,
            length,
            content_type=content_type,
        )

    def download(self, key: str, destination: BinaryIO) -> None:
        """Download a stream and always release its HTTP connection."""
        try:
            response = self._client.get_object(self._bucket, key)
        except S3Error as error:
            if error.code in {"NoSuchKey", "NoSuchObject"}:
                raise ObjectNotFoundError(key) from error
            raise

        try:
            copyfileobj(response, destination)
        finally:
            response.close()
            response.release_conn()

    def delete(self, key: str) -> None:
        """Delete a key using S3's idempotent delete behavior."""
        self._client.remove_object(self._bucket, key)

    def delete_prefix(self, prefix: str) -> None:
        """List and bulk-delete every object under ``prefix``."""
        objects = self._client.list_objects(self._bucket, prefix=prefix, recursive=True)
        delete_requests = (
            DeleteObject(obj.object_name) for obj in objects if obj.object_name
        )
        errors = list(self._client.remove_objects(self._bucket, delete_requests))
        if errors:
            raise RuntimeError(
                f"failed to delete {len(errors)} object(s) under prefix {prefix!r}: "
                f"{errors[0]}"
            )


def create_object_storage(settings: Settings) -> MinioObjectStorage:
    """Build the S3 adapter from environment-backed settings."""
    client = Minio(
        settings.object_storage_endpoint,
        access_key=settings.object_storage_access_key.get_secret_value(),
        secret_key=settings.object_storage_secret_key.get_secret_value(),
        secure=settings.object_storage_secure,
    )
    return MinioObjectStorage(client, settings.object_storage_bucket)


def initialize_object_storage(settings: Settings) -> None:
    """Create the configured bucket once; repeated initialization is safe."""
    client = Minio(
        settings.object_storage_endpoint,
        access_key=settings.object_storage_access_key.get_secret_value(),
        secret_key=settings.object_storage_secret_key.get_secret_value(),
        secure=settings.object_storage_secure,
    )
    if not client.bucket_exists(settings.object_storage_bucket):
        client.make_bucket(settings.object_storage_bucket)
