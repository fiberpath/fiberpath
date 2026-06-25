# Contributing to FiberPath

Thanks for investing time in the project! This guide explains how to set up a development environment, follow the coding standards, and get changes merged smoothly.

## Development Environment

1. **Install prerequisites:** Python 3.11+, Node.js 24.x + npm 11.x (for the GUI), Rust toolchain (for Tauri), and `uv` for deterministic Python environments.
2. **Create a virtual environment:**

   ```sh
   uv venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   ```

3. **Install dependencies:**

   ```sh
   uv pip install -e .[dev,cli,api]
   ```

4. **Optional extras:**
   - GUI: `cd fiberpath_gui && npm install`

Documentation is plain Markdown — no local tooling is needed to edit it. The
site (theme, build, publishing) is owned by
[`fiberpath/fiberpath.github.io`](https://github.com/fiberpath/fiberpath.github.io);
to preview the full rendered site, build it from that repo.

## Coding Standards

- **Formatting & linting:** Ruff enforces style, imports, and best practices. Run `uv run ruff check` before committing.
- **Type checking:** MyPy runs in strict mode across `fiberpath`, `fiberpath_cli`, and `fiberpath_api`. Use `uv run mypy` and prefer adding annotations rather than suppressions.
- **Tests:** `uv run pytest` exercises all unit/integration suites. Add targeted tests for new planner logic, CLI behavior, or API endpoints.
- **Docs:** Keep `docs/*.md` in sync with feature work. Significant planner or simulator changes usually deserve updates to `docs/architecture.md` or `docs/planner-math.md`.
- **Dependency hygiene:** Follow `docs/development/dependency-policy.md` for cadence, SLA, and defer/exception handling.
- **Commit-time automation:** Install and use pre-commit hooks (`pre-commit install`) so baseline Python and GUI checks run before each commit.

## Pull Request Checklist

1. `pre-commit run --all-files`
2. `uv run mypy`
3. `uv run pytest`
4. Update documentation and add changelog entries in `CHANGELOG.md` when behavior changes.
5. Ensure commits are scoped and descriptive. Squash locally if needed before opening the PR.

CI will enforce the same Ruff/MyPy/Pytest pipeline on every PR. If a job fails, reproduce locally with the matching `uv run …` command.

## CI/CD Workflows

FiberPath uses GitHub Actions with specialized workflows:

- **backend-ci.yml** - Python linting (Ruff), type checking (MyPy), testing (pytest on 3 OS)
- **gui-ci.yml** - GUI type/lint checks (tsc, stylelint, CSS var guard), testing (Vitest), building (Vite), Rust checks (fmt + clippy)
- **dependency-audit.yml** - Scheduled and PR-gated dependency security audit (pip-audit, npm audit, cargo audit)
- **gui-packaging.yml** - Tauri installer creation for Windows/macOS/Linux
- **backend-publish.yml** - PyPI publishing with trusted publishing (releases only)
- **release.yml** - Coordinated release orchestration (manual dispatch)

All workflows use reusable composite actions (`.github/actions/`) for setup steps. See [ci-cd.md](ci-cd.md) for complete architecture documentation.

**Branch Triggers:**

- CI workflows (backend-ci, gui-ci) run on `main`, `vX.Y.Z-dev`, and all PRs
- Packaging and publishing run on releases or manual dispatch

Documentation is **authored here** (this repo holds only the `docs/` Markdown — no MkDocs config). On every PR touching docs, the `CI Check`'s docs job calls a shared reusable workflow in the org's `.github` repo that builds these docs against the site's real config (`--strict`). The site is **owned and published by** [`fiberpath/fiberpath.github.io`](https://github.com/fiberpath/fiberpath.github.io), which serves them at <https://fiberpath.github.io/fiberpath>.

## Issue Triage & Discussion

- Use GitHub Issues for bugs and feature requests. Include `.wind` or `.gcode` snippets when relevant.
- Draft PRs are welcome for early feedback—link them to the corresponding issue for visibility.
- For larger architecture changes, open a discussion post or add a proposal document under `docs/proposals/` before writing code.

We appreciate every contribution, from typo fixes to new planner strategies. Thank you!
