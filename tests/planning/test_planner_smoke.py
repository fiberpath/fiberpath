from pathlib import Path

import pytest
from fiberpath.config import load_wind_definition
from fiberpath.config.schemas import WindDefinition
from fiberpath.planning import LayerValidationError, PlanOptions, plan_wind

REFERENCE_ROOT = Path(__file__).parents[1] / "cyclone_reference_runs"
REFERENCE_INPUTS = REFERENCE_ROOT / "inputs"


def _reference_definition(name: str = "simple-hoop") -> WindDefinition:
    return load_wind_definition(REFERENCE_INPUTS / f"{name}.wind")


def test_plan_wind_returns_commands() -> None:
    result = plan_wind(_reference_definition())

    assert result.commands[0].startswith("; Parameters")
    # Header, then the modal preamble (units / positioning / feed mode), then motion.
    assert [c.split(";")[0].strip() for c in result.commands[1:4]] == ["G21", "G90", "G94"]
    assert result.commands[4] == "G0 X0 A0 B0"
    assert result.total_time_s > 0
    assert result.layers[0].commands > 0


@pytest.mark.parametrize(
    "case",
    [
        "simple-hoop",
    ],
)
def test_plan_wind_uses_xab_axes(case: str) -> None:
    result = plan_wind(_reference_definition(case), PlanOptions())

    motion_commands = [
        cmd for cmd in result.commands if cmd.startswith("G0") or cmd.startswith("G1")
    ]
    assert any(" A" in cmd for cmd in motion_commands)
    assert any(" B" in cmd for cmd in motion_commands)
    assert all(" Y" not in cmd for cmd in motion_commands)
    assert all(" Z" not in cmd for cmd in motion_commands)


def test_plan_wind_rejects_legacy_non_divisible_helical_reference() -> None:
    with pytest.raises(LayerValidationError, match="not divisible by patternNumber"):
        plan_wind(_reference_definition("helical-balanced"), PlanOptions())


def test_plan_wind_rejects_legacy_skip_bias_non_divisible_reference() -> None:
    with pytest.raises(LayerValidationError, match="not divisible by patternNumber"):
        plan_wind(_reference_definition("skip-bias"), PlanOptions())


def test_plan_wind_rejects_layers_after_terminal() -> None:
    definition = WindDefinition.model_validate(
        {
            "layers": [
                {"windType": "hoop", "terminal": True},
                {"windType": "skip", "mandrelRotation": 30.0},
            ],
            "mandrelParameters": {"diameter": 70.0, "windLength": 100.0},
            "towParameters": {"width": 7.0, "thickness": 0.5},
            "defaultFeedRate": 9000.0,
        }
    )

    with pytest.raises(LayerValidationError):
        plan_wind(definition)


def test_plan_wind_rejects_invalid_skip_index() -> None:
    definition = WindDefinition.model_validate(
        {
            "layers": [
                {
                    "windType": "helical",
                    "windAngle": 35.0,
                    "patternNumber": 4,
                    "skipIndex": 2,
                    "lockDegrees": 180.0,
                    "leadInMM": 5.0,
                    "leadOutDegrees": 15.0,
                }
            ],
            "mandrelParameters": {"diameter": 70.0, "windLength": 100.0},
            "towParameters": {"width": 7.0, "thickness": 0.5},
            "defaultFeedRate": 9000.0,
        }
    )

    with pytest.raises(LayerValidationError):
        plan_wind(definition)
