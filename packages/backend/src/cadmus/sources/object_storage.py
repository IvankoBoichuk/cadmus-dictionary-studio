"""Application-owned object-storage contract."""

from typing import BinaryIO, Protocol


class ObjectNotFoundError(Exception):
    """Raised when an object key does not exist in the configured bucket."""


class ObjectStorage(Protocol):
    """Stream binary source material without exposing an S3 provider SDK."""

    def upload(
        self,
        key: str,
        source: BinaryIO,
        length: int,
        content_type: str,
    ) -> None:
        """Store exactly ``length`` bytes from ``source`` under ``key``."""
        ...

    def download(self, key: str, destination: BinaryIO) -> None:
        """Stream the object at ``key`` into ``destination``."""
        ...

    def delete(self, key: str) -> None:
        """Delete the object at ``key``; deleting a missing key is idempotent."""
        ...
