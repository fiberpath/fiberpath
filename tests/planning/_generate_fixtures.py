"""Utility script to refresh planner fixtures."""

from __future__ import annotations

from pathlib import Path

from fiberpath.config.schemas import (
    HelicalLayer,
    HoopLayer,
    MandrelParameters,
    SkipLayer,
    TowParameters,
    WindDefinition,
)
from fiberpath.planning import plan_wind
from fiberpath.planning.layer_strategies import dispatch_layer
from fiberpath.planning.machine import WinderMachine

FIXTURE_DIR = Path(__file__).parent / "fixtures"
FIXTURE_DIR.mkdir(parents=True, exist_ok=True)


def write(name: str, commands: list[str]) -> None:
    (FIXTURE_DIR / name).write_text("\n".join(commands) + "\n", encoding="utf-8")


def machine(diameter: float = 50.0) -> WinderMachine:
    mach = WinderMachine(diameter)
    mach.set_feed_rate(9000.0)
    return mach


def update_layer_fixtures() -> None:
    mandrel = MandrelParameters.model_validate({"diameter": 50.0, "windLength": 120.0})
    tow = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})

    hoop_machine = machine()
    dispatch_layer(hoop_machine, HoopLayer(terminal=False), mandrel, tow)
    write("hoop_layer.gcode", hoop_machine.get_gcode())

    helical_mandrel = MandrelParameters.model_validate({"diameter": 40.0, "windLength": 120.0})
    helical_machine = machine(40.0)
    dispatch_layer(
        helical_machine,
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
        helical_mandrel,
        tow,
    )
    write("helical_layer.gcode", helical_machine.get_gcode())

    skip_machine = machine()
    dispatch_layer(
        skip_machine,
        SkipLayer.model_validate({"mandrelRotation": 45.0}),
        mandrel,
        tow,
    )
    write("skip_layer.gcode", skip_machine.get_gcode())


def update_program_fixture() -> None:
    definition = WindDefinition.model_validate(
        {
            "layers": [
                {"windType": "hoop", "terminal": False},
            ],
            "mandrelParameters": {"diameter": 70.0, "windLength": 100.0},
            "towParameters": {"width": 7.0, "thickness": 0.5},
            "defaultFeedRate": 9000.0,
        }
    )
    result = plan_wind(definition)
    write("hoop_only_program.gcode", result.commands)


def main() -> None:
    update_layer_fixtures()
    update_program_fixture()


if __name__ == "__main__":
    main()
