#!/usr/bin/env python3
"""Export the FiberPath API's OpenAPI spec to a stable, committed artifact.

The output (`fiberpath_gui/openapi.json`) is the codegen input for the typed
TypeScript client. It is written deterministically (sorted keys, fixed
formatting) and the `info.version` is normalised to a placeholder so the
artifact — and therefore the generated client and the CI drift gate — only
change when the API *shape* changes, not on every release version bump.

The emitted spec reflects the installed FastAPI/Pydantic versions, so a
dependency bump that changes OpenAPI emission will (correctly) require
regenerating and committing this artifact via ``npm run api:generate``.
"""

from __future__ import annotations

import json
from pathlib import Path

from fiberpath_api.main import create_app

# Placeholder so a release version bump does not churn the spec/client/gate.
# The real, served spec at /openapi.json still reports the package version.
_NORMALISED_VERSION = "0"


def build_spec() -> dict[str, object]:
    spec = create_app().openapi()
    info = spec.get("info")
    if isinstance(info, dict):
        info["version"] = _NORMALISED_VERSION
    return spec


def main() -> None:
    output_path = Path(__file__).resolve().parent.parent / "fiberpath_gui" / "openapi.json"
    text = json.dumps(build_spec(), indent=2, sort_keys=True) + "\n"
    output_path.write_text(text, encoding="utf-8")
    print(f"✓ Exported OpenAPI spec: {output_path}")


if __name__ == "__main__":
    main()
