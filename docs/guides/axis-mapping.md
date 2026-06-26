# Axis Mapping Guide

FiberPath uses logical planning axes and maps them to physical controller axes at G-code generation time.

## Standard Output Format

FiberPath v0.7.0+ emits a single built-in Marlin format:

- `X` = carriage (linear, mm)
- `A` = mandrel rotation (degrees)
- `B` = delivery-head rotation (degrees)

This matches Marlin rotational-axis semantics and is the recommended production configuration.

## CLI and API Behavior

- CLI `fiberpath plan` always generates XAB output.
- API `POST /plan` always generates XAB output.
- GUI export also generates XAB output through the CLI.

No axis-format flag or request field is required.

## Example Move

```text
G1 X50.0 A180.0 B90.0 F2000
```

This means:

- carriage at `50.0 mm`
- mandrel at `180°`
- delivery head at `90°`
- feed `2000 mm/min`

## Migrating from Legacy XYZ Programs

If you previously used `X/Y/Z` rotational encoding:

1. Update scripts and automation to remove `--axis-format` usage.
2. Regenerate all production G-code with current FiberPath.
3. Validate machine configuration for rotational A/B axes in firmware.
4. Dry-run and verify motion on hardware before full production.

Simulation and plotting now reject auto-detected XYZ programs with a clear error message so stale files are surfaced early.

## Advanced Integrations

Advanced Python integrations can still pass a custom `MarlinDialect` via `PlanOptions(dialect=...)` when needed for specialized machines, but XAB is the built-in product path.
