"""Unit tests for low-level planning helpers and machine utilities."""

from __future__ import annotations

import pytest
from fiberpath.planning.helpers import Axis, interpolate_coordinates
from fiberpath.planning.machine import WinderMachine

BASE_START = {axis: 0.0 for axis in Axis}
BASE_END = {
    Axis.CARRIAGE: 10.0,
    Axis.MANDREL: 5.0,
    Axis.DELIVERY_HEAD: -2.5,
}


def test_interpolate_coordinates_rejects_non_positive_steps() -> None:
    with pytest.raises(ValueError):
        interpolate_coordinates(BASE_START, BASE_END, 0)


def test_interpolate_coordinates_with_single_step_returns_end() -> None:
    result = interpolate_coordinates(BASE_START, BASE_END, 1)
    assert result == [BASE_END]


def test_interpolate_coordinates_generates_even_steps() -> None:
    result = interpolate_coordinates(BASE_START, BASE_END, 3)
    assert len(result) == 3
    assert result[0] == BASE_START
    assert result[-1] == BASE_END
    assert pytest.approx(result[1][Axis.CARRIAGE], rel=1e-9) == 5.0


def test_machine_emits_verbose_comment_for_simple_moves() -> None:
    machine = WinderMachine(50.0, verbose_output=True)
    machine.set_feed_rate(1000.0)
    machine.move({Axis.DELIVERY_HEAD: -5.0})

    assert any(cmd.startswith("; Move ") for cmd in machine.get_gcode())


def test_machine_emits_verbose_comment_for_segmented_moves() -> None:
    machine = WinderMachine(50.0, verbose_output=True)
    machine.set_feed_rate(1000.0)
    machine.move({Axis.CARRIAGE: 2.5})

    assert any("Segmented move" in cmd for cmd in machine.get_gcode())


def test_machine_requires_feed_rate_before_moves() -> None:
    machine = WinderMachine(50.0)
    with pytest.raises(RuntimeError):
        machine.move({Axis.CARRIAGE: 1.0})


def test_machine_mandrel_accessors() -> None:
    machine = WinderMachine(42.0)
    assert machine.get_mandrel_diameter() == pytest.approx(42.0)
    machine.set_mandrel_diameter(50.0)
    assert machine.get_mandrel_diameter() == pytest.approx(50.0)
