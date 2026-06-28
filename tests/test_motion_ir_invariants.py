"""CI guard for the Motion IR single-source-of-truth invariants (#136).

The epic collapsed triplicated motion math and two G-code text re-parsers into a
single home each. These source greps fail loudly if a future change reintroduces a
duplicate — the exact divergence the epic removed. They are intentionally simple
(substring scans over ``fiberpath/``), so a deliberate move just updates the
expected home here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Scan every shipped package, not just the engine — a duplicate reintroduced at
# the CLI/API boundary must be caught too.
PACKAGES = ("fiberpath", "fiberpath_cli", "fiberpath_api")


def _files_containing(needle: str) -> set[str]:
    return {
        path.relative_to(ROOT).as_posix()
        for package in PACKAGES
        for path in (ROOT / package).rglob("*.py")
        if needle in path.read_text(encoding="utf-8")
    }


@pytest.mark.parametrize(
    ("needle", "home"),
    [
        # The O1 surface-arc distance — the one motion-math implementation.
        ("math.sqrt(", "fiberpath/planning/metrics.py"),
        # G-code dialect sniffing lives only in the boundary reader.
        ("_detect_dialect", "fiberpath/gcode/reader.py"),
        # The `; Parameters` header is recognized/parsed only in the reader.
        ('"; Parameters "', "fiberpath/gcode/reader.py"),
    ],
)
def test_single_implementation(needle: str, home: str) -> None:
    found = _files_containing(needle)
    assert found == {home}, (
        f"{needle!r} must live only in {home} (the Motion IR single source of "
        f"truth), but was found in {sorted(found)}. If this is a deliberate move, "
        f"update the expected home in this guard."
    )


def test_no_ast_literal_eval() -> None:
    # The plotter's old header hack; the reader parses the header as strict JSON.
    assert _files_containing("literal_eval") == set()
