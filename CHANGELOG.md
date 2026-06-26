# Changelog

All notable changes to this project are documented in this file.

The format is based on Keep a Changelog, and this project follows semantic versioning.

<!-- markdownlint-disable MD024 -->

## [Unreleased]

### Changed

- The API compute routes are now **body-only**: `POST /plan` and `POST /validate` take a wind definition in the request body (the same JSON as a `.wind` file), and `POST /simulate` takes a G-code program (`{"gcode": "..."}`). They no longer accept filesystem paths, so the path-allow-list policy and its `FIBERPATH_API_ALLOWED_ROOTS` setting are gone. `POST /plan` now returns the generated program directly in the `gcode` field instead of writing a `.gcode` file and returning its path. This makes the service stateless and safe to run as a local sidecar.
- Compute results (`/plan`, `/simulate`) now share **one versioned wire schema** (`fiberpath/wire.py`): every response carries a `schemaVersion` and all fields are camelCase (e.g. `commandCount`, `cumulativeTimeSeconds`, `estimatedTimeSeconds`). The wire format is decoupled from the internal engine dataclasses so it is no longer hostage to engine refactors, and the per-route hand-rename DTOs are gone.
- The generated `.wind` JSON Schema now carries a canonical versioned `$id` (`https://fiberpath.org/schemas/wind/1.0/wind.schema.json`) and is produced deterministically from the `WindDefinition` model. The orphaned second generator (`scripts/export_schema.py`) is removed, leaving `scripts/generate_schema.py` as the single source, and a CI drift gate now fails if the committed `wind-schema.json` or its generated TypeScript types drift from the model.
- The desktop app now runs the API as a **bundled local sidecar**: the Tauri shell spawns and supervises a frozen `fiberpath-api` server (ephemeral `127.0.0.1` port, restart-on-crash, killed on exit) and the GUI's compute operations (export, preview, validate) call it through the generated typed client instead of shelling out to the CLI. The hand-maintained GUI response types are retired in favour of the OpenAPI-generated ones. (Driving a Marlin controller still uses the existing path; its REST surface lands with #190/#199.)
- The Tauri shell is now thinner: the dead compute commands it no longer uses (`plan_wind`, `simulate_program`, `plot_preview`, `plot_definition`, `validate_wind_definition`) and their CLI-subprocess/temp-file machinery are removed (~290 lines), now that compute goes through the sidecar. The CLI subprocess and `stream_program` remain only for the Marlin serial path, pending its REST surface (#190/#199).

### Added

- `POST /plot` renders an unwrapped 2D preview of a G-code program (`{"gcode": "..."}`) and returns `image/png` bytes.
- A typed TypeScript client for the local API, generated from the API's OpenAPI spec (`openapi-typescript` types + an `openapi-fetch` wrapper in `fiberpath_gui/src/api/`). A committed `fiberpath_gui/openapi.json` is the codegen input, and a CI drift gate regenerates both and fails if the spec or client diverges from the live API — so the frontend's view of the backend can no longer silently rot.
- The compute routes (`/plan`, `/simulate`, `/validate`, `/plot`) now **declare their `400` response** (`{"detail": "..."}`) in the OpenAPI spec. Previously only `200`/`422` were documented even though the engine maps invalid-but-well-formed input to a 400, so the generated client now types that error body instead of inferring it.

### Removed

- The API streaming route (`POST /stream/`) has been removed; driving a Marlin controller is being reworked into a dedicated REST surface (see issues #190 and #199).

### Fixed

- The bundled `fiberpath` CLI (and the new API sidecar) are now found on Linux/macOS desktop builds. Resources from the `../bundled-*/*` globs land under a `_up_/` subdirectory on **every** platform, but the lookup only checked it on Windows — so installed Linux/macOS apps reported "CLI Backend Unavailable" and the sidecar failed to start. The lookup now checks `_up_/` first on all platforms.
- The `.wind` file `schemaVersion` is no longer pinned to the exact string `1.0`. It now accepts any `1.x` minor (additive evolution); an absent value is treated as the legacy `1.0`, and an incompatible major (`2.0`+) is rejected. `schemaVersion` is now a native field on the `WindDefinition` model (`pattern: ^1\.\d+$`) — the single source of truth — so the backend validates it on load and the schema generator no longer needs to inject a `const: "1.0"`. The GUI's `.wind` validator was relaxed from `z.literal("1.0")` to the same `1.x` pattern.

## [0.7.4] - 2026-06-25

### Fixed

- Marlin desktop commands no longer hang forever if the underlying CLI subprocess dies or emits a non-JSON line: when the response reader stops, in-flight requests are failed (the command returns an error) instead of leaving the UI spinner stuck permanently.
- Desktop preview/validate temp files now use process- and counter-unique names, fixing rare collisions when commands fired in the same millisecond could delete or clobber each other's temp file (intermittent "file not found" / corrupted preview).
- The Marlin desktop integration now recovers if its helper subprocess dies: a dead process is detected and respawned on the next command instead of reusing it forever, and the subprocess is killed on app shutdown so it no longer lingers as an orphan holding the serial port open.
- Helical layer editor and save-gate validation now match the planner's bounds, so the editor no longer accepts values the backend rejects with a 422: `lockDegrees`, `leadInMM`, and `leadOutDegrees` must be positive (were allowed to be `0`), `skipIndex` must be a positive integer (the save gate allowed `0`), and the wind angle is constrained to `[1°, 89°]` (was `(0°, 90°)`; the engine clamps to `[1, 89]` because `90°` gives `cos = 0`).
- Helical layer geometry hint no longer renders "not divisible by pattern number (NaN)" while the Pattern Number field is mid-edit (emptied to `NaN`); no hint is shown until the field holds a valid positive integer.
- The streaming API (`POST /stream/`) now returns 400 for empty/whitespace-only G-code instead of 502; an empty program is a client error, not an upstream device failure (502 is reserved for genuine transport errors).
- Simulating a G-code path that is a directory or non-UTF-8/binary file now returns a 4xx (API `/simulate/from-file`) or a clean usage error (CLI `simulate`/`plot`/`stream` reject directories) instead of an HTTP 500 / raw `IsADirectoryError`/`UnicodeDecodeError` traceback.
- Loading a wind definition that is a directory, an unreadable file, or non-UTF-8/binary content now reports a clean error instead of crashing. Previously these raised an unmapped `IsADirectoryError`/`UnicodeDecodeError`, surfacing as an HTTP 500 from the API (`/plan/from-file`, `/validate/from-file`) or a raw traceback from the CLI; they are now mapped to the standard `WindFileError` (4xx / clean CLI message).
- `fiberpath plan --output <dir>/<file>.gcode` into a directory that does not exist now creates the parent directories instead of crashing with a `FileNotFoundError` traceback (matching the existing `plot` behavior). `write_gcode` creates the destination's parent directory.
- A helical layer whose `leadInMM` is greater than or equal to the mandrel `windLength` is now rejected during planning. Previously it passed validation and generated G-code that drove the carriage off the end of the mandrel into negative coordinates (inverting the main-pass rotation), risking an end-stop collision.
- Non-finite numeric inputs (`NaN`, `Infinity`) in a `.wind` file are now rejected at load instead of being silently accepted. Previously a `NaN` value could be emitted into generated G-code as a literal `Anan` axis word, and an `Infinity` geometry value crashed the planner with an uncaught `OverflowError` (HTTP 500 / CLI traceback).
- Helical layer editor no longer crashes the app ("Maximum call stack size exceeded") when the Pattern Number or Skip Index field is emptied. The emptied field became `NaN`, and the cross-field coprime check recursed forever in `gcd()`; the check now skips non-integer values and the field reports its own validation error instead.

## [0.7.3] - 2026-06-25

### Changed

- **Project moved to the [`fiberpath` GitHub organization](https://github.com/fiberpath).** The repository, issue tracker, and PyPI trusted publisher now live under `fiberpath/fiberpath`. `pip install fiberpath` is unchanged.
- Documentation now lives at **[fiberpath.org](https://fiberpath.org)** (FiberPath docs at `fiberpath.org/fiberpath`), built and published from the `fiberpath/fiberpath.github.io` hub. This repository now contains only docs content under `docs/`; the MkDocs configuration, site assembly, and publishing moved to the hub, and docs are validated on every PR via the org's shared `docs-validate` reusable workflow.
- The required `CI Check` status now runs on every pull request (no path filter) so it always reports and never leaves a PR stuck pending; an inner change-detection job still gates the heavy backend/GUI/docs jobs by path.
- Release notes are now produced by GitHub-native release-note generation instead of `git describe`, fixing the "Initial release." text that appeared on prior releases.

### Fixed

- Unified helical-layer defaults via a shared `HELICAL_DEFAULTS` constant so the CLI, API, and GUI agree on the same values.

### Removed

- Retired `TODO.md` in favor of tracked GitHub issues.

### Documentation

- Added a development roadmap and relocated the feature backlog under `docs/development/`.

### Dependencies

- Migrated dependency automation from Dependabot to org-shared **Renovate** (preset `github>fiberpath/renovate-config`); Dependabot security alerts/updates remain enabled.
- GitHub Actions: `actions/setup-node` v6, `actions/cache` v6.
- npm: `@types/node` 26.0.1, `stylelint` 17.14.0.

## [0.7.2] - 2026-06-24

### Security

- Hardened API path policy (`enforce_input_path_policy`) to reject absolute paths (POSIX `/`, Windows drive `C:\`, UNC `\\`), NUL bytes, `..` traversal segments, and empty/whitespace inputs with 400 before any filesystem access. Resolved CodeQL alert #9 ("Uncontrolled data used in path expression").
- Patched `starlette` CVE-2026-48710 (BadHost) by upgrading to a fixed release.
- Cleared the GUI dev-tree advisories `js-yaml` (GHSA-h67p-54hq-rp68, merge-key DoS → 4.2.0) and `undici` (GHSA-vmh5-mc38-953g and related → 7.28.0). Both are dev-only; the shipped application is unaffected.
- Bumped `rand` to 0.8.6 (GHSA-cq8v-f236-94qc). A residual, build-time-only `rand` 0.7.3 is pinned upstream in the Tauri toolchain with no available fix and is tracked in `TODO.md`.

### Changed

- API file endpoints now require relative paths; the configured `FIBERPATH_API_ALLOWED_ROOTS` controls which directories they resolve against.
- Rebuilt user-supplied paths from validated components (`Path(*parts)`) instead of passing raw input to `Path()`, breaking the taint chain for static analysis.
- API plan/simulate routes map core-engine input errors (`PlanningError`, `SimulationError`) to HTTP 400 via centralized exception handlers instead of surfacing them as 500s, and `/stream` caps the G-code payload at 10 MB.
- Routed streaming `[DEBUG]`/`[ERROR]` output through the `logging` module instead of `print(..., file=sys.stderr)`, so a normal run is quiet by default while the stdout JSON protocol is unchanged.
- Upgraded Tauri to 2.11 (Cargo + npm aligned) and refreshed CI actions.

### Fixed

- `MarlinStreamer` transport guards now raise `StreamError` instead of `assert`, so they behave identically under `python -O` rather than degrading to a `None` dereference.
- Tauri `plot_definition`, `plot_preview`, and `validate_wind_definition` no longer leak temporary `.wind`/`.gcode`/`.png` files on error paths; an RAII guard removes them on every exit.

### Removed

- Removed the unused `fiberpath/geometry/` stub module (dead code advertising non-cylindrical capability that does not exist; the roadmap is documented instead).
- Removed dead branches in `planning/layer_strategies.py` (a no-op `build_layer_summary` conditional and an unreachable circuit-divisibility guard superseded by upstream validation).

### Added

- `tests/api/test_path_policy.py` — 18 dedicated tests covering all rejected input classes (NUL bytes, POSIX absolute, Windows drive/UNC, `..` traversal with forward and backslash separators, empty/whitespace, absolute-inside-root) and accepted cases (bare filename, nested relative, multiple roots, single-dot normalisation).
- Integration-level rejection tests in `test_plan_route.py` and `test_simulate_route.py` for absolute-path and traversal inputs.
- Tests for API error-to-4xx mapping, `MarlinStreamer` transport guards (including a `python -O` subprocess check), streaming logging staying quiet by default, and the Tauri temp-file cleanup guard.

### Documentation

- Aligned the README and architecture docs with the implemented scope (cylindrical mandrels; hoop/helical/skip layers), framed geodesic/curved-surface support as roadmap, and removed the stale `examples/complex_surface/` placeholder.

### Dependencies

- Tooling/CI: `astral-sh/setup-uv` v8.2.0 (Node 24), `codecov/codecov-action` v7, `actions/checkout` v7.
- Python (uv): `starlette` 1.3.1, `urllib3` 2.7.0, `idna` 3.15, `pymdown-extensions` 10.21.3.
- npm: `@types/node` 26, `lucide-react`, `fast-uri` 3.1.2, plus the npm prod and dev minor-patch dependency groups.
- Cargo: the cargo minor-patch dependency groups.

## [0.7.1] - 2026-04-16

### Added

- Expanded GUI test suite to 614 tests across 53 files via three RTL sprint phases covering pure components, store-coupled components, hooks, canvas rendering, CLI health, and stream branches (79.81% line / 91.17% branch / 87.73% function coverage).

### Fixed

- Fixed Python audit CI failure caused by CVE-2025-71176 in `pytest 9.0.2`; bumped to `pytest 9.0.3`.
- Fixed Windows E2E smoke test failure caused by WiX MSI two-pass CAB extraction not being handled in `extract-package-runtime.ps1`.
- Fixed Windows E2E smoke test failure where accumulated MSI artifacts caused the oldest version to be selected instead of the newest; extraction now sorts by `LastWriteTime` descending.
- Fixed `cargo audit` CI failure when `cargo-audit` was already installed (`exit 101`); guarded install with a version check.
- Fixed `ci-check.yml` required-status gate never posting on `scripts/ci/**` and workflow changes; broadened path filter to `scripts/**` and `.github/workflows/**`.

### Changed

- Extended `dependency-audit.yml` and `gui-packaging.yml` to trigger on pull requests, not only post-merge pushes.
- Improved `find-bundled-cli.ps1` with a wider path regex and full diagnostics output on failure.

### Dependencies

- Bumped `pillow` (uv).
- Bumped `tokio` (Cargo, two patches).
- Bumped npm prod and dev minor-patch dependency groups.
- Bumped `react-zoom-pan-pinch` to 4.0.3.
- Bumped `actions/upload-pages-artifact` from 4 to 5.
- Bumped multiple Cargo minor-patch dependency groups.

### Internal

- Synchronized release version metadata across Python (`pyproject.toml`, `uv.lock`), npm (`package.json`, `package-lock.json`), and Tauri (`Cargo.toml`, `Cargo.lock`, `tauri.conf.json`).

## [0.7.0] - 2026-04-08

### Added

- Added GUI bundle-budget enforcement (`npm run perf:bundle`) with CI gating and machine-readable report output.
- Added stricter repository hygiene checks through pre-commit integration for Python lint/format and GUI type/CSS validation.

### Changed

- Completed the XAB-only axis cutover across core planning, simulation, plotting, CLI, API, and GUI export workflows.
- Removed legacy XYZ axis-format options from built-in interfaces and aligned fixtures/examples with XAB defaults.
- Simplified GUI component/style surfaces by removing dead CSS/component paths and tightening shared editor/form boundaries.
- Hardened packaging/CI helper scripts for bundled CLI discovery and cross-platform release reliability.

### Fixed

- Fixed regression tests and fixtures that drifted during axis-format migration, including layer-strategy and plot-signature expectations.
- Fixed pre-commit Ruff hook compatibility by migrating from the legacy `ruff` alias to `ruff-check`.

### Documentation

- Updated release-facing docs to position v0.7.0 as current and reflect XAB-only behavior in user/developer guides.
- Documented helical coverage compatibility caveats and follow-up validation/schema hardening scope in roadmap/release notes.

### Internal

- Synchronized release version metadata across Python (`pyproject.toml`, `uv.lock`), npm (`package.json`, `package-lock.json`), and Tauri (`Cargo.toml`, `Cargo.lock`, `tauri.conf.json`).

## [0.6.2] - 2026-04-07

### Added

- Added stream-domain action hooks (`useConnectionActions`, `useStreamingActions`, `useManualCommandActions`) and consolidated stream feedback helpers for consistent toast/log behavior.
- Added focused integration coverage for stream lifecycle transitions in `streamLifecycle.test.ts`.
- Added shared React UI primitives/utilities including `LayerNumericField`, `numericFields`, `helicalValidation`, `usePreviewGeneration`, and `BaseDialog`.

### Changed

- Completed the v0.6.2 React hotspot cleanup roadmap (Waves A-D), including StreamTab domain decomposition, menu/file orchestration cleanup, and canvas/editor component simplification.
- Standardized store boundaries by moving `projectStore` into `src/stores` and removing StreamTab wrapper path indirection.
- Updated release-facing docs to reflect v0.6.2 as the current release.

### Fixed

- Removed remaining imperative `alert(...)` UI fallback paths in favor of app-level notifications.
- Eliminated final inline-style residue in streaming UI components to keep styling maintainable and class-driven.

## [0.6.1] - 2026-04-07

### Added

- Automated `useTheme` hook regression tests covering system preference fallback, persisted manual overrides, and reset-to-system behavior.

### Changed

- Completed GUI styling simplification rollout with token-first cleanup, reduced style entropy, and updated styling guidance to match implementation reality.
- Updated release-facing docs to reflect v0.6.1 as the current release and refreshed versioned troubleshooting examples.

### Fixed

- Removed dead GUI dependencies (`@radix-ui/react-dropdown-menu`, `@radix-ui/react-menubar`, `clsx`) from package metadata.
- Resolved stylelint compliance issues in `StreamTab.css` (`currentcolor` keyword casing and media range notation syntax).
- Synchronized release version metadata across Python, npm, Cargo, and Tauri config to eliminate cross-stack version drift.

## [0.6.0] - 2026-04-06

### Added

- Comprehensive GUI E2E smoke test workflow (`gui-e2e-smoke.yml`) with cross-platform matrix validation (Windows/macOS/Ubuntu).
- Package artifact presence validation for all OS distributions (`.msi`/`.exe`, `.deb`/`.AppImage`, `.dmg`/`.app`).
- Bundled CLI resolution and smoke execution on packaged outputs; validates `validate`, `plan`, and `plot` CLI commands from frozen binaries.
- Hash-based bundled CLI discovery for Windows MSI streams with automatic materialization to executable format.
- Reference CLI artifact download and management for E2E validation comparisons.

### Changed

- E2E smoke workflow now enforces packaged CLI validation on all platforms with hard-fail on bundled CLI discovery (no silent fallback).
- Windows bundled CLI discovery supports structural path matching and hash-based fallback for opaque MSI stream extraction scenarios.
- Improved artifact inspection and debugging output in E2E workflows for faster triage of packaging regressions.

### Fixed

- Resolved Ubuntu E2E broken-pipe error in artifact listing under `set -euo pipefail` (replaced `find | head -20 || true` with `find | awk 'NR <= 20'`).
- Restored macOS bundled CLI executable bit preservation after artifact download by adding `chmod +x` in CLI source selection.
- Fixed Windows E2E hang by replacing indefinite `msiexec /a` admin-install with reliable 7-zip extraction (with msiexec fallback).
- CLI smoke tests now use `--help` capability check instead of unsupported `--version` flag.
- Windows MSI stream CLI files now properly materialized to `.resolved-bundled-cli/fiberpath.exe` for PowerShell execution.

## [0.5.4] - 2026-03-23

### Added

- Dependabot automation for pip, npm, cargo, and GitHub Actions with managed PR limits and ignore controls for deferred version lanes.
- New dependency security workflow (`dependency-audit`) that gates Python, Node, and Rust audits and uploads machine-readable reports.
- Release SBOM generation/upload for Python, Node, and Rust artifacts as part of the GitHub release pipeline.
- Published dependency policy covering cadence, ownership, CVE SLAs, and exception handling.

### Changed

- Completed deferred high-risk dependency migrations from v0.5.3, including React 19, Vite 8, Vitest 4, Zod 4, stylelint 17, thiserror 2, and which 8.
- Aligned GUI runtime/tooling constraints to Node 24 and npm 11 with CI parity in shared setup actions.

### Fixed

- Resolved Python audit vulnerabilities by upgrading `fonttools` and `urllib3` to patched versions.
- Removed optional GUI test UI dependency path that introduced unresolved upstream audit exposure.

## [0.5.3] - 2026-03-22

### Added

- Formal dependency audit matrix and risk-bucket staging workflow across Python, Node/Tauri, and Cargo ecosystems.
- Explicit deferral track for high-risk dependency migrations into v0.5.4.

### Changed

- Updated low-risk Python dependencies and toolchain packages to current compatible releases.
- Updated low-risk GUI/npm dependencies while preserving framework-major boundaries.
- Synchronized release metadata and documentation references for the v0.5.3 release line.

### Fixed

- Restored stable local development environment bootstrap guidance by clarifying extras-based `uv sync` usage for test/dev workflows.
- Resolved Tauri npm/crate parity drift from prior lockfile changes and revalidated packaging behavior.

## [0.5.2] - 2026-03-22

### Added

- Strict helical layer divisibility validation to prevent silent layer omission when computed circuits are incompatible with `patternNumber`.
- API route path policy enforcement for planning, validation, and simulation file operations.
- CSS variable guard script integrated into GUI CI to fail unresolved token references.
- Expanded regression coverage for strict helical validation behavior across planning, simulation, and visualization tests.

### Changed

- Clarified winding terminology in docs and in-app tooltips for helical and skip parameters (`windAngle`, `patternNumber`, `skipIndex`, lock/lead settings).
- Consolidated remaining cross-platform validation and E2E execution work into the v0.6.0 roadmap plan.

### Fixed

- GUI contrast regressions in dialogs and status surfaces caused by missing token aliases and legacy button style drift.
- Legacy visualization test expectations that assumed invalid helical fixtures would still plan successfully.

## [0.5.1] - 2026-03-22

### Added

- Bundled Python CLI in desktop distribution for Windows release path.
- Release workflow hardening for tagged packaging and publishing.

### Changed

- Windows packaging and upgrade-path validation for bundled CLI behavior.

## [0.5.0] - 2026-03-22

### Changed

- Marlin streaming pause/cancel behavior refinements.
- Documentation overhaul and workflow cleanup.

## Prior (To Organize)

- v0.1.0
  - Core planning engine, geometry, simulation baseline, and initial CLI/API hardening.
- v0.2.0
  - GUI rehaul and Tauri/React workflow maturation.
- v0.3.0
  - Quality/stability pass, testing expansion, error handling, and CI/CD organization.
- v0.4.0
  - Tabbed interface and Marlin streaming integration maturity.
