#!/usr/bin/env python3
"""
Generate JSON Schema from Pydantic models for the .wind file format.
This ensures GUI and CLI stay in sync.
"""

import json
from pathlib import Path

from fiberpath.config.schemas import WindDefinition


def main() -> None:
    # Generate schema
    schema = WindDefinition.model_json_schema(mode="serialization")

    # Add metadata. The $id is the canonical, versioned identifier for the open
    # .wind format (see #141). It is MAJOR-only: additive 1.x revisions (tracked by
    # the `schemaVersion` field) validate against this same schema and keep this
    # $id; bump the path only on a breaking (major) format change (.../wind/2/...).
    # Keep pydantic's title ("WindDefinition") so the generated TS root type name
    # stays stable for the GUI consumers; the $id carries the format identity.
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema["$id"] = "https://fiberpath.org/schemas/wind/1/wind.schema.json"
    schema["description"] = "Schema for FiberPath filament winding pattern definitions"

    # schemaVersion is a native field on WindDefinition (default "1.0", pattern
    # ^1\.\d+$), so it is already present in the generated schema: absent is
    # treated as 1.0, any 1.x minor is accepted, and an incompatible major
    # (2.0+) is rejected. It is intentionally not `required` for backwards compat.

    # Output path
    output_path = Path(__file__).parent.parent / "fiberpath_gui" / "schemas" / "wind-schema.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write deterministically (sorted keys + trailing newline) so the committed
    # artifact only changes on real schema changes and a CI drift gate is stable.
    output_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    schema_version = WindDefinition.model_fields["schema_version"].default
    print(f"✓ Generated schema: {output_path}")
    print(f"  Default schemaVersion: {schema_version}")
    print(f"  Definitions: {len(schema.get('$defs', {}))}")


if __name__ == "__main__":
    main()
