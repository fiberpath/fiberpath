# Backend Integration Architecture

How FiberPath GUI bridges to its Python backends. There are **two** backends, and
the GUI talks to each differently:

- **Compute** (plan / validate / plot) goes to a **local FastAPI sidecar** over
  HTTP, through a generated, OpenAPI-typed client.
- **Native host duties** (file I/O, driving Marlin hardware over serial) stay as
  **Tauri commands** invoked over the IPC bridge.

The Tauri shell is a thin native host: it owns the window, reads/writes files,
**supervises the sidecar process**, and runs the Marlin serial path. It no longer
performs compute itself.

> History: before v0.7 the shell shelled out to the `fiberpath` CLI for compute
> (`plan_wind`, `simulate_program`, `plot_preview`) and round-tripped results
> through temp files. Those commands were removed once the sidecar landed
> (#192/#193/#194). Compute now never touches the filesystem.

## Architecture Overview

```text
┌─────────────────────────────────────┐
│  React Components                   │  User interactions
│  (PlanForm, PlotPanel, Stream tab)  │
└─────────────┬───────────────────────┘
              │ TypeScript functions
              ▼
┌─────────────────────────────────────┐
│  Command Layer (lib/commands.ts)    │  Type-safe wrappers + retry
└──────┬───────────────────────┬──────┘
       │ compute               │ files / hardware
       ▼                       ▼
┌──────────────────┐   ┌──────────────────────┐
│ API client       │   │ Tauri IPC (invoke)   │
│ (lib/apiClient)  │   │ - save/load_wind_file│
│ openapi-fetch    │   │ - stream_program     │
└──────┬───────────┘   │ - marlin::*          │
       │ HTTP          │ - check_cli_health   │
       │ 127.0.0.1     └──────────┬───────────┘
       ▼                          │ std::process::Command
┌──────────────────┐              ▼
│ FastAPI sidecar  │   ┌──────────────────────┐
│ (fiberpath-api)  │   │ FiberPath CLI        │
│ POST /plan       │   │ $ fiberpath stream   │
│ POST /validate   │   │   (Marlin serial)    │
│ POST /plot       │   └──────────────────────┘
└──────────────────┘
   both freeze from the same `fiberpath` Python package
```

## Compute path: the API sidecar

### Why a sidecar instead of CLI calls

| CLI-subprocess (old)                        | HTTP sidecar (now)                          |
| ------------------------------------------- | ------------------------------------------- |
| One process spawn per operation             | One long-lived process, many requests       |
| Results passed through temp files on disk   | Stateless request/response, nothing on disk |
| Hand-written response types, Zod-validated  | Types generated from the OpenAPI spec       |
| GUI re-implements arg/flag wiring per call  | One typed client method per route           |

The same compute engine is reused by the CLI and the API — they freeze from the
one `fiberpath` Python package — but the GUI now speaks to it as a service.

### Supervision (`src-tauri/src/api_sidecar.rs`)

The Rust shell spawns and owns the sidecar process. The sidecar binds an
**ephemeral `127.0.0.1` port** (loopback only — never network-exposed) and prints
a one-line JSON handshake to stdout so the shell learns the port:

```json
{"event":"listening","host":"127.0.0.1","port":54321}
```

Lifecycle:

1. **Spawn** the frozen `fiberpath-api` (or the `fiberpath-api` console script in
   dev) with piped stdio.
2. **Read the handshake** — the first stdout line yields the base URL
   `http://127.0.0.1:<port>`. If the process exits first (EOF), that surfaces as
   `NoHandshake`.
3. **Drain pipes** on background threads so a full pipe never blocks the child;
   stderr (uvicorn logs) is forwarded to `log::debug!("[api-sidecar] …")`.
4. **Respawn on death** — `base_url()` checks `try_wait()` and starts a fresh
   sidecar if the previous one died.
5. **Reap on Drop** — the child is killed and waited on app exit so it never
   lingers as an orphan holding its port.

The shell warms the sidecar in a background thread at startup (`setup` hook), so
the first compute call is fast; failures there are non-fatal because
`api_base_url` spawns lazily on demand. The frontend reaches the URL through the
`api_base_url` Tauri command.

### The typed client (`src/lib/apiClient.ts`)

`getApiClient()` is the single entry point. On first use it:

1. invokes `api_base_url` to get (and, if needed, start) the sidecar URL,
2. polls `GET /health` until the server answers (`waitForHealth`, 30 s budget),
3. builds an [`openapi-fetch`](https://github.com/openapi-ts/openapi-typescript)
   client over the generated types in `src/api/`.

The client promise is memoised; a failed start clears the memo so the next call
retries (`resetApiClient()` forces a fresh client, e.g. in tests).

```typescript
const client = await getApiClient();
const response = await client.POST("/plan", { body: definition });
if (response.error || !response.data) throw new CommandError(/* … */);
const { gcode, commandCount } = response.data;
```

Request/response shapes are **generated**, not hand-written: `client.POST("/plan", …)`
knows the body and response types from the OpenAPI spec. A CI drift gate
regenerates the spec and client and fails if either is out of date (see #191).

> **CORS:** the webview fetches the sidecar cross-origin (its `tauri://` origin →
> `127.0.0.1:<port>`), so the sidecar enables permissive CORS. It binds loopback
> only, so allowing any origin is safe. Without it the webview can't read
> responses ("TypeError: Load failed").

### Command wrappers (`src/lib/commands.ts`)

The compute wrappers translate between the UI and the API:

| Wrapper                   | API calls                                  | Notes                                                         |
| ------------------------- | ------------------------------------------ | ------------------------------------------------------------ |
| `planWind`                | `POST /plan` → `saveWindFile`              | API returns `gcode` in the body; the shell writes it to disk |
| `plotDefinition`          | `POST /plan` then `POST /plot`             | `/plot` returns a PNG arrayBuffer, encoded to base64 for `<img>` |
| `validateWindDefinition`  | `POST /validate`                           | 400/422 is a normal "invalid" outcome, not a thrown error    |

Because the API is body-only and stateless, `planWind` plans in memory and then
persists the returned G-code through the file-system bridge — the backend never
writes files itself.

## Native path: Tauri commands

These stay in the Rust shell because they need OS access the sidecar shouldn't have.

| Command                                  | Purpose                                            |
| ---------------------------------------- | -------------------------------------------------- |
| `save_wind_file` / `load_wind_file`      | Read/write `.wind` (and `.gcode`) files            |
| `stream_program`                         | Stream G-code to a Marlin board (shells out to the CLI's `stream` subcommand) |
| `marlin::*`                              | Interactive Marlin control (connect, send, pause…) |
| `check_cli_health` / `get_cli_diagnostics` | Verify the bundled CLI is runnable                 |

`stream_program` and the `exec_fiberpath`/`parse_json_payload` helpers remain
only for the Marlin serial path; its REST surface lands with #190/#199, after
which more of this moves to the sidecar too.

### Frontend wrappers and retry

Compute and file wrappers are decorated with `withRetry` for transient failures
(file locks, a sidecar still warming up):

```typescript
export const planWind = withRetry(
  async (definitionJson: string, outputPath: string): Promise<PlanSummary> => {
    const client = await getApiClient();
    const response = await client.POST("/plan", { body: JSON.parse(definitionJson) });
    if (response.error || !response.data) {
      throw new CommandError("Failed to plan wind definition", "plan", response.error);
    }
    await saveWindFile(outputPath, response.data.gcode);
    return { output: outputPath, commands: response.data.commandCount };
  },
  { maxAttempts: 2 },
);
```

Errors are wrapped in typed classes (`src/lib/schemas.ts`): `CommandError`,
`ValidationError`, `FileError`, `ConnectionError` — all extending `FiberPathError`.

## Bundling & discovery

Both binaries are frozen with PyInstaller `--onefile` from the same Python package
and bundled into the installer:

- `scripts/freeze_cli.py` → `fiberpath` (Typer CLI)
- `scripts/freeze_api.py` → `fiberpath-api` (uvicorn + FastAPI app)

In CI the freeze jobs run per-platform and their artifacts are dropped into
`fiberpath_gui/bundled-cli/` and `fiberpath_gui/bundled-api/` before
`tauri build`. (Those directories are git-ignored apart from a `.gitkeep`; the
binaries are build artifacts, never committed.)

### Path resolution (`cli_path.rs`, `api_path.rs`)

Each resolver checks the bundled binary first, then falls back to the system
`PATH` (dev installs that `pip install -e .`).

Resources bundled from the `../bundled-cli/*` / `../bundled-api/*` globs land
under a **`_up_/` subdirectory on every platform** (Tauri encodes the parent-dir
`../`). So resolution prefers `…/_up_/bundled-cli/<exe>` and falls back to a flat
`…/bundled-cli/<exe>` (dev builds):

```rust
let up_layout = resource_dir.join("_up_").join("bundled-cli").join(exe_name);
let cli_path = if up_layout.exists() {
    up_layout
} else {
    resource_dir.join("bundled-cli").join(exe_name)
};
```

| Mode          | Platform | Resolved path                                          |
| ------------- | -------- | ------------------------------------------------------ |
| **Installed** | all      | `…/resources/_up_/bundled-{cli,api}/<exe>`             |
| **Dev build** | all      | `…/resources/bundled-{cli,api}/<exe>`                  |
| **Fallback**  | all      | `which fiberpath` / `which fiberpath-api` (system PATH) |

> The earlier docs claimed `_up_/` was Windows-only. It is not — every platform
> gets it for resources copied from a parent-relative glob. Resolving it
> uniformly is what fixed the "backend unavailable" bug in #208.

## Testing

Compute wrappers are tested against a mocked `openapi-fetch` client; native
wrappers mock `@tauri-apps/api/core`'s `invoke`. The sidecar supervisor has Rust
unit tests for the handshake parser, and `scripts/ci/smoke_api_sidecar.py`
exercises the frozen server end-to-end in CI.

```typescript
import { vi } from "vitest";
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

it("streams via the Marlin bridge", async () => {
  vi.mocked(invoke).mockResolvedValue({ /* StreamSummary */ });
  await streamProgram("out.gcode", { baudRate: 115200, dryRun: true });
  expect(invoke).toHaveBeenCalledWith("stream_program", expect.objectContaining({
    gcodePath: "out.gcode",
  }));
});
```

## Troubleshooting

### "API sidecar did not become healthy"

**Cause:** the sidecar never answered `GET /health` within the timeout — usually
a frozen `fiberpath-api` that failed to start, or a missing bundled binary in dev.

**Check:** look for `[api-sidecar]` lines in the logs (forwarded uvicorn stderr),
confirm `fiberpath-api` resolves (bundled path or `which fiberpath-api`), and that
CORS is enabled on the app.

### "CLI Backend Unavailable"

**Cause:** the bundled CLI (used by the Marlin/`stream_program` path and health
checks) wasn't found.

**Check:** `get_cli_diagnostics` reports the resolved path, whether it exists, and
the result of running `--help`. In dev, `pip install -e .` exposes `fiberpath` on
PATH.

### "Permission denied" on a serial port (Linux)

Add your user to the `dialout` group: `sudo usermod -a -G dialout $USER`.

## Next Steps

- [Streaming State Management](streaming-state.md) — real-time Marlin control
- [State Management](state-management.md) — store → backend data flow
- [Schema Validation](../guides/schemas.md) — where Zod still applies
