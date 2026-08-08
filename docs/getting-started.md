# Getting Started with FiberPath

This guide walks you through installing FiberPath and creating your first filament winding pattern.

## Installation

### Desktop GUI (Recommended for New Users)

**Download installers from the [latest release](https://github.com/fiberpath/fiberpath/releases/latest):**

- **Windows:** `.msi` or `.exe` installer
- **macOS:** `.dmg` installer
- **Linux:** `.deb` or `.AppImage`

**No Python installation required.** The desktop GUI is fully self-contained with the FiberPath backend bundled inside. Simply download, install, and start designing winding patterns.

The GUI provides an intuitive interface for planning, visualization, and streaming to hardware—no command-line experience needed.

Once installed, the app registers the `.wind` file type: **double-click a `.wind` file** to open it directly in FiberPath. (On Linux this applies to the `.deb`; AppImage association is best-effort.)

### Python CLI & API (For Developers and Automation)

If you need command-line access or want to integrate FiberPath into your own tools, install via pip or uv:

```sh
pip install fiberpath
```

or with uv for faster, deterministic installs:

```sh
uv pip install fiberpath
```

Verify installation:

```sh
fiberpath --version
```

**Note:** The desktop GUI already includes everything\u2014you only need this if you want standalone CLI access or are developing with the API.

### Development Setup

Clone the repository and install with development dependencies:

```sh
git clone https://github.com/fiberpath/fiberpath.git
cd fiberpath
uv pip install -e .[dev,cli,api]
```

See [Contributing](development/contributing.md) for detailed development setup.

## Basic Workflow

FiberPath follows a simple workflow: **Plan → Visualize → Stream**

### 1. Plan: Generate G-code

Create a `.wind` file defining your winding pattern or use an example:

```sh
fiberpath plan examples/simple_cylinder/input.wind -o simple.gcode
```

The planner generates G-code from your wind definition, validating parameters and calculating toolpaths.

### 2. Visualize: Preview the Pattern

Preview the generated toolpath before streaming to hardware:

```sh
fiberpath plot simple.gcode --output simple.png --scale 0.8
```

The plot command creates an unwrapped mandrel view showing fiber placement. The scale parameter (0-1) adjusts image size.

### 3. Stream: Execute on Hardware (Optional)

Stream G-code to Marlin-compatible hardware:

**CLI:**

```sh
fiberpath stream simple.gcode --port COM3 --baud 115200
```

**GUI:**
Open the Stream tab (Alt+2) and use the visual interface for connection management and file streaming.

## Your First Wind Definition

Create a file named `my_first_wind.wind`:

```json
{
  "schemaVersion": "1.0",
  "mandrelParameters": {
    "diameter": 100,
    "windLength": 200
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
      "lockDegrees": 10,
      "leadInMM": 10,
      "leadOutDegrees": 10
    },
    {
      "windType": "hoop",
      "terminal": true
    }
  ]
}
```

This defines a simple 3-layer pattern: hoop → helical (45°) → hoop.

Generate G-code:

```sh
fiberpath plan my_first_wind.wind -o my_first.gcode
```

## Common Commands

### Planning

```sh
# Basic plan (XAB rotational axes)
fiberpath plan input.wind -o output.gcode
# Verbose output with layer details
fiberpath plan input.wind -o output.gcode --verbose
# Use a calibrated machine profile (sets the slip limit for non-geodesic winding)
fiberpath plan input.wind -o output.gcode --profile my-winder.machine.json
```

### Visualization

```sh
# Generate preview plot
fiberpath plot output.gcode --output preview.png
# Smaller image for quick preview
fiberpath plot output.gcode --output preview.png --scale 0.5
```

### Simulation

```sh
# Estimate time and material usage (summary output; no interactive 3D viewer)
fiberpath simulate output.gcode
```

### Validation

```sh
# Validate wind definition without generating G-code
fiberpath validate input.wind
```

### Streaming

```sh
# Stream with dry-run (no hardware required)
fiberpath stream output.gcode --dry-run
# Stream to hardware
fiberpath stream output.gcode --port COM3 --baud-rate 115200
```

## Next Steps

- **Learn the Wind Format:** See [Wind Format Guide](guides/wind-format.md) for complete schema documentation
- **Understand Axis Mapping:** Read [Axis Mapping Guide](guides/axis-mapping.md) for XAB output details and migration notes
- **Stream to Hardware:** Follow [Marlin Streaming Guide](guides/marlin-streaming.md) for connection and control
- **Explore Examples:** Check `examples/` directory for sample wind definitions (simple cylinder, multi-layer, sized cylinder)

## Troubleshooting

**ImportError: No module named 'fiberpath'**:

- Ensure you've installed the package: `pip install fiberpath` or `uv pip install fiberpath`
- For development: `uv pip install -e .`

**Command not found: fiberpath**:

- Ensure your virtual environment is activated
- Verify installation with `python -m fiberpath_cli.main --help`

**Validation errors in .wind file**:

- Check JSON syntax is valid
- Ensure all required fields are present
- Verify camelCase property names (e.g., `windAngle` not `wind_angle`)
- See [Wind Format Guide](guides/wind-format.md) for schema details

**Serial port not detected**:

- Verify hardware is connected and powered
- Check drivers are installed (Windows may need CH340/FTDI drivers)
- Try different USB ports
- On Linux, ensure user is in `dialout` group: `sudo usermod -a -G dialout $USER`
- See [Troubleshooting Guide](troubleshooting.md) for platform-specific serial port issues
