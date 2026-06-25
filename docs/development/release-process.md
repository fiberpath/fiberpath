# Release Checklist

## Pre-Release

- [ ] Run all linters, type checkers, and formatters locally:
  - **Python Backend:** `uv run ruff check` (linting), `uv run ruff format` (formatting), `uv run mypy` (type checking)
  - **TypeScript/React GUI:** `cd fiberpath_gui && npm run lint` (TypeScript check), `npm run lint:css` (CSS linting)
  - **Rust Backend:** `cd fiberpath_gui/src-tauri && cargo clippy` (linting), `cargo fmt --check` (formatting)
- [ ] Run all test suites locally:
  - **Python:** `uv run pytest -v`
  - **GUI:** `cd fiberpath_gui && npm test`
- [ ] All CI workflows passing on target branch (backend-ci, gui-ci, gui-packaging)
- [ ] All planned features from roadmap completed and tested
- [ ] Manual end-to-end testing on Windows/macOS/Linux (GUI streaming, planning workflows, CLI commands)

## Version Updates

Update version strings in these files (single source of truth for each stack):

- [ ] **`pyproject.toml`** – Line 7: `version = "X.Y.Z"` (Python packages read from this)
- [ ] **`fiberpath_gui/src-tauri/Cargo.toml`** – Line 3: `version = "X.Y.Z"` (Tauri/Rust reads from this)
- [ ] **`fiberpath_gui/src-tauri/tauri.conf.json`** – Line 10: `"version": "X.Y.Z"` (Tauri bundle metadata)
- [ ] **`fiberpath_gui/package.json`** – Line 3: `"version": "X.Y.Z"` (npm package metadata)
- [ ] **`README.md`** – Version badge references current release (`version-X.Y.Z`)
- [ ] **`docs/index.md`** – Line 5: Download link version reference

**Note:** `fiberpath_api/main.py` and `AboutDialog.tsx` auto-read from `pyproject.toml` and `Cargo.toml` respectively.

## Lock Files

Refresh dependency locks after version updates:

- [ ] **`uv.lock`** – Run `uv lock` to refresh Python dependencies
- [ ] **`fiberpath_gui/package-lock.json`** – Run `cd fiberpath_gui && npm install`
- [ ] **`fiberpath_gui/src-tauri/Cargo.lock`** – Run `cd fiberpath_gui && npm run tauri build` (auto-updates)

## Documentation

- [ ] Create/update `CHANGELOG.md` with notable changes since last release
- [ ] Review and update feature documentation in `docs/` for any changed behavior
- [ ] Update `docs/index.md` "What's New" section with release highlights
- [ ] Verify all code examples and CLI commands in docs reflect current syntax
- [ ] Check for any outdated version references in documentation

### CHANGELOG Maintenance Rules

- **Owner:** The release manager for the target milestone owns final changelog curation for that release cut.
- **Timing:** Update `## [Unreleased]` during development as PRs merge; before release, move finalized bullets into the new `## [X.Y.Z] - YYYY-MM-DD` section.
- **Required section order:** `Added`, `Changed`, `Fixed`, `Documentation`, `Internal` (omit empty sections).
- **Entry format:** One behavior-oriented bullet per change (user impact first, implementation detail second if needed).
- **Pre-release check:** No placeholder bullets (`TBD`, `WIP`, `misc`) in release-bound sections.

## Quality Checks

- [ ] Verify Python package builds cleanly: `uv build` (check `dist/` output)
- [ ] Verify GUI builds successfully: `cd fiberpath_gui && npm run build`
- [ ] Test GUI installers on target platforms (download workflow artifacts or build locally with `npm run tauri build`)
- [ ] Smoke test core workflows:
  - **Planning:** `fiberpath plan examples/simple_cylinder/input.wind -o test.gcode`
  - **Simulation:** `fiberpath simulate test.gcode`
  - **Plotting:** `fiberpath plot test.gcode --output test.png`
  - **Streaming (dry-run):** `fiberpath stream test.gcode --dry-run`
  - **API:** `uvicorn fiberpath_api.main:app` (verify starts without errors)
- [ ] Test GUI application launches and loads example files correctly

## Release Workflow

- [ ] Push all version updates and documentation to main branch
- [ ] Wait for all CI checks to pass
- [ ] Navigate to GitHub Actions → **Release** workflow
- [ ] Click "Run workflow" and input version (e.g., `0.3.14`)
- [ ] Select pre-release checkbox if applicable
- [ ] Monitor workflow execution:
  - Validation checks version format and pyproject.toml match
  - Creates git tag and GitHub release
  - Publishes Python package to PyPI via trusted publishing
  - Builds Tauri installers for Windows/macOS/Linux
  - Attaches installers to GitHub release

## Post-Release Verification

- [ ] Verify GitHub release page has all artifacts attached (`.msi`, `.dmg`, `.deb`, `.AppImage`)
- [ ] Verify PyPI listing: https://pypi.org/project/fiberpath/
- [ ] Test installation from PyPI: `pip install fiberpath==X.Y.Z`
- [ ] Download and test one GUI installer per platform
- [ ] Verify documentation site updated with new version: https://fiberpath.github.io/fiberpath
- [ ] Update any external links or announcements referencing old version
- [ ] Create PR to bump version to next development version (e.g., `0.7.1-dev`)

## Notes

- **Version Format:** Use semantic versioning (`X.Y.Z` or `X.Y.Z-rc.N` for pre-releases)
- **Branch Strategy:** Release from `main` branch only
- **CI Automation:** Release workflow orchestrates PyPI publish, GUI packaging, and artifact uploads
- **Rollback:** If issues found post-release, create hotfix branch and follow checklist with patch version
