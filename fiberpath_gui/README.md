# FiberPath Desktop GUI

Cross-platform desktop application for FiberPath filament winding. Built with Tauri + React, providing visual planning, simulation, and hardware streaming.

## Features

### Main Tab - Wind Pattern Planning & Visualization

- **Plan** – Generate G-code from `.wind` definitions with real-time validation
- **Plot Preview** – View PNG visualizations with adjustable scale
- **Simulate** – Inspect motion time estimates and machine kinematics
- **Layer Management** – Create and edit hoop, helical, and skip winding layers

### Stream Tab - Marlin G-code Streaming

- **Serial Connection** – Auto-discover and connect to Marlin-compatible devices
- **Manual Control** – Quick-access buttons (Home, Get Position, E-Stop, Disable Motors)
- **File Streaming** – Real-time progress monitoring with pause/resume
- **Live Log** – Command/response history with auto-scroll
- **Keyboard Shortcuts** – `Alt+1/2` tab switching, `?` for help

## Installation

**End Users:** Download installers from [GitHub Releases](https://github.com/fiberpath/fiberpath/releases). No setup required—the application includes everything needed.

**Developers:** See [Development Setup](#development-setup) below.

## Development Setup

### Prerequisites

- **Node.js 24.x + npm 11.x** ([nodejs.org](https://nodejs.org))
- **Rust 1.70+** ([rustup.rs](https://rustup.rs))
- **Platform-specific tools:**
  - Windows: Visual C++ Build Tools, WebView2
  - macOS: Xcode Command Line Tools
  - Linux: `build-essential libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf`

### Bundled vs Development CLI Modes

**Production Mode (Installers):**

- CLI is bundled inside the application (`bundled-cli/fiberpath.exe` or `bundled-cli/fiberpath`)
- No Python installation required
- Frozen executable includes all dependencies

**Development Mode (Local):**

- Application checks for bundled CLI first
- If not found, falls back to system PATH: `which fiberpath` (Unix) or `where fiberpath` (Windows)
- **For development, install CLI from source:**
  ```sh
  # In repo root
  pip install -e .[cli]
  # Or with uv
  uv pip install -e .[cli]
  ```

**Verification:**

```sh
# Ensure CLI is accessible
fiberpath --version

# Should output: fiberpath, version X.Y.Z
```

This fallback design allows contributors to develop without running PyInstaller locally.

## Getting Started

```pwsh
cd fiberpath_gui
npm install
npm run tauri dev
```

The `tauri dev` command spawns the Vite dev server and opens the desktop shell.
It is the canonical dev loop: the Rust shell also starts the API sidecar, so
compute/file/machine features work (status bar shows **CLI: Ready**).

> `npm run dev` alone serves the UI in a browser at `http://localhost:5173` with
> **no backend** (it shows a "Browser preview" banner) — use it only for styling
> and layout. Likewise, don't QA the prebuilt `release` binary; it can embed a
> stale frontend. See [../docs/development.md](../docs/development.md).

### Main Tab

Use the four panels to plan, visualize, and simulate winding patterns:

1. **Plan** – Select a `.wind` input file. The CLI generates G-code and returns a JSON summary.
2. **Plot Preview** – Load a `.gcode` file and adjust the scale slider to view PNG previews.
3. **Simulate** – Run the simulator to inspect motion time estimates.
4. **Layer Editor** – Create and configure hoop, helical, and skip winding layers.

### Stream Tab

Connect to Marlin-compatible hardware and stream G-code:

1. **Connect** – Refresh serial ports, select your device and baud rate, then click Connect.
2. **Manual Control** – Test the connection with common commands (Home, Get Position) or send custom G-code.
3. **Stream Files** – Select a G-code file, click Start Stream, and monitor progress in real-time.
4. **Monitor** – View command/response log with timestamps and status updates.

See [../docs/guides/marlin-streaming.md](../docs/guides/marlin-streaming.md) for detailed streaming documentation.

## Schema Management

The GUI uses a JSON Schema generated from the Python Pydantic models to ensure type safety and validation:

```pwsh
# Regenerate schema and TypeScript types from Python models
npm run schema:generate
```

This:

1. Runs `scripts/generate_schema.py` to extract JSON Schema from Pydantic
2. Generates TypeScript types in `src/types/wind-schema.ts`
3. Ensures GUI and CLI stay in sync

The schema is automatically validated before sending data to the backend, catching errors early.

## Building for Production

For production builds:

```pwsh
cd fiberpath_gui
npm install
npm run package
```

`npm run package` wraps `tauri build --ci`, which emits platform-specific installers under
`src-tauri/target/release/bundle/` (MSI/NSIS on Windows, AppImage/Deb on Linux, App/Disk image on
macOS). Windows packaging works locally, while macOS/Linux artifacts require running the command on
those respective platforms (handled automatically in CI).

See `fiberpath_gui/docs/` for detailed documentation:

- `overview.md` – GUI capabilities and architecture overview
- `development.md` – setup, build, and quality workflows
- `testing.md` – GUI test strategy and commands
- `architecture/` – stack details, CLI bridge, and streaming state model
- `guides/` – styling, schema, and performance guides
- `reference/type-safety.md` – end-to-end type contracts
