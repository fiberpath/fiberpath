# `.wind` File Format

The `.wind` file format is a JSON-based configuration file that defines filament winding patterns for composite manufacturing. It specifies mandrel geometry, tow material properties, and a sequence of winding layers.

## Schema Version

Current schema version: **1.0**

The schema is formally defined in JSON Schema format and validated using [Pydantic](https://docs.pydantic.dev/) models in the CLI backend.

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

- `diameter` (required): Mandrel outer diameter in mm (must be > 0)
- `windLength` (required): Length of the winding area in mm (must be > 0)

**Example**:

```json
"mandrelParameters": {
  "diameter": 150,
  "windLength": 800
}
```

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

### Backwards Compatibility

The `schemaVersion` field allows for future format evolution:

- Version `1.0`: Initial schema with discriminated layer types
- Future versions may add new layer types or optional fields
- The CLI maintains backwards compatibility by making `schemaVersion` optional

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
