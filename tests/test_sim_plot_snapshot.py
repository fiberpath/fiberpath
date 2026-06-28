"""Before-snapshot of simulator + plotter outputs for the frozen example goldens.

The simulator and plotter currently re-parse G-code text, and their numbers will
legitimately shift in the Motion IR work (#136): adopting the single O1 time
model (#275/S3) and consuming the IR — which stops silently dropping the ``G92``
reference frame (S3/S4) — change `estimated_time_s`, `average_feed_rate_mmpm`,
and the plot ``digest``. Those deltas are NOT covered by the byte-equal G-code
gate (`test_example_goldens`), so this captures today's values as a committed
baseline: when S3/S4 regenerate it, the JSON diff is the explicit, reviewable
delta.

It also acts as a tripwire: while the G-code stays byte-equal (S2a/S2b) the
text-parsing consumers can't change, so this stays green until a consumer is
deliberately migrated.

Regenerate deliberately (never hand-edit) with::

    FIBERPATH_UPDATE_GOLDENS=1 pytest tests/test_sim_plot_snapshot.py

The three large rocketry triples are intentionally excluded for speed: their
G-code is byte-gated by `test_example_goldens`, and their sim/plot deltas mirror
the single-helical AvBay case kept below.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fiberpath.simulation import simulate_program
from fiberpath.visualization.plotter import compute_plot_signature

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = Path(__file__).parent / "sim_plot_snapshot.json"

# Representative frozen goldens: hoop, larger hoop, hoop+helical, single helical.
SNAPSHOT_INPUTS: list[str] = [
    "examples/simple_cylinder/expected.gcode",
    "examples/sized_simple_cylinder/expected.gcode",
    "examples/multi_layer/expected.gcode",
    "examples/rocketry/AvBay(470mm)single.gcode",
]


def _snapshot(gcode_rel: str) -> dict[str, object]:
    program = (REPO_ROOT / gcode_rel).read_text(encoding="utf-8").splitlines()
    sim = simulate_program(program)
    sig = compute_plot_signature(program)
    return {
        "sim": {
            "commands_executed": sim.commands_executed,
            "moves": sim.moves,
            "estimated_time_s": round(sim.estimated_time_s, 6),
            "total_distance_mm": round(sim.total_distance_mm, 6),
            "tow_length_mm": round(sim.tow_length_mm, 6),
            "average_feed_rate_mmpm": round(sim.average_feed_rate_mmpm, 6),
        },
        "plot": {
            "mandrel_length_mm": round(sig.metadata.mandrel_length_mm, 6),
            "tow_width_mm": round(sig.metadata.tow_width_mm, 6),
            "segments_rendered": sig.segments_rendered,
            "digest": sig.digest,
        },
    }


def _current() -> dict[str, object]:
    return {rel: _snapshot(rel) for rel in SNAPSHOT_INPUTS}


def test_sim_plot_snapshot_matches_baseline() -> None:
    current = _current()

    if os.environ.get("FIBERPATH_UPDATE_GOLDENS"):
        SNAPSHOT_PATH.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
        pytest.skip(f"regenerated {SNAPSHOT_PATH.name}")

    baseline = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert current == baseline, (
        "Simulator/plotter output drifted from the committed baseline. If this is "
        "an intended change (e.g. the O1 time model or IR G92 handling in S3/S4), "
        "regenerate with FIBERPATH_UPDATE_GOLDENS=1 pytest and review the JSON diff."
    )
