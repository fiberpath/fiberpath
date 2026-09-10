# AGENTS.md

Instructions for AI coding agents working in this repository.

## Project

FiberPath is a filament-winding **planner, simulator and G-code toolkit**: winding
patterns are expressed as mathematics over a mandrel surface, lowered through a
typed Motion IR, and post-processed to Marlin XAB G-code. It ships a Python
engine + CLI, a FastAPI service, and a Svelte/Tauri desktop app from one repo.

The `.wind` input is a **normative, versioned open format**, not an internal
config file — see [`docs/guides/wind-format.md`](docs/guides/wind-format.md).

## Stack

- **Engine / CLI / API** — Python `>=3.11`, package manager **uv**;
  `ruff` (format + lint), `mypy`, `pytest`.
- **Desktop GUI** — Svelte 5 (runes) + TypeScript + Vite, tested with Vitest.
  There is no SvelteKit. State lives in `src/state/*.svelte.ts`.
- **Desktop shell** — Rust + Tauri v2 (`fiberpath_gui/src-tauri`).

## Layout

```
fiberpath/            # engine: config schemas, planning, gcode, simulation, visualization
fiberpath_cli/        # Typer CLI (`fiberpath`)
fiberpath_api/        # FastAPI service (`fiberpath-api`), also run as a GUI sidecar
fiberpath_gui/        # Svelte desktop app; src-tauri/ is the Rust shell
tests/                # mirrors the engine layout; conformance/ holds the format corpus
examples/             # .wind inputs + expected.gcode goldens
conformance/          # valid/ and invalid/ .wind cases for the open format
docs/                 # published to fiberpath.org via the org-pages repo
```

## Commands

**There is no `justfile` in this repo** — do not go looking for one. Run the
stack-native commands directly. These are what CI enforces:

```sh
# Python engine / CLI / API
uv sync --all-extras
uv run ruff check && uv run ruff format --check
uv run mypy
uv run pytest

# Svelte GUI  (cd fiberpath_gui)
npm ci
npm run lint            # tsc --noEmit
npm run check:svelte
npm run lint:css && npm run lint:css:vars
npx vitest run
npm run build && npm run perf:bundle

# Rust shell  (cd fiberpath_gui/src-tauri)
cargo fmt --check && cargo clippy -- -D warnings && cargo test
```

`pre-commit` is configured but is **not** installed as a local git hook, so
committing runs nothing. Run the checks above yourself before committing.

## Invariants that will fail CI if you break them

These encode decisions, not style. Read the linked source before working around one.

- **Motion IR is the single source of motion math.** `tests/test_motion_ir_invariants.py`
  greps the shipped packages and fails if a second implementation of the nominal
  time model or a second G-code parser reappears. A deliberate move updates the
  expected home in that test; a duplicate is a bug.
- **Toolpath output is regression-gated.** `examples/*/expected.gcode` are byte
  goldens for the cylinder paths. Curved-surface examples (cone, Von Kármán) are
  gated by a tolerance-based equivalence harness instead, because transcendental
  coordinates are not bit-stable across platforms. Never regenerate a golden to
  make a test pass — if output changed, justify why.
- **`.wind` changes must be additive.** New capability is an optional field plus a
  `schemaVersion` minor bump; existing files must keep planning identically. The
  `conformance/` corpus pins the accept/reject contract.
- **Generated artifacts must be committed in sync.** CI regenerates and diffs
  `fiberpath_gui/openapi.json`, `src/api/schema.ts`, `schemas/wind-schema.json`
  and `src/types/wind-schema.ts`. After changing API or schema models run
  `npm run api:generate` and `npm run schema:generate` in `fiberpath_gui`.

## Conventions

- Conventional Commits (`type(scope): subject`, imperative, ≤72 chars).
- No AI attribution in commits or PR bodies — no co-author trailer, no
  "Generated with" footer, no session URL.
- Tests mirror source structure.
- Keep planning machine-agnostic: machine specifics belong in a `MachineProfile`
  or the post-processor, never in pattern logic.
- Releases follow [`docs/development/release-process.md`](docs/development/release-process.md).
  Direction and staging live in [`docs/development/roadmap.md`](docs/development/roadmap.md);
  update it when a release moves a stage.

## Constraints

- Do not commit secrets or credentials.
- Do not commit build or scratch output — `temp/` and `dist/` are gitignored; keep
  throwaway files there rather than adding new ignore rules.
- Do not add a runtime dependency without justification — the engine's runtime set
  is deliberately small.
- Hardware-touching behaviour (streaming, timing calibration) is validated against
  a real machine. Issues labelled `needs-hardware` are not desk-completable.
