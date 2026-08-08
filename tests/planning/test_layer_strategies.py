from __future__ import annotations

from pathlib import Path

from fiberpath.config.schemas import (
    HelicalLayer,
    HoopLayer,
    MandrelParameters,
    SkipLayer,
    TowParameters,
)
from fiberpath.planning.layer_strategies import dispatch_layer
from fiberpath.planning.machine import WinderMachine

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def _machine(diameter: float = 50.0) -> WinderMachine:
    machine = WinderMachine(diameter)
    machine.set_feed_rate(9000.0)
    return machine


def _mandrel(diameter: float = 50.0) -> MandrelParameters:
    return MandrelParameters.model_validate({"diameter": diameter, "windLength": 120.0})


def _tow() -> TowParameters:
    return TowParameters.model_validate({"width": 6.0, "thickness": 0.5})


def _load_fixture(name: str) -> list[str]:
    return (FIXTURE_DIR / name).read_text().splitlines()


def test_hoop_layer_matches_fixture() -> None:
    machine = _machine()
    dispatch_layer(machine, HoopLayer(terminal=False), _mandrel(), _tow())

    assert machine.get_gcode() == _load_fixture("hoop_layer.gcode")


def test_helical_layer_matches_fixture() -> None:
    machine = _machine(40.0)
    dispatch_layer(
        machine,
        HelicalLayer.model_validate(
            {
                "windAngle": 35.0,
                "patternNumber": 3,
                "skipIndex": 2,
                "lockDegrees": 180.0,
                "leadInMM": 4.0,
                "leadOutDegrees": 12.0,
            }
        ),
        _mandrel(40.0),
        _tow(),
    )

    assert machine.get_gcode() == _load_fixture("helical_layer.gcode")


def test_skip_layer_matches_fixture() -> None:
    machine = _machine()
    dispatch_layer(machine, SkipLayer.model_validate({"mandrelRotation": 45.0}), _mandrel(), _tow())

    assert machine.get_gcode() == _load_fixture("skip_layer.gcode")


def _vk_mandrel() -> MandrelParameters:
    return MandrelParameters.model_validate(
        {"diameter": 98.0, "windLength": 300.0, "profile": {"type": "vonKarman"}}
    )


def _vk_helical() -> HelicalLayer:
    return HelicalLayer.model_validate(
        {
            "windAngle": 30.0,
            "patternNumber": 3,
            "skipIndex": 1,
            "lockDegrees": 360.0,
            "leadInMM": 20.0,
            "leadOutDegrees": 60.0,
        }
    )


def test_dispatch_routes_friction_lambda_to_the_nongeodesic_path() -> None:
    # friction_lambda > 0 must reach compute_profile_helical_kinematics via the dispatch
    # fallback: the marched path climbs past the geodesic cap, so it emits strictly more
    # moves than the geodesic (friction_lambda = 0) path on the same mandrel.
    geo = _machine(98.0)
    dispatch_layer(geo, _vk_helical(), _vk_mandrel(), _tow())
    fric = _machine(98.0)
    dispatch_layer(fric, _vk_helical(), _vk_mandrel(), _tow(), friction_lambda=0.1)

    assert len(fric.get_moves()) > len(geo.get_moves())
