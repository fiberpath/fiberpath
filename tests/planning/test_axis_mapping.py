"""Tests for axis mapping behavior in planner output."""

from pathlib import Path

import pytest
from fiberpath.config import MachineProfile, default_machine_profile, load_wind_definition
from fiberpath.config.schemas import WindDefinition
from fiberpath.gcode.dialects import MARLIN_XAB_STANDARD, AxisMapping
from fiberpath.planning import LayerValidationError, PlanOptions, plan_wind

REFERENCE_ROOT = Path(__file__).parents[1] / "cyclone_reference_runs"
REFERENCE_INPUTS = REFERENCE_ROOT / "inputs"


def _reference_definition(name: str = "simple-hoop") -> WindDefinition:
    return load_wind_definition(REFERENCE_INPUTS / f"{name}.wind")


def test_default_dialect_is_xab_standard() -> None:
    """Verify planning defaults to XAB axis output."""
    definition = _reference_definition("simple-hoop")

    result_default = plan_wind(definition)
    result_xab = plan_wind(definition, PlanOptions(profile=default_machine_profile()))

    assert result_default.commands == result_xab.commands
    # commands[1:4] is the modal preamble; the first motion line follows it.
    assert result_default.commands[4] == "G0 X0 A0 B0"


def test_xab_output_generates_expected_axis_letters() -> None:
    """Verify generated motion commands use X/A/B axes only."""
    result = plan_wind(_reference_definition("simple-hoop"), PlanOptions())

    motion_commands = [
        cmd for cmd in result.commands if cmd.startswith("G0") or cmd.startswith("G1")
    ]
    assert len(motion_commands) > 0

    assert any(" A" in cmd for cmd in motion_commands)
    assert any(" B" in cmd for cmd in motion_commands)
    assert all(" Y" not in cmd for cmd in motion_commands)
    assert all(" Z" not in cmd for cmd in motion_commands)


def test_axis_mapping_rotational_properties() -> None:
    """Verify AxisMapping property methods identify rotational axes."""
    xab = AxisMapping(carriage="X", mandrel="A", delivery_head="B")
    assert xab.is_rotational_mandrel
    assert xab.is_rotational_delivery

    xyz_like = AxisMapping(carriage="X", mandrel="Y", delivery_head="Z")
    assert not xyz_like.is_rotational_mandrel
    assert not xyz_like.is_rotational_delivery

    mixed = AxisMapping(carriage="X", mandrel="C", delivery_head="Y")
    assert mixed.is_rotational_mandrel
    assert not mixed.is_rotational_delivery


def test_predefined_dialect_configuration() -> None:
    """Ensure predefined dialect constant has expected mapping."""
    assert MARLIN_XAB_STANDARD.axis_mapping.carriage == "X"
    assert MARLIN_XAB_STANDARD.axis_mapping.mandrel == "A"
    assert MARLIN_XAB_STANDARD.axis_mapping.delivery_head == "B"
    assert MARLIN_XAB_STANDARD.axis_mapping.is_rotational_mandrel
    assert MARLIN_XAB_STANDARD.axis_mapping.is_rotational_delivery


def test_set_position_commands_use_active_dialect_axes() -> None:
    """Verify G92 commands honor configured axis mapping."""
    definition = WindDefinition.model_validate(
        {
            "layers": [
                {"windType": "hoop", "terminal": False},
                {"windType": "skip", "mandrelRotation": 90},
                {"windType": "hoop", "terminal": False},
            ],
            "mandrelParameters": {"diameter": 90.0, "windLength": 400.0},
            "towParameters": {"width": 8.0, "thickness": 0.4},
            "defaultFeedRate": 6000.0,
        }
    )

    result = plan_wind(definition, PlanOptions())
    g92_commands = [cmd for cmd in result.commands if cmd.startswith("G92")]
    assert len(g92_commands) > 0
    assert all(" A" in cmd or cmd == "G92 A0" for cmd in g92_commands)
    assert all(" Y" not in cmd for cmd in g92_commands)
    assert all(" Z" not in cmd for cmd in g92_commands)


def test_custom_axis_mapping() -> None:
    """Verify the planner honors a custom machine profile's axis mapping."""
    custom_profile = MachineProfile.model_validate(
        {
            "id": "custom-xca",
            "name": "Custom X/C/A",
            "controller": "marlin",
            "axisMapping": {"carriage": "X", "mandrel": "C", "deliveryHead": "A"},
            "requiredGcodes": ["G0", "G92"],
        }
    )

    definition = WindDefinition.model_validate(
        {
            "layers": [{"windType": "hoop"}],
            "mandrelParameters": {"diameter": 70.0, "windLength": 100.0},
            "towParameters": {"width": 7.0, "thickness": 0.5},
            "defaultFeedRate": 9000.0,
        }
    )

    result = plan_wind(definition, PlanOptions(profile=custom_profile))
    assert result.commands[4] == "G0 X0 C0 A0"  # after header + 3 preamble lines
    move_commands = [cmd for cmd in result.commands if cmd.startswith("G0") or cmd.startswith("G1")]
    assert any(" C" in cmd for cmd in move_commands)
    assert any(" A" in cmd for cmd in move_commands)


def test_verbose_mode_with_xab_dialect() -> None:
    """Verify verbose mode emits comments under XAB output."""
    definition = WindDefinition.model_validate(
        {
            "layers": [{"windType": "hoop"}],
            "mandrelParameters": {"diameter": 70.0, "windLength": 100.0},
            "towParameters": {"width": 7.0, "thickness": 0.5},
            "defaultFeedRate": 9000.0,
        }
    )

    result = plan_wind(definition, PlanOptions(verbose=True))
    comments = [cmd for cmd in result.commands if cmd.startswith(";")]
    assert len(comments) > 0


def test_helical_balanced_reference_rejected_by_divisibility_validation() -> None:
    """Legacy helical-balanced fixture is invalid under strict divisibility checks."""
    with pytest.raises(LayerValidationError, match="not divisible by patternNumber"):
        plan_wind(_reference_definition("helical-balanced"), PlanOptions())


def test_skip_bias_reference_rejected_by_divisibility_validation() -> None:
    """Legacy skip-bias fixture is invalid under strict divisibility checks."""
    with pytest.raises(LayerValidationError, match="not divisible by patternNumber"):
        plan_wind(_reference_definition("skip-bias"), PlanOptions())
