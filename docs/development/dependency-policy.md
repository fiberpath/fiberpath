# Dependency Update Policy

## Purpose

This policy defines how FiberPath tracks, triages, and upgrades dependencies across Python, Node/Tauri, Rust, and GitHub Actions workflows.

## Scope

Applies to:

- Python dependencies in `pyproject.toml` and `uv.lock`
- Node dependencies in `fiberpath_gui/package.json` and `fiberpath_gui/package-lock.json`
- Rust dependencies in `fiberpath_gui/src-tauri/Cargo.toml` and `fiberpath_gui/src-tauri/Cargo.lock`
- GitHub Actions dependencies in `.github/workflows/*.yml`

## Cadence

- Patch updates: monthly
- Minor updates: quarterly review window
- Major updates: dedicated release slot (for example, a migration-focused release like v0.7.0 or similar)

## Ownership

- Primary triage owner: maintainers responsible for the active release planning document in `docs/development/feature-backlog.md`
- PR review owner: area maintainer for the affected ecosystem
- Security escalation owner: release manager on current target milestone

## Triage SLAs

- Critical vulnerabilities: initial triage within 48 hours
- High vulnerabilities: triage and mitigation plan within 7 days
- Moderate vulnerabilities: scheduled into next planned maintenance slot
- Low vulnerabilities: best-effort backlog prioritization

## Update Classification

- Low risk: patch updates and non-breaking minor updates without migration notes
- Medium risk: minor updates with behavior changes, tooling/runtime defaults, or lockfile churn with integration risk
- High risk: major updates, breaking API changes, migration guide required, or observed test/build regressions

## Exception Handling

When an update is deferred:

1. Record package, current version, candidate version, and reason in the active roadmap.
2. Assign a target release for re-evaluation.
3. Add temporary ignore rules only when they reduce noise and are documented.
4. Remove ignore rules once the deferred item is re-scoped into active execution.

## Required Tooling

- Python: `uv`, `pip-audit`
- Node: `npm audit`
- Rust: `cargo audit`
- Automation: Dependabot (`.github/dependabot.yml`) and scheduled dependency audit workflow (`.github/workflows/dependency-audit.yml`)

## CI and Artifact Requirements

- Dependency audit workflow must run on PRs to `main`, pushes to `main`, and weekly schedule.
- PRs must not merge with unresolved high/critical findings in Node or Cargo scans.
- Release workflow must publish SBOM artifacts for Python, Node, and Rust.

## Documentation and Traceability

- Roadmap and release source of truth: `CHANGELOG.md`, `docs/development/roadmap.md`, and `docs/development/feature-backlog.md`.
- Release-level summary: `CHANGELOG.md`.
- CI architecture reference: `docs/development/ci-cd.md`.
