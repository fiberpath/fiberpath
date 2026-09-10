# Release Checklist

## Pre-Release

- [ ] Run all linters, type checkers, and formatters locally:
  - **Python backend:** `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`
  - **Svelte GUI:** `cd fiberpath_gui && npm run lint` (`tsc --noEmit`), `npm run check:svelte`,
    `npm run lint:css`, `npm run lint:css:vars`
  - **Rust (Tauri shell):** `cd fiberpath_gui/src-tauri && cargo fmt --check`, `cargo clippy -- -D warnings`
- [ ] Run all test suites locally:
  - **Python:** `uv run pytest -v`
  - **GUI:** `cd fiberpath_gui && npx vitest run`
  - **Rust:** `cd fiberpath_gui/src-tauri && cargo test`
- [ ] All CI workflows passing on target branch (CI Check, Dependency Audit, GUI E2E Smoke)
- [ ] All planned features from roadmap completed and tested
- [ ] Manual end-to-end testing on Windows/macOS/Linux (GUI streaming, planning workflows, CLI commands)

## Version Updates

Update version strings in these files (single source of truth for each stack):

- [ ] **`pyproject.toml`** – Line 7: `version = "X.Y.Z"` (Python packages read from this)
- [ ] **`fiberpath_gui/src-tauri/Cargo.toml`** – Line 3: `version = "X.Y.Z"` (Tauri/Rust reads from this)
- [ ] **`fiberpath_gui/src-tauri/tauri.conf.json`** – Line 10: `"version": "X.Y.Z"` (Tauri bundle metadata)
- [ ] **`fiberpath_gui/package.json`** – Line 3: `"version": "X.Y.Z"` (npm package metadata)
- [ ] **`README.md`** – Version badge (`version-X.Y.Z`)
- [ ] **`docs/index.md`** – **two** references: the "Latest Release" link and the "What's New in vX.Y.Z"
  heading (the body of that card also needs rewriting for the new release — see Documentation below)

A quick way to catch a missed one, since every literal reference should move together:

```sh
git grep -n --fixed-strings "<previous version>" -- . ':!CHANGELOG.md'
```

The only expected false positives are npm `"node": ">=0.10.0"`-style engine constraints in
`package-lock.json`.

**Note:** `fiberpath_api/main.py` reads its version from installed package metadata
(`importlib.metadata.version("fiberpath")`), and `AboutDialog.svelte` reads it from Tauri at runtime, so
neither needs a manual edit.

## Lock Files

Refresh dependency locks after version updates:

- [ ] **`uv.lock`** – Run `uv lock` (rewrites the `fiberpath` self-version entry)
- [ ] **`fiberpath_gui/package-lock.json`** – Run `cd fiberpath_gui && npm install --package-lock-only`
  (`--package-lock-only` refreshes the lock without touching `node_modules`)
- [ ] **`fiberpath_gui/src-tauri/Cargo.lock`** – only the `fiberpath_gui` package entry changes, so edit
  that one `version = "X.Y.Z"` line directly. `npm run tauri build` also updates it, but a full bundle
  build is a slow way to change one line.

## Documentation

- [ ] Create/update `CHANGELOG.md` with notable changes since last release
- [ ] Review and update feature documentation in `docs/` for any changed behavior
- [ ] Update `docs/index.md` "What's New" section with release highlights — the heading version **and**
  the bullet list beneath it
- [ ] **Update `docs/development/roadmap.md` if this release moved a stage.** Check the stage table's
  Horizon column, the "Today FiberPath plans …" paragraph under North star, the surface-model line in the
  architecture diagram, and any section that still describes now-closed issues as future work.
- [ ] **Re-check `README.md`'s "Scope & roadmap" note.** It states which mandrel surfaces are supported and
  goes stale the moment a new surface ships.
- [ ] Verify all code examples and CLI commands in docs reflect current syntax
- [ ] Check for any outdated version references in documentation

> **Why the roadmap and README get their own line items:** both describe *capability*, not version numbers,
> so a version-string sweep will not catch them. 0.11.0 shipped with a README claiming non-cylindrical
> support was "planned but not yet implemented" — two releases after cones shipped — and a roadmap dating
> the just-released feature to "2027+".

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
- [ ] Verify the release body lists installer filenames that match the attached assets, and that **only**
  the current version's assets are attached (5 installers + 3 SBOMs). Stale installers from cached Tauri
  bundle output were a recurring defect, fixed in #120/#121.
- [ ] Verify documentation site updated with new version: <https://fiberpath.org/fiberpath>. The site lives
  in `fiberpath/fiberpath.github.io` and pulls this repo's `docs/` on a **daily 06:00 UTC cron** — there is
  no cross-repo push trigger, so to publish immediately run
  `gh workflow run deploy.yml -R fiberpath/fiberpath.github.io --ref main`.
- [ ] Update any external links or announcements referencing old version

**Do not** bump `pyproject.toml` to a `-dev` version after releasing. This project has never used
development-version suffixes (all 11 tags are plain `X.Y.Z`), and the Release workflow's `validate` job
hard-fails when `pyproject.toml` does not exactly equal the requested version — so a lingering `-dev`
suffix would block the next release.

## Notes

- **Version Format:** Use semantic versioning (`X.Y.Z` or `X.Y.Z-rc.N` for pre-releases)
- **Branch Strategy:** Release from `main` branch only
- **CI Automation:** Release workflow orchestrates PyPI publish, GUI packaging, and artifact uploads
- **Rollback:** If issues found post-release, create hotfix branch and follow checklist with patch version
