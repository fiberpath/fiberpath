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

## CI audit gating

One policy, enforced per ecosystem by `.github/workflows/dependency-audit.yml` (runs on PRs to
`main`, pushes to `main`, and weekly on Monday). The policy: **High/Critical vulnerabilities block;
everything else is reported but does not block.** Full dependency tree is in scope — dev and build
dependencies block the same as runtime ones, because the build chain produces the shipped binaries
(PyInstaller, Tauri bundler) and dev tools execute in CI.

| Ecosystem | Blocks CI | Reported, non-blocking | Mechanism |
| --- | --- | --- | --- |
| Rust (`cargo audit`) | vulnerability with CVSS ≥ 7.0 | CVSS < 7.0, unscored (loud `::warning::`), informational `unmaintained`/`unsound`/`yanked` | `scripts/ci/cargo_audit_gate.py` computes the CVSS 3.x base score from the RustSec vector and fails closed on a missing/malformed report |
| Python (`pip-audit`) | **any** advisory | — | pip-audit exit code. **Deliberately stricter**: pip-audit has no severity filter and PyPI/OSV advisories often carry no CVSS, so tiering is not implementable. Use the allowlist to accept a triaged Medium/Low. |
| Node (`npm audit`) | severity `high` or `critical` | `moderate`/`low` (silent — npm exits 0 below the level) | `npm audit --audit-level=high` exit code |

Allowlists — an accepted advisory is waived where the tool supports it, and every entry must carry
the advisory ID, a one-line justification, and a re-check trigger (an upstream event or date):

- **Rust:** `[advisories] ignore` in `fiberpath_gui/src-tauri/audit.toml` (create on first use).
- **Python:** `--ignore-vuln <ID>` flags on the pip-audit step in `dependency-audit.yml`.
- **Node:** no native ignore exists. On first need, gate via a small post-processor over
  `npm-audit.json` (mirror `cargo_audit_gate.py`); do not lower `--audit-level`.

Record the *reasoning* for each accepted advisory in this document (see
[Accepted advisories](#accepted-advisories-reasoning-record)); the *live state* is whatever the
latest audit run reports — its JSON reports upload as artifacts on every run, pass or fail.

**Enforcement note:** Dependency Audit is intentionally **not** a required status check (only
"CI Check" is). Advisories are published asynchronously — an unrelated PR must not be hard-blocked
because a CVE landed overnight. The gate is the weekly scheduled run plus PR-level visibility, and
the rule that a red audit is triaged (fix, allowlist, or tracked deferral) before further merges —
by convention, not branch protection.

**Remediation flow** when an audit goes red: Renovate's weekly lock-file maintenance (Mondays
before 06:00, ahead of the 07:00 audit) usually clears it; for urgent advisories bump directly
(`uv lock --upgrade-package <pkg>`, `cargo update -p <pkg>`, `npm audit fix`) — floor constraints
like `Pillow>=10.3` mean no Renovate update PR will exist, so the lockfile bump is the fix.
Dependabot security alerts remain enabled as the notification backstop.

## Exception Handling

When an update is deferred:

1. Record package, current version, candidate version, and reason in the active roadmap.
2. Assign a target release for re-evaluation.
3. Add temporary ignore rules only when they reduce noise and are documented.
4. Remove ignore rules once the deferred item is re-scoped into active execution.

## Accepted advisories (reasoning record)

This section records *why* an advisory is accepted so it is not re-triaged from scratch. It is
deliberately **not** an inventory — the live advisory state is the latest audit run's report
artifacts, and informational warnings never block by policy, so they only get an entry when the
reasoning is non-obvious. Remove an entry when its re-check trigger fires. **Do not block a release
solely for anything listed here.**

- **gtk3-rs binding stack — `unmaintained`/`unsound` warnings (RUSTSEC-2024-04xx series;
  `glib` 0.18 unsound iterator, RUSTSEC-2024-0429).** Tauri 2.x on Linux renders via GTK3, whose
  Rust bindings (`gtk`/`gdk`/`atk`/`gdk-pixbuf`/… 0.18) were declared unmaintained upstream in
  late 2024. They are structurally pinned by `tauri` — not upgradable from this repo. These are
  informational warnings (no CVSS), reported by every audit run and non-blocking under the gate.
  Re-check when Tauri moves off GTK3 on Linux (tracked upstream in tauri-apps/tauri).

Resolved entries for the record: `glib` GHSA-wrw7-89jp-8q8g and `rand` 0.7.3 GHSA-cq8v-f236-94qc
(both from the pre-2026 lockfile) no longer apply — the pinning chains left the tree with the
Tauri 2.x migration; `quick-xml` RUSTSEC-2026-0194/0195 (CVSS 7.5) were remediated by bumping
`plist` to 1.10.0 rather than accepted.

## Required Tooling

- Python: `uv`, `pip-audit`
- Node: `npm audit`
- Rust: `cargo audit` + the CVSS gate `scripts/ci/cargo_audit_gate.py` (unit-tested in `tests/ci/`)
- Automation: Renovate for version updates (org preset `github>fiberpath/renovate-config`, configured via `renovate.json`); Dependabot **security** alerts/updates remain enabled; scheduled dependency audit workflow (`.github/workflows/dependency-audit.yml`)

## CI and Artifact Requirements

- Dependency audit workflow must run on PRs to `main`, pushes to `main`, and weekly schedule.
- PRs must not merge over unresolved blocking findings in any ecosystem — High/Critical for Rust
  and Node, any advisory for Python — per [CI audit gating](#ci-audit-gating).
- Audit report artifacts (JSON) must upload on every run, pass or fail (`if: always()`).
- Release workflow must publish SBOM artifacts for Python, Node, and Rust.

## Documentation and Traceability

- Roadmap and release source of truth: `CHANGELOG.md`, `docs/development/roadmap.md`, and `docs/development/feature-backlog.md`.
- Release-level summary: `CHANGELOG.md`.
- CI architecture reference: `docs/development/ci-cd.md`.
