# Axis System Architecture

This document provides a technical deep dive into FiberPath's axis mapping system, which separates planning logic from G-code output format.

## Design Philosophy

FiberPath uses a **logical-to-physical axis mapping** approach:

1. **Planner operates on logical axes:** Carriage, Mandrel, Delivery Head
2. **Dialect converts to physical axes:** Built-in output uses X/A/B; custom mappings are optional
3. **Planning logic remains unchanged:** Same algorithms work for all output formats

This design allows:

- Supporting multiple machine configurations without code duplication
- Easy addition of new dialects (FANUC, GRBL, custom controllers)
- Machine-independent layer strategies and calculations

## Logical Axes

The core planner (`fiberpath.planning`) uses three logical axes:

### Carriage Axis

- **Type:** Linear
- **Units:** Millimeters (mm)
- **Description:** Motion along the mandrel's longitudinal axis
- **Usage:** All axial positioning, lead-in/lead-out moves

### Mandrel Axis

- **Type:** Rotational
- **Units:** Degrees
- **Description:** Mandrel rotation for winding
- **Usage:** Hoop layer wraps, helical layer rotation component

### Delivery Head Axis

- **Type:** Rotational
- **Units:** Degrees
- **Description:** Delivery head rotation for tow feed
- **Usage:** Pattern synchronization, tow angle control

## Physical Mapping

The `AxisMapping` class (in `fiberpath/gcode/dialects.py`) maps logical to physical:

```python
class AxisMapping:
    carriage: str  # Physical axis name (e.g., "X")
    mandrel: str  # Physical axis name (e.g., "A" or "Y")
    delivery: str  # Physical axis name (e.g., "B" or "Z")
    is_rotational_mandrel: bool
    is_rotational_delivery: bool
```

### XAB Mapping (Standard)

```python
MARLIN_XAB_STANDARD = AxisMapping(
    carriage="X", mandrel="A", delivery="B", is_rotational_mandrel=True, is_rotational_delivery=True
)
```

Maps logical axes to Marlin's native rotational axes:

- Carriage → X (linear)
- Mandrel → A (rotational)
- Delivery → B (rotational)

## MarlinDialect Class

The `MarlinDialect` class wraps an `AxisMapping` with Marlin-specific features:

```python
class MarlinDialect:
    name: str
    mapping: AxisMapping

    def prologue(self) -> List[str]:
        """G-code commands at file start (G21, G94)"""

    def format_move(self, carriage, mandrel, delivery, feed) -> str:
        """Convert logical coordinates to G-code command"""
```

### Prologue Generation

All Marlin dialects emit standard setup commands:

```text
G21  ; Set units to millimeters
G94  ; Set feed rate mode to units/min
```

### Move Formatting

The `format_move()` method converts logical coordinates to G-code:

**Input (logical):**

```python
carriage=50.0, mandrel=180.0, delivery=90.0, feed=2000
```

**Output XAB:**

```text
G1 X50.0 A180.0 B90.0 F2000
```

## Planning Flow

### 1. Wind Definition Parsed

`fiberpath.config` loads and validates the `.wind` file.

### 2. Planner Creates Logical Commands

Layer strategies (`fiberpath.planning.layer_strategies`) generate commands using logical axes:

```python
# Hoop layer: rotate mandrel, small carriage steps
commands = [
    (carriage=0.0, mandrel=0.0, delivery=0.0),
    (carriage=0.5, mandrel=360.0, delivery=0.0),
    (carriage=1.0, mandrel=720.0, delivery=0.0),
    ...
]
```

### 3. Dialect Converts to G-code

The G-code writer (`fiberpath.gcode.generator`) uses the selected dialect:

```python
dialect = MARLIN_XAB_STANDARD
gcode = dialect.format_move(carriage, mandrel, delivery, feed)
```

### 4. G-code Written

Final G-code file contains physical axis names:

```text
; FiberPath v0.5.0 - XAB Format
G21
G94
G1 X0.0 A0.0 B0.0 F2000
G1 X0.5 A360.0 B0.0 F2000
...
```

## Extension Points

### Adding New Dialects

To support a new controller (e.g., FANUC):

1. **Create AxisMapping:**

   ```python
   FANUC_STANDARD = AxisMapping(
       carriage="X",
       mandrel="C",  # FANUC uses C for rotation
       delivery="B",
       is_rotational_mandrel=True,
       is_rotational_delivery=True,
   )
   ```

2. **Create Dialect Class:**

   ```python
   class FanucDialect(Dialect):
       def prologue(self) -> List[str]:
           return [
               "G90",  # Absolute positioning
               "G21",  # Metric units
           ]
   ```

3. **Use in core integration:**

   Pass it through `PlanOptions(dialect=...)` in direct Python integrations.

### Custom Axis Configurations

For non-standard setups, create custom mappings:

```python
CUSTOM_MAPPING = AxisMapping(
    carriage="Z",  # Vertical machine
    mandrel="A",
    delivery="C",  # Different delivery axis
    is_rotational_mandrel=True,
    is_rotational_delivery=True,
)
```

## Rotational Flag Implications

The `is_rotational_*` flags affect:

### Simulation

- Rotational axes use angular velocity calculations
- Linear axes use standard distance/time calculations

### Validation

- Rotational axes checked for 0-360° wrapping
- Linear axes checked for machine limits in mm

### Future Features

- Could affect acceleration profiles
- May influence homing sequences
- Potential for axis-specific optimization

## Implementation Details

### Code Locations

- **Axis mapping:** `fiberpath/gcode/dialects.py`
- **G-code generation:** `fiberpath/gcode/generator.py`
- **CLI integration:** `fiberpath_cli/plan.py`
- **API integration:** `fiberpath_api/routes/plan.py`

### Type Definitions

```python
# Logical coordinates (used in planning)
LogicalCoordinates = tuple[float, float, float]  # (carriage, mandrel, delivery)
# Physical coordinates (used in G-code)
PhysicalCoordinates = dict[str, float]  # {"X": 50.0, "A": 180.0, ...}
```

### Coordinate Transformations

The planner never deals with physical axis names. All transformations happen at the G-code generation boundary:

```python
# Planning layer (logical)
carriage_pos = calculate_carriage_position(...)
mandrel_angle = calculate_mandrel_rotation(...)
# G-code layer (physical)
gcode = dialect.format_move(carriage_pos, mandrel_angle, delivery_angle, feed)
```

## Design Tradeoffs

### Advantages

- ✅ Single planning codebase supports multiple output formats
- ✅ Easy to add new dialects without changing core logic
- ✅ Clear separation of concerns
- ✅ Machine-independent layer strategies

### Limitations

- ⚠️ Adds abstraction layer (slight complexity)
- ⚠️ Dialect-specific optimizations require care
- ⚠️ Must ensure advanced/custom integrations pass dialects consistently

## Future Enhancements

Potential improvements to the axis system:

- **Dynamic dialect selection:** Auto-detect from Marlin firmware capabilities
- **Dialect validation:** Check firmware configuration matches expected axes
- **Non-Marlin dialects:** FANUC, GRBL, custom controllers
- **Axis limits per dialect:** Different physical constraints per machine type
- **Coordinate frame transformations:** Support non-cartesian systems

## See Also

- [Axis Mapping Guide](../guides/axis-mapping.md) - User-facing documentation
- [Architecture Overview](overview.md) - High-level system design
- [Planner Math](../reference/planner-math.md) - Layer strategy algorithms
