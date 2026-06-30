# Machine Profile

A **machine profile** is the compatibility contract between FiberPath and a
target winder: a versioned, validated description of what a controller must
satisfy to run FiberPath's G-code. The planner consumes a profile rather than a
hardcoded dialect, so supporting a new controller is a data change, not a code
change.

This is the controller-side counterpart to the [`.wind` format](wind-format.md)
(which describes the *input*); see also the [Axis Mapping](axis-mapping.md) guide
for the logical-to-physical axis story.

## Schema

A profile is a JSON document validated against the `MachineProfile` model
(`fiberpath.config.MachineProfile`):

| Field | Type | Meaning |
| --- | --- | --- |
| `profileVersion` | string `1.x` | Schema version. Absent → `1.0`. |
| `id` | string | Stable slug, e.g. `marlin-xab`. |
| `name` | string | Human-readable name. |
| `controller` | string | Firmware family, e.g. `marlin`. |
| `units` | `mm` | Coordinate units. FiberPath emits mm only. |
| `feedMode` | `G94` | Feed-rate mode (units per minute). |
| `axisMapping` | object | `carriage` / `mandrel` / `deliveryHead` → G-code axis letters (each a distinct single uppercase letter). |
| `requiredGcodes` | string[] | Opcodes the planner emits (each a `G`/`M` code); a compatible controller must support all. |

The bundled canonical profile is `marlin-xab`
(`fiberpath/profiles/marlin_xab.json`):

```json
{
  "profileVersion": "1.0",
  "id": "marlin-xab",
  "name": "Marlin (X/A/B standard)",
  "controller": "marlin",
  "units": "mm",
  "feedMode": "G94",
  "axisMapping": { "carriage": "X", "mandrel": "A", "deliveryHead": "B" },
  "requiredGcodes": ["G0", "G21", "G90", "G92", "G94"]
}
```

## Compatibility requirements

A controller is compatible with this profile if it:

- **MUST** support every opcode in `requiredGcodes`. Each program begins with a
  modal preamble — `G21` (mm units), `G90` (absolute positioning), `G94` (feed
  rate in units per minute) — followed by motion via `G0` and `G92` (set
  position). Emitting the preamble makes the program self-describing rather than
  dependent on the controller's power-on modal state.
- **MUST** drive the carriage on the `axisMapping.carriage` axis as a linear axis
  (mm) and the mandrel/delivery-head on their mapped axes as rotational axes
  (degrees).

## Versioning

`profileVersion` follows the same policy as the `.wind` `schemaVersion`: additive
`1.x` revisions stay backward-compatible and validate against the same model; an
incompatible major (`2.0`+) is rejected. Bump the minor for additive fields.

## Using a profile

The planner defaults to the bundled `marlin-xab` profile. Pass a different one
explicitly:

```python
from fiberpath.config import MachineProfile, load_machine_profile
from fiberpath.planning import PlanOptions, plan_wind

profile = load_machine_profile("my-winder.machine.json")
result = plan_wind(definition, PlanOptions(profile=profile))
```

The CLI, API, and GUI export paths all use the default profile; no flag is
required for standard Marlin X/A/B winders.
