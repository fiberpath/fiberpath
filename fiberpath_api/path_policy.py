"""Path policy helpers for API file access."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import HTTPException

_ALLOWED_ROOTS_ENV = "FIBERPATH_API_ALLOWED_ROOTS"


def _parse_allowed_roots() -> list[Path]:
    raw = os.getenv(_ALLOWED_ROOTS_ENV)
    if not raw:
        return [Path.cwd().resolve()]

    roots: list[Path] = []
    for token in raw.split(os.pathsep):
        value = token.strip()
        if not value:
            continue
        # Ensure each configured root is absolute and normalized.
        root_path = Path(value).expanduser()
        if not root_path.is_absolute():
            root_path = Path.cwd() / root_path
        roots.append(root_path.resolve())

    return roots or [Path.cwd().resolve()]


def _resolve_user_path(user_path: str, roots: list[Path]) -> Path:
    raw = user_path.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="Path must not be empty")
    if "\x00" in raw:
        raise HTTPException(status_code=400, detail="Path contains invalid characters")

    expanded = os.path.expanduser(raw)
    drive, _ = os.path.splitdrive(expanded)
    if os.path.isabs(expanded) or drive:
        raise HTTPException(status_code=400, detail="Absolute paths are not allowed")

    normalized = os.path.normpath(expanded)
    if normalized in ("", "."):
        raise HTTPException(status_code=400, detail="Path must not be empty")
    if os.path.isabs(normalized):
        raise HTTPException(status_code=400, detail="Absolute paths are not allowed")

    candidate = Path(normalized)

    # Relative paths are resolved from each allowed root in order.
    # Pick the first candidate that remains within that same root.
    for root in roots:
        resolved = (root / candidate).resolve(strict=False)
        try:
            resolved.relative_to(root.resolve(strict=False))
            return resolved
        except ValueError:
            continue

    # None of the root-relative candidates were within a root.
    roots_str = ", ".join(str(root) for root in roots)
    raise HTTPException(
        status_code=403,
        detail=(
            f"Path '{user_path}' is outside allowed API roots. "
            f"Configure {_ALLOWED_ROOTS_ENV} to permit additional roots. "
            f"Current roots: {roots_str}"
        ),
    )


def _is_within_roots(path: Path, roots: list[Path]) -> bool:
    """Return True if `path` is located within any of the allowed `roots`."""
    # Work with absolute, normalized paths to avoid traversal / prefix issues.
    path = path.resolve(strict=False)
    for root in roots:
        root = root.resolve(strict=False)
        try:
            # `relative_to` succeeds only if `path` is the same as `root`
            # or is located within `root`.
            path.relative_to(root)
            return True
        except ValueError:
            # Not a subpath of this root (or different drive on Windows); try next.
            continue
    return False


def enforce_input_path_policy(user_path: str) -> Path:
    """Resolve and validate an input path against configured allowed roots."""
    roots = _parse_allowed_roots()
    return _resolve_user_path(user_path, roots)


def enforce_output_path_policy(path: Path) -> Path:
    """Validate an output path against configured allowed roots."""
    resolved = path.resolve(strict=False)
    roots = _parse_allowed_roots()

    if not _is_within_roots(resolved, roots):
        roots_str = ", ".join(str(root) for root in roots)
        raise HTTPException(
            status_code=403,
            detail=(
                f"Output path '{resolved}' is outside allowed API roots. "
                f"Configure {_ALLOWED_ROOTS_ENV} to permit additional roots. "
                f"Current roots: {roots_str}"
            ),
        )

    return resolved
