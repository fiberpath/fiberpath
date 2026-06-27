# Development Guide

Complete setup and workflow documentation for developing FiberPath GUI.

## Prerequisites

### Required

- **Node.js** 24.x and **npm** 11.x ([nodejs.org](https://nodejs.org))
- **Rust** 1.70+ ([rustup.rs](https://rustup.rs))
- **Python CLI** installed and available in PATH (for development mode)
  - Via pip: `pip install fiberpath`
  - Via uv: `uv pip install fiberpath`
  - From source: `pip install -e .` in repo root

**Important:** Production installers bundle the CLI—end users don't need Python. Developers need it for local testing.

### Platform-Specific

**Windows:**

- Microsoft Visual Studio C++ Build Tools
- WebView2 (usually pre-installed on Windows 10+)

**macOS:**

- Xcode Command Line Tools: `xcode-select --install`

**Linux:**

- Build essentials: `sudo apt install build-essential libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf`

## CLI Discovery & Fallback

The GUI uses a two-stage CLI discovery process implemented in `src-tauri/src/cli_path.rs`:

**1. Check for Bundled CLI (Production Mode):**

- **Windows installed:** `resources\_up_\bundled-cli\fiberpath.exe`
- **Windows dev:** `resources\bundled-cli\fiberpath.exe`
- **macOS:** `Resources/bundled-cli/fiberpath` (relative to `.app` bundle)
- **Linux:** `resources/bundled-cli/fiberpath`

**2. Fallback to System PATH (Development Mode):**

If bundled CLI not found, uses `which fiberpath` (Unix) or `where fiberpath` (Windows).

**3. Error if Neither Found:**

Returns user-friendly message suggesting `pip install fiberpath`.

**Why This Design:**

- **Production users:** Zero setup—CLI bundled in installer
- **Contributors:** No PyInstaller required for local dev
- **CI testing:** Works in both modes automatically

**Verification:**

```sh
# Ensure CLI is on PATH for development
fiberpath --version
# Test GUI with bundled CLI
npm run tauri build  # Check src-tauri/target/release/bundle/
```

## Initial Setup

```sh
# Clone repository
git clone https://github.com/your-org/fiberpath.git
cd fiberpath/fiberpath_gui
# Install dependencies
npm install
# Verify CLI is available
fiberpath --version
```

## Development

### Run Development Build

```sh
npm run tauri dev
```

**This is the canonical dev loop** — the only command that runs the GUI with a
working backend. It starts:

- Vite dev server with HMR (Hot Module Replacement)
- Tauri window with development console enabled
- The API sidecar, spawned and supervised by the Rust shell (compute, file, and
  machine features work; the status bar reads **CLI: Ready**)
- File watcher for Rust changes (auto-rebuild)

**Hot Reload:**

- Frontend changes (Svelte/TypeScript) reload instantly
- Rust changes trigger rebuild (~5-15 seconds)

> **Don't QA the prebuilt `src-tauri/target/release/fiberpath_gui` binary.** It
> embeds the frontend that existed when it was last compiled, which is often
> stale. Always use `npm run tauri dev` (or rebuild) to exercise current code.

### Run Frontend Only (no backend)

```sh
npm run dev
```

Starts the Vite dev server at `http://localhost:5173` for **UI-only** work —
styling, layout, component iteration with browser DevTools.

**There is no backend in this mode.** The sidecar URL and health are obtained
through the Tauri bridge (`invoke("api_base_url")` / `check_cli_health`), which
does not exist in a plain browser — so compute, file, and machine features are
unavailable. The app detects this and shows a calm **"Browser preview"** banner
(status bar: **Browser preview**) rather than an error. For anything that needs
the backend, use `npm run tauri dev`.

## Testing

### Run All Tests

```sh
npm test
```

### Run Tests in Watch Mode

```sh
npm test -- --watch
```

### Run Specific Test File

```sh
npm test -- schemas.test.ts
```

### Test Coverage

```sh
npm test -- --coverage
```

**Current Test Suite:**

- Schema and validation tests (`src/lib`)
- Reactive state tests (`src/state/*.svelte.test.ts`)
- Service and converter tests
- Svelte component tests (`*.svelte.test.ts`)

## Building

### Development Build

```sh
npm run tauri build -- --debug
```

Creates debug binary with:

- Development console enabled
- Faster build time
- Source maps included

### Production Build

```sh
npm run tauri build
```

Creates optimized release bundle:

- **Windows:** `.exe` installer in `src-tauri/target/release/bundle/msi/`
- **macOS:** `.dmg` disk image in `src-tauri/target/release/bundle/dmg/`
- **Linux:** `.AppImage` or `.deb` in `src-tauri/target/release/bundle/`

**Build Output:**

```sh
src-tauri/target/release/
├── fiberpath-gui[.exe]         # Binary executable
└── bundle/
    ├── msi/                     # Windows installer
    ├── dmg/                     # macOS disk image
    └── appimage/                # Linux portable app
```

## Packaging

### Create Distributable Package

```sh
npm run package
```

This runs:

1. `npm run tauri build` (production build)
2. Package verification
3. Signing (if configured)

**Release Checklist:**

- [ ] Update version in `package.json`, `Cargo.toml`, `tauri.conf.json`
- [ ] Run `npm run check:all` and `npm test`
- [ ] Run `npm run build` and `npm run perf:bundle`
- [ ] Test on target platforms
- [ ] Build production bundles
- [ ] Verify bundle functionality
- [ ] Tag release in git

## Code Quality

### Run All Checks

```sh
npm run check:all
```

Runs in sequence:

1. TypeScript compiler (`tsc --noEmit`)
2. Stylelint (`src/**/*.css`)
3. CSS variable guard (`lint:css:vars`)
4. Rust formatter check (`cargo fmt --check`)
5. Clippy (Rust linting)

`check:all` covers the plain `.ts` type check; the `.svelte`/`.svelte.ts`
type check (`npm run check:svelte`, via `svelte-check`) runs as its own command.

**CI Pipeline:** These checks plus `npm run check:svelte`, `npm run build`, and
`npm run perf:bundle` run on every PR.

### Individual Commands

```sh
# Type and CSS checks
npm run lint              # TypeScript type check (tsc --noEmit) for .ts
npm run check:svelte      # svelte-check for .svelte and .svelte.ts
npm run lint:css          # Stylelint
npm run lint:css:vars     # CSS variable guard
npm run lint:css:fix      # Auto-fix CSS lint issues
# Rust checks
npm run format:check      # cargo fmt --check
npm run format:fix        # cargo fmt
npm run clippy            # cargo clippy -- -D warnings
# Tests and build
npm test                  # Vitest
npm run test:coverage     # Vitest with coverage
npm run build             # Vite production build
npm run perf:bundle       # Enforce bundle budget and emit metrics
```

## Project Structure

```sh
fiberpath_gui/
├── src/                          # Frontend code (Svelte 5 + Vite SPA)
│   ├── main.svelte.ts            # App entry point (mounts App.svelte)
│   ├── App.svelte                # Root component with workspace layout
│   ├── shell/                    # App shell (MenuBar, tabs, workspaces, status bar)
│   ├── components/               # Feature components (forms, editors, layers, canvas, machine, dialogs)
│   ├── ui/                       # Reusable primitives (NumberField, Dialog, …)
│   ├── state/                    # Reactive runes singletons (*.svelte.ts)
│   ├── services/                 # Plain service functions (file operations)
│   ├── lib/                      # Tauri/API command bindings, validation helpers
│   ├── api/                      # OpenAPI-generated sidecar client
│   ├── styles/                   # Global CSS + design tokens
│   ├── tests/                    # Test setup and mocks
│   └── types/                    # Domain models, document, converters
├── src-tauri/                    # Rust backend
│   ├── src/
│   │   ├── main.rs               # Tauri command registration + app bootstrap
│   │   └── marlin.rs             # Streaming state and command handling
│   ├── Cargo.toml                # Rust dependencies
│   ├── tauri.conf.json           # Tauri configuration
│   └── icons/                    # App icons
├── schemas/                      # JSON schemas
│   └── FiberPathProject.schema.json
├── docs/                         # This documentation
├── package.json                  # NPM scripts and dependencies
├── tsconfig.json                 # TypeScript config (strict mode)
├── vite.config.ts                # Vite build config
└── vitest.config.ts              # Test configuration
```

## Common Tasks

### Add New Tauri Command

1. **Define in Rust** (`src-tauri/src/main.rs`):

   ```rust
   #[tauri::command]
   fn my_command(arg: String) -> Result<String, String> {
       Ok(format!("Hello {}", arg))
   }
   ```

2. **Register** in `main()`:

   ```rust
   tauri::Builder::default()
       .invoke_handler(tauri::generate_handler![my_command])
       .run(tauri::generate_context!())
   ```

3. **Call from Frontend** (`src/lib/commands.ts`):

   ```typescript
   export async function myCommand(arg: string): Promise<string> {
     return invoke("my_command", { arg });
   }
   ```

### Add New Layer Type

1. **Define Zod schema** (`src/lib/schemas.ts`)
2. **Add discriminated union case** to the wind-definition schema
3. **Update TypeScript types** (`src/types/project.ts`)
4. **Add an editor component** in `src/components/editors/` and wire it into
   `PrepareWorkspace.svelte`'s layer-properties switch
5. **Add tests** in `schemas.test.ts` (and an editor `*.svelte.test.ts`)

### Add UI Component

1. **Create component file** in `src/components/MyComponent.svelte` (or `src/ui/` for a primitive)
2. **Declare props** with `let { ... }: Props = $props()`
3. **Reuse global primitives/tokens**; add a scoped `<style>` block for unique chrome
4. **Read shared state** from a `src/state/*.svelte` singleton via `$derived`
5. **Write tests** in `MyComponent.svelte.test.ts`

## Debugging

### Frontend Debugging

**Browser DevTools (dev mode only):**

- Right-click → Inspect Element
- Or press F12 in Tauri window

**Inspecting reactive state:**

State lives in plain runes singletons (`src/state/*.svelte.ts`). Import one in the
DevTools console (or log it) to inspect it — for example
`projectSession.document`, `projectSession.isDirty`, or `uiState.workspace`. The
Svelte DevTools extension can also inspect component state and props live.

### Rust Debugging

**Console Logging:**

```rust
println!("Debug: {:?}", value);
```

**Run with backtrace:**

```sh
RUST_BACKTRACE=1 npm run tauri dev
```

### CLI Integration Debugging

**Test CLI directly:**

```sh
fiberpath plan examples/simple_cylinder/input.wind
```

**Check CLI version:**

```sh
fiberpath --version
```

**Verify CLI in PATH:**

```sh
# Windows PowerShell
Get-Command fiberpath
# macOS/Linux
which fiberpath
```

## Troubleshooting

### "Command 'fiberpath' not found"

**Solution:** Install Python CLI and ensure it's in PATH:

```sh
pip install fiberpath
fiberpath --version
```

### "Tauri build failed on Linux"

**Solution:** Install WebKit dependencies:

```sh
sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev
```

### Tests fail with "Cannot find module"

**Solution:** Rebuild dependencies:

```sh
rm -rf node_modules package-lock.json
npm install
```

### HMR not working

**Solution:** Restart dev server:

```sh
# Ctrl+C to stop
npm run tauri dev
```

### Streaming connection timeout

**Solution:** Check serial port permissions:

- **Linux:** Add user to dialout group: `sudo usermod -a -G dialout $USER` (logout required)
- **macOS:** Grant permissions in System Settings → Security
- **Windows:** Usually no action needed

## Performance Profiling

See [Performance Guide](guides/performance.md) for detailed profiling instructions using the browser Performance panel.

## Next Steps

- [Tech Stack Details](architecture/tech-stack.md)
- [State Management Architecture](architecture/state-management.md)
- [Schema Validation Guide](guides/schemas.md)
- [Styling Guide](guides/styling.md)
