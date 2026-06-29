"""Equivalence gate for the developed-surface helical lowering (Stage 2 / S2 #296).

Asserts the lowered Motion IR is a correct winding path via coverage, on-surface
fiber angle, and delivery-head lean invariants, plus old-vs-new metric parity
against the committed goldens. This is the gate that replaces byte-equality for
helical as later slices change the emitted bytes; here it is validated against the
byte-identical cutover (so it must pass) and against deliberately broken inputs
(so it must fail).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from _equivalence import (
    assert_coverage,
    assert_geometry,
    assert_hoop_geometry,
    assert_lean,
    assert_metrics_equal,
    helical_layer_moves,
    hoop_layer_moves,
)
from fiberpath.config import load_wind_definition
from fiberpath.config.schemas import HelicalLayer, HoopLayer
from fiberpath.gcode.reader import read_program
from fiberpath.planning import plan_wind

REPO_ROOT = Path(__file__).resolve().parents[2]

# Pure-hoop example parts (developed-surface hoop lowering, S3).
HOOP_GOLDENS: list[tuple[str, str]] = [
    ("examples/simple_cylinder/input.wind", "examples/simple_cylinder/expected.gcode"),
    ("examples/sized_simple_cylinder/input.wind", "examples/sized_simple_cylinder/expected.gcode"),
]

# Example parts that contain helical layers (the ones whose bytes the developed
# lowering owns); the two pure-hoop parts stay on the byte-equal gate.
HELICAL_GOLDENS: list[tuple[str, str]] = [
    ("examples/multi_layer/input.wind", "examples/multi_layer/expected.gcode"),
    ("examples/rocketry/AvBay(470mm)single.wind", "examples/rocketry/AvBay(470mm)single.gcode"),
    ("examples/rocketry/AvBay(470mm)triple.wind", "examples/rocketry/AvBay(470mm)triple.gcode"),
    ("examples/rocketry/MainChute(585mm).wind", "examples/rocketry/MainChute(585mm).gcode"),
    (
        "examples/rocketry/CarbonMotorTube(1295mm).wind",
        "examples/rocketry/CarbonMotorTube(1295mm).gcode",
    ),
]


@pytest.mark.parametrize("wind_rel", [w for w, _ in HELICAL_GOLDENS])
def test_helical_layers_satisfy_path_invariants(wind_rel: str) -> None:
    definition = load_wind_definition(REPO_ROOT / wind_rel)
    mandrel = definition.mandrel_parameters
    tow = definition.tow_parameters

    helical = [layer for layer in definition.layers if isinstance(layer, HelicalLayer)]
    assert helical, f"{wind_rel} has no helical layer"
    for layer in helical:
        assert_coverage(layer, mandrel, tow)
        moves = helical_layer_moves(layer, mandrel, tow, definition.default_feed_rate)
        assert_geometry(moves, layer.wind_angle, mandrel.diameter)
        assert_lean(moves, layer.wind_angle)


@pytest.mark.parametrize("wind_rel", [w for w, _ in HOOP_GOLDENS])
def test_hoop_layers_lay_at_densest_wrap_angle(wind_rel: str) -> None:
    definition = load_wind_definition(REPO_ROOT / wind_rel)
    mandrel = definition.mandrel_parameters
    tow = definition.tow_parameters

    hoops = [layer for layer in definition.layers if isinstance(layer, HoopLayer)]
    assert hoops, f"{wind_rel} has no hoop layer"
    for layer in hoops:
        moves = hoop_layer_moves(layer, mandrel, tow, definition.default_feed_rate)
        assert_hoop_geometry(moves, mandrel.diameter, tow.width)


@pytest.mark.parametrize("wind_rel,golden_rel", HELICAL_GOLDENS + HOOP_GOLDENS)
def test_new_lowering_matches_golden_metrics(wind_rel: str, golden_rel: str) -> None:
    definition = load_wind_definition(REPO_ROOT / wind_rel)
    old = read_program((REPO_ROOT / golden_rel).read_text(encoding="utf-8").splitlines())
    new = read_program(plan_wind(definition).commands)
    assert_metrics_equal(old.moves, new.moves, definition.mandrel_parameters.diameter)


# --- the harness must actually catch regressions (not be vacuous) ---

_LAYER = HelicalLayer.model_validate(
    {
        "windAngle": 35.0,
        "patternNumber": 3,
        "skipIndex": 2,
        "lockDegrees": 180.0,
        "leadInMM": 4.0,
        "leadOutDegrees": 12.0,
    }
)


def _fixture_moves():
    from fiberpath.config.schemas import MandrelParameters, TowParameters

    mandrel = MandrelParameters.model_validate({"diameter": 40.0, "windLength": 120.0})
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})
    return helical_layer_moves(_LAYER, mandrel, tow), mandrel, tow


def test_geometry_check_rejects_wrong_angle() -> None:
    moves, mandrel, _ = _fixture_moves()
    with pytest.raises(AssertionError):
        assert_geometry(moves, _LAYER.wind_angle + 5.0, mandrel.diameter)


def test_lean_check_rejects_wrong_angle() -> None:
    moves, mandrel, _ = _fixture_moves()
    with pytest.raises(AssertionError):
        assert_lean(moves, _LAYER.wind_angle + 5.0)


def test_coverage_check_rejects_non_coprime_pattern() -> None:
    from fiberpath.config.schemas import MandrelParameters, TowParameters

    mandrel = MandrelParameters.model_validate({"diameter": 40.0, "windLength": 120.0})
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})
    aliasing = HelicalLayer.model_validate(
        {
            "windAngle": 35.0,
            "patternNumber": 4,
            "skipIndex": 2,  # gcd(2, 4) = 2 -> aliases
            "lockDegrees": 180.0,
            "leadInMM": 4.0,
            "leadOutDegrees": 12.0,
        }
    )
    with pytest.raises(AssertionError):
        assert_coverage(aliasing, mandrel, tow)


def test_metrics_check_rejects_dropped_moves() -> None:
    moves, mandrel, _ = _fixture_moves()
    with pytest.raises(AssertionError):
        assert_metrics_equal(moves, moves[: len(moves) // 2], mandrel.diameter)


def test_hoop_geometry_check_rejects_wrong_tow_width() -> None:
    from fiberpath.config.schemas import MandrelParameters, TowParameters

    mandrel = MandrelParameters.model_validate({"diameter": 50.0, "windLength": 120.0})
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})
    moves = hoop_layer_moves(HoopLayer(terminal=False), mandrel, tow)
    with pytest.raises(AssertionError):
        assert_hoop_geometry(moves, mandrel.diameter, tow.width * 2.0)
