"""One-shot Compose entrypoint for object-storage bucket initialization."""

from cadmus.config import Settings
from cadmus.infrastructure.object_storage import initialize_object_storage


def main() -> None:
    """Initialize the configured bucket from environment settings."""
    initialize_object_storage(Settings())


if __name__ == "__main__":
    main()
