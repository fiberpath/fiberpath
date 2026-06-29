"""Byte-equal golden tests for the example ``.wind`` -> ``.gcode`` toolpaths.

Each example program is planned and compared, byte-for-byte, against its
committed golden. This is the regression gate the Motion IR refactor (#136) runs
against: the IR lowering + ``serialize()`` in #274 must keep these diffs empty.
Until then the harness exercises the current emit path (``plan_wind().commands``
serialized exactly as :func:`fiberpath.gcode.write_gcode` writes the file).

Regenerate the goldens **deliberately** (never hand-edit) with::

    FIBERPATH_UPDATE_GOLDENS=1 pytest tests/planning/test_example_goldens.py

The four strategy-level fixtures in ``tests/planning/fixtures/`` stay on their
own path (``_generate_fixtures.py`` / ``test_layer_strategies.py``); this module
covers the full-program path.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fiberpath.config import load_wind_definition
from fiberpath.gcode.dialects import MARLIN_XAB_STANDARD
from fiberpath.planning import PlanOptions, plan_wind

REPO_ROOT = Path(__file__).resolve().parents[2]

# (wind, golden) pairs relative to the repo root, smallest first so a fast run
# surfaces a structural break before grinding through the multi-MB rocketry parts.
EXAMPLE_GOLDENS: list[tuple[str, str]] = [
    ("examples/simple_cylinder/input.wind", "examples/simple_cylinder/expected.gcode"),
    ("examples/sized_simple_cylinder/input.wind", "examples/sized_simple_cylinder/expected.gcode"),
    ("examples/multi_layer/input.wind", "examples/multi_layer/expected.gcode"),
    # NOTE: examples/cone_reducer is intentionally NOT byte-goldened. Its geodesic
    # path uses acos/asin accumulation whose last rounded digit is not bit-stable
    # across platforms (Linux vs Windows differ by ~1e-6 on boundary coordinates),
    # so it is gated by the tolerance-based equivalence harness instead -- see
    # tests/planning/test_cone.py::test_cone_reducer_example_is_a_valid_geodesic.
    ("examples/rocketry/AvBay(470mm)single.wind", "examples/rocketry/AvBay(470mm)single.gcode"),
    ("examples/rocketry/AvBay(470mm)triple.wind", "examples/rocketry/AvBay(470mm)triple.gcode"),
    ("examples/rocketry/MainChute(585mm).wind", "examples/rocketry/MainChute(585mm).gcode"),
    (
        "examples/rocketry/CarbonMotorTube(1295mm).wind",
        "examples/rocketry/CarbonMotorTube(1295mm).gcode",
    ),
]


def _render(wind: Path) -> str:
    """Plan a ``.wind`` to G-code text exactly as ``write_gcode`` serializes it."""
    definition = load_wind_definition(wind)
    result = plan_wind(definition, PlanOptions(verbose=False, dialect=MARLIN_XAB_STANDARD))
    return "\n".join(result.commands) + "\n"


def _first_difference(rendered: str, expected: str, golden_rel: str) -> str:
    """A concise mismatch report (these files run to millions of lines)."""
    r_lines = rendered.splitlines()
    e_lines = expected.splitlines()
    for i, (r, e) in enumerate(zip(r_lines, e_lines, strict=False)):
        if r != e:
            return (
                f"{golden_rel} differs at line {i + 1} "
                f"(rendered {len(r_lines)} lines, golden {len(e_lines)}):\n"
                f"  expected: {e[:120]!r}\n"
                f"  rendered: {r[:120]!r}\n"
                f"Regenerate deliberately with FIBERPATH_UPDATE_GOLDENS=1 pytest."
            )
    # No line differs within the shared prefix -> the lengths (or trailing
    # newline) differ. Catching that is the whole point of the exact compare.
    return (
        f"{golden_rel} matches for {min(len(r_lines), len(e_lines))} lines but "
        f"lengths differ (rendered {len(r_lines)}, golden {len(e_lines)}) "
        f"or the trailing newline drifted. "
        f"Regenerate deliberately with FIBERPATH_UPDATE_GOLDENS=1 pytest."
    )


@pytest.mark.parametrize(
    "wind_rel,golden_rel", EXAMPLE_GOLDENS, ids=[pair[0] for pair in EXAMPLE_GOLDENS]
)
def test_example_golden_is_byte_equal(wind_rel: str, golden_rel: str) -> None:
    wind = REPO_ROOT / wind_rel
    golden = REPO_ROOT / golden_rel
    rendered = _render(wind)

    if os.environ.get("FIBERPATH_UPDATE_GOLDENS"):
        golden.write_text(rendered, encoding="utf-8")
        pytest.skip(f"regenerated {golden_rel}")

    expected = golden.read_text(encoding="utf-8")
    if rendered != expected:
        # Don't let pytest diff multi-MB strings; report the first difference.
        pytest.fail(_first_difference(rendered, expected, golden_rel), pytrace=False)
