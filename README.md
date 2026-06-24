<div align="center">

<h1>FiberPath</h1>

**Plan, simulate, and manufacture composite parts with precision fiber winding.**

[![Version](https://img.shields.io/badge/version-0.7.2-4c7284)](https://github.com/CameronBrooks11/fiberpath/releases)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-00695C.svg)](LICENSE)
[![Backend CI](https://img.shields.io/github/actions/workflow/status/CameronBrooks11/fiberpath/backend-ci.yml?branch=main&label=Backend%20CI&logo=python&logoColor=white)](https://github.com/CameronBrooks11/fiberpath/actions/workflows/backend-ci.yml)
[![GUI CI](https://img.shields.io/github/actions/workflow/status/CameronBrooks11/fiberpath/gui-ci.yml?branch=main&label=GUI%20CI&logo=react&logoColor=white)](https://github.com/CameronBrooks11/fiberpath/actions/workflows/gui-ci.yml)
[![Docs](https://img.shields.io/github/actions/workflow/status/CameronBrooks11/fiberpath/docs-deploy.yml?branch=main&label=Docs&logo=githubpages&logoColor=white)](https://cameronbrooks11.github.io/fiberpath)

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/React-19+-61DAFB?logo=react&logoColor=black)
![Tauri](https://img.shields.io/badge/Tauri-2.0-FFC131?logo=tauri&logoColor=white)

[Download](https://github.com/CameronBrooks11/fiberpath/releases/latest) · [Documentation](https://cameronbrooks11.github.io/fiberpath) · [Examples](examples/)

</div>

---

## Overview

FiberPath automates the complex process of **filament winding**—wrapping fiber-reinforced composites around mandrels to create lightweight, high-strength cylindrical parts like pressure vessels, pipes, and aerospace structures.

Design multi-layer winding patterns in a visual interface, simulate the full manufacturing process, and stream G-code directly to Marlin-based hardware. FiberPath handles the winding mathematics — hoop and helical path generation, tow coverage, and machine kinematics for cylindrical mandrels — so you can focus on part design.

### Features

- **Visual Layer Editor** – Design winding patterns with live preview
- **Winding Path Planning** – Automatic hoop, helical, and skip pattern generation for cylindrical mandrels
- **Hardware Simulation** – Validate motion before manufacturing
- **Direct Machine Control** – Stream G-code to Marlin controllers with pause/resume
- **XAB-Native Axis Output** – Standardized rotational-axis output with clear logical axis mapping
- **Cross-Platform Desktop GUI** – Native Windows, macOS, and Linux applications
- **Command-Line Tools** – Scriptable workflows for automation and CI/CD
- **Comprehensive Documentation** – Architecture guides, examples, and API reference

> **Scope & roadmap:** FiberPath currently plans **cylindrical mandrels** with hoop, helical, and skip layers. Non-cylindrical (geodesic) surface support — including tapered and custom mandrels — is planned but not yet implemented.

## Quick Start

### Option 1: Desktop GUI (Recommended)

Download the installer for your platform from the [latest release](https://github.com/CameronBrooks11/fiberpath/releases/latest):

- **Windows**: `.msi` or `.exe` installer
- **macOS**: `.dmg` disk image
- **Linux**: `.deb` package or `.AppImage`

Launch the application, load an example from the `File` menu, and explore the visual editor.

### Option 2: Command-Line Interface

Install via pip or uv:

```sh
pip install fiberpath
# or
uv pip install fiberpath
```

Generate G-code from an example:

```sh
fiberpath plan examples/simple_cylinder/input.wind -o simple.gcode
fiberpath plot simple.gcode --output simple.png
```

The `plot` command creates a 2D unwrapped visualization of the toolpath for quick inspection.

## Installation

### Desktop Application (Recommended)

📦 **Download:** [github.com/CameronBrooks11/fiberpath/releases/latest](https://github.com/CameronBrooks11/fiberpath/releases/latest)

**No Python installation required**—the GUI is a fully self-contained native application with the FiberPath backend bundled inside. Just download, install, and run.

- **Windows:** `.msi` or `.exe` installer
- **macOS:** `.dmg` disk image
- **Linux:** `.deb` package or `.AppImage`

All desktop installers include the complete FiberPath toolchain for planning, simulation, and streaming.

### Python Package

**Requirements:** Python 3.11+

```sh
# Install from PyPI
pip install fiberpath

# Install with optional dependencies
pip install fiberpath[cli]  # CLI tools
pip install fiberpath[api]  # FastAPI server
pip install fiberpath[dev]  # Development tools
```

**Development Install:**

```sh
git clone https://github.com/CameronBrooks11/fiberpath.git
cd fiberpath
uv pip install -e .[dev,cli,api]
pytest
```

> 💡 Using [uv](https://docs.astral.sh/uv/) is recommended for faster installs, but standard `pip` works fine.

## Usage Examples

### Planning a Winding Pattern

```sh
# Generate G-code from a .wind configuration
fiberpath plan examples/simple_cylinder/input.wind -o output.gcode
```

### Visualizing Toolpaths (2D)

```sh
# Create 2D unwrapped plot
fiberpath plot output.gcode --output preview.png --scale 0.8
```

### Simulating Jobs

```sh
# Simulation summary (time/material estimates; no interactive 3D viewer)
fiberpath simulate output.gcode
```

### Streaming to Hardware

```sh
# Test streaming without hardware connection
fiberpath stream output.gcode --dry-run

# Connect and stream to Marlin controller
fiberpath stream output.gcode --port COM5 --baud-rate 250000
```

FiberPath automatically waits for Marlin's startup sequence (`M92`, `M203`, etc.) before streaming. Use `Ctrl+C` to pause—FiberPath issues `M0` and resumes with `M108`.

### Using the Desktop GUI

The GUI provides two main workflows:

**Main Tab:**

- Visual layer editor with add/remove/reorder
- Real-time unwrapped toolpath preview
- Parameter forms for mandrel, tow, and machine settings
- Export to G-code or save as `.wind` project file

**Stream Tab:**

- Serial port selection and connection management
- Manual G-code command input for testing
- File streaming with pause/resume/cancel controls
- Real-time position tracking and status updates

### Development Workflow

```sh
# Run GUI in development mode
cd fiberpath_gui
npm install
npm run tauri dev

# Run tests
pytest                           # Python tests
cd fiberpath_gui && npm test     # TypeScript tests

# Run API server
fiberpath-api --port 8000        # Requires fiberpath[api] install
```

## Architecture

FiberPath consists of four coordinated components:

```text
┌─────────────────────────────────────────────────┐
│              Desktop GUI (Tauri + React)        │
│  • Visual layer editor                          │
│  • 2D preview canvas                            │
│  • Serial communication controls                │
└───────────────┬─────────────────────────────────┘
                │ IPC calls
                ▼
┌─────────────────────────────────────────────────┐
│           CLI (Typer + Python)                  │
│  • plan   • plot   • simulate   • stream        │
└───────────────┬─────────────────────────────────┘
                │ imports
                ▼
┌─────────────────────────────────────────────────┐
│           Core Engine (Python)                  │
│  • Winding path planning (hoop/helical/skip)    │
│  • Layer strategies                             │
│  • G-code generation                            │
└─────────────────────────────────────────────────┘
                ▲
                │ imports
┌───────────────┴─────────────────────────────────┐
│           API Server (FastAPI)                  │
│  • RESTful planning endpoints                   │
│  • JSON input/output                            │
│  • Optional deployment for web integration      │
└─────────────────────────────────────────────────┘
```

**Design Principles:**

- **CLI and API are parallel interfaces** to the same Core Engine
- **GUI calls CLI via IPC** for offline operation (no server required)
- **Core is deterministic** and thoroughly tested
- **Modular architecture** allows using components independently

See [Architecture Documentation](https://cameronbrooks11.github.io/fiberpath/architecture/overview/) for detailed design rationale.

## Axis Configuration

FiberPath uses XAB rotational-axis output in built-in workflows:

- `X` = Carriage position (linear, mm)
- `A` = Mandrel rotation (rotational, degrees)
- `B` = Delivery head rotation (rotational, degrees)

Legacy XYZ programs should be re-generated under current versions. Simulation and plotting reject auto-detected XYZ files with an explicit error so stale programs are surfaced early.

## Documentation

Comprehensive documentation is available at [cameronbrooks11.github.io/fiberpath](https://cameronbrooks11.github.io/fiberpath):

- **[Getting Started Guide](https://cameronbrooks11.github.io/fiberpath/getting-started/)** – Installation and first steps
- **[Architecture Overview](https://cameronbrooks11.github.io/fiberpath/architecture/overview/)** – System design and components
- **[Usage Guides](https://cameronbrooks11.github.io/fiberpath/guides/visualization/)** – Visualization, streaming, WIND format
- **[API Reference](https://cameronbrooks11.github.io/fiberpath/reference/api/)** – Core functions and CLI commands
- **[GUI Documentation](https://cameronbrooks11.github.io/fiberpath/gui/overview/)** – Desktop application architecture
- **[Development Guide](https://cameronbrooks11.github.io/fiberpath/development/contributing/)** – Contributing, tooling, release process

## Contributing

Contributions are welcome! FiberPath is actively developed and maintained.

**Before contributing:**

1. Read the [Contributing Guide](https://cameronbrooks11.github.io/fiberpath/development/contributing/)
2. Check existing [issues](https://github.com/CameronBrooks11/fiberpath/issues) and [pull requests](https://github.com/CameronBrooks11/fiberpath/pulls)
3. Open an issue to discuss major changes before implementing

**Development setup:**

```sh
git clone https://github.com/CameronBrooks11/fiberpath.git
cd fiberpath
uv pip install -e .[dev,cli,api]
pytest

cd fiberpath_gui
npm install
npm test
```

**Code standards:**

- Python code follows PEP 8 (enforced by CI)
- TypeScript/React follows project ESLint configuration
- All new features require tests and documentation
- Commit messages use conventional commits format

See [Development Documentation](https://cameronbrooks11.github.io/fiberpath/development/) for tooling, CI/CD, and release process details.

## License

FiberPath is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

This means:

- ✅ Free to use, modify, and distribute
- ✅ Source code must be made available to users
- ⚠️ Network use (e.g., hosting as a service) triggers copyleft

See [LICENSE](LICENSE) for full terms.

---

**Questions?** Open an [issue](https://github.com/CameronBrooks11/fiberpath/issues) or check the [documentation](https://cameronbrooks11.github.io/fiberpath).

**Found a bug?** Report it on [GitHub Issues](https://github.com/CameronBrooks11/fiberpath/issues/new) with steps to reproduce.
