"""Export the application OpenAPI document for deterministic client codegen."""

import json
import sys
from pathlib import Path

from cadmus_api.main import create_app


def main() -> None:
    """Write the current application contract to the requested JSON file."""
    output = Path(sys.argv[1])
    output.write_text(
        json.dumps(create_app().openapi(), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
