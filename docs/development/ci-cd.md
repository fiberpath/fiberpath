# CI/CD Workflow Architecture

## Overview

The FiberPath CI/CD system has been completely reorganized for v3 to:

- Eliminate redundancy and improve maintainability
- Establish clear naming conventions
- Separate concerns (CI vs packaging vs deployment)
- Add missing automation (PyPI publishing, coordinated releases)
- Reduce GitHub Actions minutes usage

## Structure

### Composite Actions (`.github/actions/`)

Reusable setup steps used across multiple workflows:

1. **setup-python/**
   - Sets up Python 3.11 with uv package manager
   - Creates virtual environment
   - Installs dependencies with caching
   - Configurable dependency groups
   - Used by: backend-ci, backend-publish

2. **setup-node/**
   - Sets up Node.js 24
   - Configures npm cache
   - Installs GUI dependencies
   - Used by: gui-ci, gui-packaging

3. **setup-rust/**
   - Sets up Rust toolchain
   - Configures cargo cache
   - Optionally installs Linux Tauri dependencies
   - Used by: gui-ci, gui-packaging

### Workflows (`.github/workflows/`)

#### CI Workflows (run on every push/PR)

**backend-ci.yml** - Python Backend CI

- Triggers: Push to main, PRs affecting Python code
- Jobs:
  1. Lint & Type Check (Ruff, MyPy)
  2. Test on ubuntu/macos/windows (pytest)
- Status: [![Backend CI](https://github.com/USER/fiberpath/actions/workflows/backend-ci.yml/badge.svg)](https://github.com/USER/fiberpath/actions/workflows/backend-ci.yml)

**gui-ci.yml** - GUI CI

- Triggers: Push to main, PRs affecting GUI code
- Jobs:
  1. Type/lint checks (TypeScript, Stylelint, CSS variable guard)
  2. Test & Build (Vitest, coverage, Vite build)
- Status: [![GUI CI](https://github.com/USER/fiberpath/actions/workflows/gui-ci.yml/badge.svg)](https://github.com/USER/fiberpath/actions/workflows/gui-ci.yml)

**Docs validation** - delegated, not local

- This repo holds no MkDocs config. On PRs affecting `docs/**` or
  `fiberpath_gui/docs/**`, the `CI Check`'s `docs` job calls the org-shared
  reusable workflow `fiberpath/.github/.github/workflows/docs-validate.yml`,
  which builds these docs against the site's real config (`--strict`).

**dependency-audit.yml** - Dependency Security Audit

- Triggers: Push to main, PRs to main, weekly schedule, manual dispatch
- Jobs:
  1. Python dependency audit (pip-audit)
  2. Node dependency audit (npm audit --audit-level=high)
  3. Rust dependency audit (cargo audit with CVSS >= 7 gate)
- Artifacts: JSON reports retained for 30 days
- Status: [![Dependency Audit](https://github.com/USER/fiberpath/actions/workflows/dependency-audit.yml/badge.svg)](https://github.com/USER/fiberpath/actions/workflows/dependency-audit.yml)

#### Deployment Workflows

Documentation is **published from the project hub repo**,
[`fiberpath/fiberpath.github.io`](https://github.com/fiberpath/fiberpath.github.io), not from this
repo. The hub owns all MkDocs config; it imports this repo's `docs/` (and the GUI docs) at build time,
builds the unified site with MkDocs `--strict`, and serves it at <https://fiberpath.github.io/fiberpath>.
This repo contributes only Markdown; validation on PRs is delegated to the org's shared
`docs-validate` reusable workflow (above).

#### Packaging Workflows

**gui-packaging.yml** - GUI Installer Creation

- Triggers: Push to main affecting GUI, manual dispatch, releases
- Jobs:
  1. Build installers for Windows/macOS/Linux (Tauri)
  2. Upload artifacts (30 day retention)
  3. Upload release assets (if triggered by release)
- Timeout: 45 minutes per OS
- Status: [![GUI Packaging](https://github.com/USER/fiberpath/actions/workflows/gui-packaging.yml/badge.svg)](https://github.com/USER/fiberpath/actions/workflows/gui-packaging.yml)

#### Publishing Workflows

**backend-publish.yml** - PyPI Publishing

- Triggers: GitHub releases, manual dispatch
- Jobs:
  1. Verify version matches tag
  2. Build distribution packages
  3. Publish to PyPI (trusted publishing)
- Environment: pypi (with deployment protection)
- Permissions: contents:read, id-token:write
- Status: [![Backend Publish](https://github.com/USER/fiberpath/actions/workflows/backend-publish.yml/badge.svg)](https://github.com/USER/fiberpath/actions/workflows/backend-publish.yml)

#### Release Orchestration

**release.yml** - Coordinated Release Management

- Triggers: Manual dispatch with version input
- Jobs:
  1. Validate version format and tag availability
  2. Generate SBOM artifacts (Python, Node, Rust)
  3. Create GitHub release with auto-generated notes
  4. Trigger backend-publish (PyPI)
  5. Trigger gui-packaging (installers)
- Inputs:
  - version: Semantic version (e.g., 0.3.14)
  - prerelease: Boolean flag
- Permissions: contents:write, id-token:write
- Status: [![Release](https://github.com/USER/fiberpath/actions/workflows/release.yml/badge.svg)](https://github.com/USER/fiberpath/actions/workflows/release.yml)

## Workflow Naming Convention

Format: `{component}-{purpose}.yml`

- **Component**: backend | gui | docs | release
- **Purpose**: ci | packaging | publish | deploy

## Trigger Strategy

| Workflow        | Push (main) | Pull Request | Manual | Release |
| --------------- | ----------- | ------------ | ------ | ------- |
| backend-ci      | ✅          | ✅           | ❌     | ❌      |
| gui-ci          | ✅          | ✅           | ❌     | ❌      |
| dependency-audit| ✅          | ✅           | ✅     | ❌      |
| gui-packaging   | ✅          | ❌           | ✅     | ✅      |
| backend-publish | ❌          | ❌           | ✅     | ✅      |
| release         | ❌          | ❌           | ✅     | ❌      |

## Path Filters

Workflows only run when relevant files change:

- **backend-ci**: `fiberpath/**`, `fiberpath_api/**`, `fiberpath_cli/**`, `tests/**`, `pyproject.toml`
- **gui-ci**: `fiberpath_gui/**`, workflow files, composite actions
- **docs (CI Check filter)**: `docs/**`, `fiberpath_gui/docs/**`, `README.md`
- **gui-packaging**: `fiberpath_gui/**`, workflow files, composite actions
- **dependency-audit**: `.github/workflows/dependency-audit.yml`, dependency manifests and lockfiles

## Release Process

### Manual Release Steps

1. **Prepare Release**
   - Update version in `pyproject.toml`
   - Update version in `fiberpath_gui/src-tauri/Cargo.toml`
   - Update `CHANGELOG.md` with release notes
   - Commit changes: `git commit -m "Prepare release 0.3.14"`

1. **Trigger Release Workflow**
   - Go to Actions → Release → Run workflow
   - Enter version: `0.3.14`
   - Set prerelease: `false`
   - Click "Run workflow"

1. **Automated Steps**
  Validates version format and tag availability, verifies version consistency, generates SBOM artifacts, creates the release tag, creates the GitHub release, and triggers package publishing and installer workflows.

1. **Post-Release**
   - Verify PyPI upload: [pypi.org/project/fiberpath](https://pypi.org/project/fiberpath/)
   - Download GUI installers from GitHub release
   - Test installers on Windows/macOS/Linux
   - Announce release

## Archived Workflows

Previous workflows moved to `.github/workflows/archive/`:

- **ci.yml** - Old monolithic Python CI (combined lint + test)
- **gui.yml** - Old GUI checks + packaging (redundant with gui-tests.yml)
- **gui-tests.yml** - Old GUI testing (redundant with gui.yml)
- **docs-site.yml** - Old docs deployment (the site now lives in the fiberpath.github.io hub repo)

## Improvements Over Previous System

| Issue                | Previous                                            | New Solution                         |
| -------------------- | --------------------------------------------------- | ------------------------------------ |
| Redundancy           | gui.yml and gui-tests.yml both ran linting/building | Single gui-ci.yml with all checks    |
| Naming               | Inconsistent (ci.yml, gui.yml, docs-site.yml)       | Consistent {component}-{purpose}.yml |
| Setup duplication    | Python/Node/Rust setup repeated in every workflow   | Composite actions (DRY principle)    |
| PyPI publishing      | Manual process                                      | Automated with trusted publishing    |
| Release coordination | Manual trigger of each workflow                     | Single release.yml orchestrates all  |
| Documentation        | No workflow docs                                    | This document + badges in README     |

## Caching Strategy

### Python (setup-python)

- Virtual environment: `.venv/` cached by OS + Python version + pyproject.toml hash
- uv cache: Built-in caching from astral-sh/setup-uv@v3

### Node.js (setup-node)

- npm modules: `~/.npm` cached by actions/setup-node@v4 with package-lock.json hash

### Rust (setup-rust)

- Cargo artifacts: `~/.cargo/` + `target/` cached by OS + Cargo.lock hash
- Binaries, registry, git index

## Future Enhancements

- [ ] Add workflow status badges to README.md
- [ ] Document in CONTRIBUTING.md
- [ ] Add Codecov integration for coverage tracking
- [x] Add Dependabot for Python, npm, Cargo, and GitHub Actions updates
- [x] Add scheduled dependency security audit workflow
- [x] Add SBOM artifacts to release pipeline
- [ ] Add workflow matrix testing for multiple Python versions
- [ ] Add performance benchmarking workflow
- [ ] Add security scanning (Snyk, SAST)
- [ ] Add automatic changelog generation
- [ ] Add automatic version bumping

## Troubleshooting

### Workflow Not Triggering

1. Check path filters - workflow only runs if affected files changed
2. Verify branch name matches trigger configuration
3. Check workflow file syntax (YAML validation)
4. Look for workflow run history in Actions tab

### Composite Action Errors

1. Verify action.yml exists in correct location
2. Check inputs are passed correctly from workflow
3. Ensure shell type is specified (bash/pwsh)
4. Review action logs for specific error messages

### Failed Builds

1. Check if dependencies changed (update lock files)
2. Verify environment variables are set correctly
3. Look for OS-specific issues (Linux deps for Tauri)
4. Review cache invalidation (might need manual clear)

### PyPI Publishing Failures

1. Verify trusted publishing is configured in PyPI project settings
2. Check version matches tag (validation step)
3. Ensure workflow has id-token:write permission
4. Verify environment "pypi" exists with protection rules

## References

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Composite Actions](https://docs.github.com/en/actions/creating-actions/creating-a-composite-action)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/)
- [Tauri GitHub Action](https://github.com/tauri-apps/tauri-action)
- [MkDocs Material](https://squidfunk.github.io/mkdocs-material/)
