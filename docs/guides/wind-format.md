# `.wind` Open Winding-Program Format — Specification

This is the **normative specification** for `.wind`, an open, JSON-based interchange
format that defines filament-winding patterns for composite manufacturing: mandrel
geometry, tow material properties, and a sequence of winding layers. It is intended
for any tool that produces or consumes winding programs, not only FiberPath.

| | |
|---|---|
| **Status** | Normative, stable within major version 1 |
| **Current version** | `1.1` (the `schemaVersion` field; see [changelog](#format-changelog)) |
| **Media type** | `application/vnd.fiberpath.wind+json` (conventional; not IANA-registered) |
| **Canonical JSON Schema `$id`** | `https://fiberpath.org/schemas/wind/1/wind.schema.json` (major-versioned) |
| **Customary extension** | `.wind` |

The format is **machine-checkable**: the canonical JSON Schema above is generated from
the [Pydantic](https://docs.pydantic.dev/) models in `fiberpath/config/schemas.py` and is
the authoritative structural contract. This document is normative for the semantics and
the conformance requirements that the schema alone cannot express.

## Conventions

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**, and
**MAY** in this document are to be interpreted as described in
[RFC 2119](https://www.rfc-editor.org/rfc/rfc2119).

## Conformance

A **conforming document** is a JSON document that validates against the canonical JSON
Schema for its major version and additionally satisfies the semantic rules in
[Validation Rules](#validation-rules).

A **conforming producer** (writer):

- MUST emit a document that validates against the canonical schema;
- SHOULD set `schemaVersion` to the minor version whose fields it uses;
- MUST NOT rely on field ordering for meaning.

A **conforming consumer** (reader):

- MUST accept any document whose `schemaVersion` shares its supported **major** version,
  including unknown **minor** versions (forward compatibility within the major);
- MUST treat an absent `schemaVersion` as `1.0`;
- MUST reject a document whose `schemaVersion` major exceeds the one it supports;
- SHOULD be **tolerant**: ignore unknown object members rather than failing, so that
  additive minor revisions remain readable.

## Schema version and compatibility policy

Current schema version: **1.1**.

The format evolves **additively within a major version**: a minor revision MAY add
optional fields or layer/surface types, MUST NOT remove or repurpose existing ones, and
MUST NOT change the meaning of an existing document. Because revisions are additive, the
canonical `$id` is **major-only** (`.../wind/1/...`) — every 1.x document validates
against it, and the `schemaVersion` field carries the minor. A **breaking** change bumps
the major and mints a new `$id` (`.../wind/2/...`). See [the changelog](#format-changelog).

## File Structure

A `.wind` file is a JSON document with the following top-level structure:

```json
{
  "schemaVersion": "1.0",
  "mandrelParameters": { ... },
  "towParameters": { ... },
  "defaultFeedRate": 2000,
  "layers": [ ... ]
}
```

## Top-Level Fields

### `schemaVersion` (optional)

- **Type**: `string`
- **Default**: `"1.0"`
- **Description**: Version of the `.wind` file format schema. Allows for future format evolution and backwards compatibility detection.

### `mandrelParameters` (required)

- **Type**: `object`
- **Description**: Physical parameters of the mandrel (the part being wound)

**Fields**:

- `diameter` (required): Mandrel outer diameter in mm (must be > 0). For a cone, this is the **large end** at `z = 0`.
- `windLength` (required): Length of the winding area in mm (must be > 0)
- `endDiameter` (optional, **1.1+**): Outer diameter in mm at the far end (`z = windLength`). When set **below** `diameter`, the mandrel is a reducing **cone (frustum)**; omit it (or set it equal to `diameter`) for a cylinder.

**Example (cylinder)**:

```json
"mandrelParameters": {
  "diameter": 150,
  "windLength": 800
}
```

**Example (cone / frustum)**:

```json
"mandrelParameters": {
  "diameter": 98,
  "windLength": 120,
  "endDiameter": 54
}
```

#### Cones (developable surfaces)

A cone, like a cylinder, is **developable**: it unrolls to a flat sector, so a
winding path is closed-form (no ODE/friction solver). Helical layers on a cone
are wound as **geodesics** (Clairaut's relation `r · sin α = const`): the wind
angle is **anchored at the large end** (`diameter`, `z = 0`) and the achieved
fiber angle increases toward the small end. Current limits:

- **Reducing frustum only** — `endDiameter` must be `< diameter` (mount the large end at `z = 0`).
- **Helical (and skip) layers only** — a hoop layer on a cone is rejected (a 90° hoop is not a geodesic).
- **Reachability** — a wind angle too steep for the taper is rejected: the geodesic must be able to reach the small end (`diameter · sin α ≤ endDiameter`).

### `towParameters` (required)

- **Type**: `object`
- **Description**: Material properties of the fiber tow (carbon fiber, fiberglass, etc.)

**Fields**:

- `width` (required): Tow width in mm (must be > 0)
- `thickness` (required): Tow thickness in mm (must be > 0)

**Example**:

```json
"towParameters": {
  "width": 12,
  "thickness": 0.25
}
```

### `defaultFeedRate` (required)

- **Type**: `number`
- **Description**: Default feed rate for winding operations in mm/min (must be > 0)
- **Example**: `2000`

### `layers` (required)

- **Type**: `array`
- **Description**: Sequential list of winding layers to apply. Each layer is one of three types: `hoop`, `helical`, or `skip`.

## Layer Types

Layers are discriminated by the `windType` field. Each layer type has specific required and optional fields.

### Hoop Layer

A hoop layer winds perpendicular to the mandrel axis (90° angle). Used for circumferential reinforcement.

**Required Fields**:

- `windType`: Must be `"hoop"`

**Optional Fields**:

- `terminal` (default: `false`): Whether this is a terminal layer (first or last layer with special handling)

**Example**:

```json
{
  "windType": "hoop",
  "terminal": false
}
```

**Use Cases**:

- Pressure vessel end caps
- Circumferential reinforcement
- First/last layers of a winding pattern

### Helical Layer

A helical layer winds at a specified angle, creating a spiral pattern around the mandrel. This is the most complex layer type with geometric constraints.

**Required Fields**:

- `windType`: Must be `"helical"`
- `windAngle`: Wind angle in degrees (0° < angle ≤ 90°)
- `patternNumber`: Number of circuits in the pattern (integer ≥ 1)
- `skipIndex`: Skip index for pattern generation (integer ≥ 1, must be coprime with `patternNumber`)
- `lockDegrees`: Lock rotation in degrees (must be > 0). When `patternNumber > 1`, this value must also satisfy the coverage compatibility conditions described under **Geometric Constraints** below.
- `leadInMM`: Lead-in distance in mm (must be > 0)
- `leadOutDegrees`: Lead-out rotation in degrees (must be > 0)

**Optional Fields**:

- `skipInitialNearLock` (default: `false`): Whether to suppress the initial near-lock mandrel pre-rotation at the start of this layer.

  Before the first circuit of a helical layer, the planner normally performs an *initial near-lock* move: it rotates the mandrel by `lockDegrees` and re-zeros the rotational position there. This ensures the first circuit starts from the same rotational reference point that all subsequent circuits establish at their turn-around. Without it, the first circuit would begin from whatever position the mandrel is currently at, causing the first and remaining circuits to be rotationally inconsistent.

  - `false` (default): Perform the initial near-lock move. Use this for standalone layers or the first helical layer in a sequence.
  - `true`: Skip the initial near-lock move. Use this when the preceding layer (e.g., a `SkipLayer` or prior helical layer) has already left the mandrel at the correct rotational reference, avoiding a redundant over-rotation.

**Geometric Constraints**:

1. **Coprime Check**: `skipIndex` and `patternNumber` must be coprime (GCD = 1) to ensure full coverage
2. **Circuit Divisibility**: The calculated number of circuits must be evenly divisible by `patternNumber` for valid pattern generation
3. **Wind Angle**: Must be between 0° (exclusive) and 90° (inclusive)
4. **lockDegrees Coverage Compatibility** (when `patternNumber > 1`): The net mandrel advance per complete circuit is `(2 × lockDegrees) mod 360°`. Two conditions must hold:
   - *Condition 1 — divisibility*: `(2 × lockDegrees) mod (360 / patternNumber)` must equal 0. Equivalently, `lockDegrees` must be a multiple of `180 / patternNumber` (e.g. for `patternNumber: 3` → multiples of 60°; for `patternNumber: 4` → multiples of 45°).
   - *Condition 2 — non-aliasing*: The resulting intra-pattern slot stride must be coprime with `patternNumber`. This prevents all in-pattern circuits from aliasing onto the same groove even when Condition 1 is satisfied.
   - The validator reports the nearest valid `lockDegrees` values when either condition fails.

**Parameter Meaning (Quick Guide)**:

- **`windAngle`**: Fiber direction relative to mandrel axis. This is the **normative** wind-angle convention across FiberPath — measured from the mandrel axis (the meridian), with `0°` axial and `90°` hoop. A hoop layer is the `windAngle → 90°` limit of a helical layer.
- **`patternNumber`**: Number of helical bands in the repeating pattern
- **`skipIndex`**: Band-to-band stride each circuit; must be coprime with `patternNumber`
- **`lockDegrees`**: Additional mandrel rotation at each turn-around (lock) point. Controls the angular spacing between successive circuits — must be a multiple of `180 / patternNumber` (Condition 1) and produce a slot stride coprime with `patternNumber` (Condition 2). See Geometric Constraints above.
- **`leadInMM` / `leadOutDegrees`**: Entry and exit transition motions for smoother placement

**Example**:

```json
{
  "windType": "helical",
  "windAngle": 45,
  "patternNumber": 3,
  "skipIndex": 1,
  "lockDegrees": 540,
  "leadInMM": 5,
  "leadOutDegrees": 10,
  "skipInitialNearLock": false
}
```

**Common Issues**:

- If validation fails because circuits are not divisible by `patternNumber`, adjust either:
  - The wind angle (changes circuit count)
  - The pattern number (must divide evenly into circuit count)
  - The mandrel diameter or wind length
- If validation fails because `lockDegrees` is incompatible with `patternNumber`, the error message suggests the nearest valid values. As a rule: `lockDegrees` must be a multiple of `180 / patternNumber`. For three-band patterns (`patternNumber: 3`), use multiples of 60° such as 180°, 360°, or 540°.

**Use Cases**:

- Pressure vessel cylindrical sections
- Angled reinforcement (±45° for shear resistance)
- Angled helical reinforcement patterns

### Skip Layer

A skip layer rotates the mandrel without winding, allowing for pattern repositioning or creating gaps.

**Required Fields**:

- `windType`: Must be `"skip"`
- `mandrelRotation`: Rotation amount in degrees

**Example**:

```json
{
  "windType": "skip",
  "mandrelRotation": 180
}
```

**Use Cases**:

- Pattern alignment between layers
- Creating intentional gaps
- Repositioning between layers

## Validation Rules

The schema enforces the following validation rules:

### Type Validation

- All numeric fields must be numbers (integer or float as specified)
- Boolean fields must be `true` or `false`
- String fields must be strings
- Arrays must contain items of the correct type

### Range Validation

- All dimensions (diameter, windLength, width, thickness, etc.) must be **greater than zero** (exclusive minimum)
- Wind angles must be in the range (0°, 90°]
- Pattern numbers and skip indices must be positive integers

### Structural Validation

- All required fields must be present
- Layer discriminator (`windType`) must be one of: `"hoop"`, `"helical"`, `"skip"`
- Each layer type must include its required fields

### Geometric Validation (CLI)

The CLI performs additional validation beyond the schema:

- Coprime check for helical layers (`gcd(skipIndex, patternNumber) == 1`)
- Circuit divisibility check for helical patterns
- `lockDegrees` coverage compatibility check for helical layers with `patternNumber > 1` (two-condition check: divisibility and non-aliasing)
- Terminal layer placement rules
- Physical feasibility checks

## Schema Management

### Schema Generation

The JSON Schema is automatically generated from Pydantic models:

```bash
cd fiberpath_gui
npm run schema:generate
```

This command:

1. Runs `scripts/generate_schema.py` to extract schema from Python
2. Generates TypeScript types using `json-schema-to-typescript`
3. Updates `schemas/wind-schema.json` and `src/types/wind-schema.ts`

### Schema Location

- **JSON Schema**: `fiberpath_gui/schemas/wind-schema.json`
- **TypeScript Types**: `fiberpath_gui/src/types/wind-schema.ts`
- **Python Models**: `fiberpath/config/schemas.py`
- **Validation**: `fiberpath/config/validator.py`

### Backwards compatibility

The compatibility guarantees are normative and stated in
[Schema version and compatibility policy](#schema-version-and-compatibility-policy) and
[Conformance](#conformance): additive-only within a major version, tolerant readers,
absent `schemaVersion` treated as `1.0`. The changelog below records each minor.

### Format changelog

Additive-only within major version 1; tolerant readers ignore unknown fields, and
a missing `schemaVersion` is treated as `1.0`.

- **1.1** — added optional `mandrelParameters.endDiameter` for reducing **cones (frustums)**; helical layers on a cone are wound as geodesics. Files omitting `endDiameter` are unchanged 1.0 cylinders.
- **1.0** — initial schema: discriminated layer types (hoop / helical / skip) on a cylinder.

## Example Files

### Minimal Hoop Pattern

```json
{
  "schemaVersion": "1.0",
  "mandrelParameters": {
    "diameter": 150,
    "windLength": 800
  },
  "towParameters": {
    "width": 12,
    "thickness": 0.25
  },
  "defaultFeedRate": 2000,
  "layers": [
    {
      "windType": "hoop",
      "terminal": false
    }
  ]
}
```

### Multi-Layer Helical Pattern

```json
{
  "schemaVersion": "1.0",
  "mandrelParameters": {
    "diameter": 150,
    "windLength": 800
  },
  "towParameters": {
    "width": 12,
    "thickness": 0.25
  },
  "defaultFeedRate": 2000,
  "layers": [
    {
      "windType": "hoop",
      "terminal": false
    },
    {
      "windType": "helical",
      "windAngle": 45,
      "patternNumber": 3,
      "skipIndex": 1,
      "lockDegrees": 540,
      "leadInMM": 5,
      "leadOutDegrees": 10,
      "skipInitialNearLock": false
    },
    {
      "windType": "skip",
      "mandrelRotation": 180
    },
    {
      "windType": "helical",
      "windAngle": 45,
      "patternNumber": 3,
      "skipIndex": 1,
      "lockDegrees": 540,
      "leadInMM": 5,
      "leadOutDegrees": 10,
      "skipInitialNearLock": true
    },
    {
      "windType": "hoop",
      "terminal": true
    }
  ]
}
```

## Related Documentation

- **[Architecture](../architecture/overview.md)**: System design and component interaction
- **[API Documentation](../reference/api.md)**: REST API endpoints for validation and planning
- **[Concepts](../reference/concepts.md)**: Winding theory and geometric calculations

## Validation Tools

### CLI Validation

```bash
fiberpath validate input.wind
```

### GUI Validation

The GUI automatically validates `.wind` files:

- On file open (before loading into editor)
- Before planning (before sending to CLI)
- On save (before writing to disk)

Validation errors are displayed with specific field paths and messages.

### Python API

```python
from fiberpath.config.validator import validate_wind_definition
errors = validate_wind_definition(wind_dict)
if errors:
    for error in errors:
        print(f"Error in {error.field}: {error.message}")
```

## Future Enhancements

Potential additions to future schema versions:

- Custom layer strategies beyond hoop/helical/skip
- Advanced material properties (resin content, fiber density)
- Multi-tow configurations
- Temperature and cure profiles
- Process parameters (tension, speed profiles)

Changes will maintain backwards compatibility through the `schemaVersion` field.
