"""Unit tests for the developed-surface path + lowering (Stage 2 / S2 #296)."""

from __future__ import annotations

import math
from pathlib import Path

from fiberpath.config.schemas import (
    HelicalLayer,
    HoopLayer,
    MandrelParameters,
    SkipLayer,
    TowParameters,
)
from fiberpath.planning.calculations import compute_helical_kinematics
from fiberpath.planning.developed import (
    build_helical_developed_path,
    build_hoop_developed_path,
    build_skip_developed_path,
    lower_developed_path,
)
from fiberpath.planning.machine import WinderMachine
from fiberpath.planning.pattern import pattern_spec

FIXTURE = Path(__file__).parent / "fixtures" / "helical_layer.gcode"
HOOP_FIXTURE = Path(__file__).parent / "fixtures" / "hoop_layer.gcode"
# _generate_fixtures.py uses these for hoop_layer.gcode (non-terminal).
HOOP_MANDREL = MandrelParameters.model_validate({"diameter": 50.0, "windLength": 120.0})

# The exact inputs _generate_fixtures.py uses for helical_layer.gcode.
MANDREL = MandrelParameters.model_validate({"diameter": 40.0, "windLength": 120.0})
TOW = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})
FIXTURE_LAYER = {
    "windAngle": 35.0,
    "patternNumber": 3,
    "skipIndex": 2,
    "lockDegrees": 180.0,
    "leadInMM": 4.0,
    "leadOutDegrees": 12.0,
}


def _lower(layer: HelicalLayer, mandrel: MandrelParameters) -> list[str]:
    machine = WinderMachine(mandrel.diameter)
    machine.set_feed_rate(9000.0)
    kinematics = compute_helical_kinematics(layer, mandrel, TOW)
    path = build_helical_developed_path(pattern_spec(layer), kinematics, mandrel)
    lower_developed_path(machine, path)
    return machine.get_gcode()


def test_lowering_is_byte_identical_to_committed_fixture() -> None:
    layer = HelicalLayer.model_validate(FIXTURE_LAYER)
    assert _lower(layer, MANDREL) == FIXTURE.read_text(encoding="utf-8").splitlines()


def test_no_negative_zero_tokens_emitted() -> None:
    lines = _lower(HelicalLayer.model_validate(FIXTURE_LAYER), MANDREL)
    assert not any(" -0" in line or line.endswith("-0") for line in lines)


def test_developed_waypoints_lie_at_the_wind_angle() -> None:
    layer = HelicalLayer.model_validate(FIXTURE_LAYER)
    kinematics = compute_helical_kinematics(layer, MANDREL, TOW)
    path = build_helical_developed_path(pattern_spec(layer), kinematics, MANDREL)

    circumference = math.pi * MANDREL.diameter
    prev = None
    checked = 0
    for waypoint in path.waypoints:
        if prev is not None:
            d_z = waypoint.z - prev.z
            if abs(d_z) > 1e-9:
                arc_mm = (waypoint.theta - prev.theta) / 360.0 * circumference
                angle = math.degrees(math.atan2(abs(arc_mm), abs(d_z)))
                assert abs(angle - layer.wind_angle) < 1e-9
                checked += 1
        prev = waypoint
    assert checked > 0  # the path actually has laying (carriage-moving) segments


def test_high_angle_helical_waypoints_lie_at_the_wind_angle() -> None:
    # alpha=80 makes pass_rotation_degrees % 360 > 180, so the per-pass tail term
    # goes negative; confirm the high-angle path still lays at the wind angle.
    layer = HelicalLayer.model_validate(
        {**FIXTURE_LAYER, "windAngle": 80.0, "patternNumber": 1, "skipIndex": 1}
    )
    kinematics = compute_helical_kinematics(layer, MANDREL, TOW)
    path = build_helical_developed_path(pattern_spec(layer), kinematics, MANDREL)

    circumference = math.pi * MANDREL.diameter
    prev = None
    checked = 0
    for waypoint in path.waypoints:
        if prev is not None:
            d_z = waypoint.z - prev.z
            if abs(d_z) > 1e-9:
                arc_mm = (waypoint.theta - prev.theta) / 360.0 * circumference
                angle = math.degrees(math.atan2(abs(arc_mm), abs(d_z)))
                assert abs(angle - layer.wind_angle) < 1e-9
                checked += 1
        prev = waypoint
    assert checked > 0


def _lower_hoop(terminal: bool) -> list[str]:
    machine = WinderMachine(HOOP_MANDREL.diameter)
    machine.set_feed_rate(9000.0)
    spec = pattern_spec(HoopLayer(terminal=terminal))
    lower_developed_path(machine, build_hoop_developed_path(spec, HOOP_MANDREL, TOW))
    return machine.get_gcode()


def test_hoop_lowering_is_byte_identical_to_committed_fixture() -> None:
    assert _lower_hoop(terminal=False) == HOOP_FIXTURE.read_text(encoding="utf-8").splitlines()


def test_terminal_hoop_omits_the_return_pass_and_zero_axes() -> None:
    terminal = _lower_hoop(terminal=True)
    non_terminal = _lower_hoop(terminal=False)
    # Terminal stops after the far-lock, so its output is exactly the shared
    # prefix of the non-terminal output: the return pass is absent (not merely
    # shorter by the zero_axes lines), and there is no G92 anywhere (hoop emits
    # G92 only via the closing zero_axes, which a terminal layer skips).
    assert terminal == non_terminal[: len(terminal)]
    assert len(terminal) < len(non_terminal)
    assert not any(line.startswith("G92") for line in terminal)


def test_skip_lowering_is_byte_identical_to_committed_fixture() -> None:
    machine = WinderMachine(HOOP_MANDREL.diameter)
    machine.set_feed_rate(9000.0)
    spec = pattern_spec(SkipLayer.model_validate({"mandrelRotation": 45.0}))
    lower_developed_path(machine, build_skip_developed_path(spec))
    fixture = (Path(__file__).parent / "fixtures" / "skip_layer.gcode").read_text().splitlines()
    assert machine.get_gcode() == fixture


def test_skip_lays_no_fiber_and_only_repositions() -> None:
    spec = pattern_spec(SkipLayer.model_validate({"mandrelRotation": 45.0}))
    path = build_skip_developed_path(spec)
    # A skip is a pure reposition: no laying waypoints, no closing zero_axes.
    assert path.waypoints == ()
    assert path.terminal is True
    assert path.initial_lock_degrees == 45.0


def test_hoop_waypoints_lie_at_the_densest_wrap_angle() -> None:
    spec = pattern_spec(HoopLayer(terminal=False))
    path = build_hoop_developed_path(spec, HOOP_MANDREL, TOW)

    circumference = math.pi * HOOP_MANDREL.diameter
    expected = math.degrees(math.atan(circumference / TOW.width))
    prev = None
    checked = 0
    for waypoint in path.waypoints:
        if prev is not None:
            d_z = waypoint.z - prev.z
            if abs(d_z) > 1e-9:
                arc_mm = (waypoint.theta - prev.theta) / 360.0 * circumference
                angle = math.degrees(math.atan2(abs(arc_mm), abs(d_z)))
                assert abs(angle - expected) < 1e-9
                checked += 1
        prev = waypoint
    assert checked > 0
