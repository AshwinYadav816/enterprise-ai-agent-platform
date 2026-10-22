"""Write the API contract for the frontend: uv run python scripts/export_openapi.py [out.json]

Needs no database or secrets: the schema is built from the routes alone.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Required setting (32+ chars), unused when exporting the schema
os.environ.setdefault("JWT_SECRET", "openapi-export-only-not-a-real-secret-0123456789")

from app.main import create_app  # noqa: E402


def main() -> None:
    out = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[1] / "openapi.json"
    )
    schema = create_app().openapi()
    out.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(schema['paths'])} paths)")


if __name__ == "__main__":
    main()
