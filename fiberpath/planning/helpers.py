"""Utility helpers shared by planner components."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from fiberpath.math_utils import strip_precision

if TYPE_CHECKING:
    from fiberpath.gcode.dialects import AxisMapping


class Axis(Enum):
    CARRIAGE = "carriage"
    MANDREL = "mandrel"
    DELIVERY_HEAD = "delivery_head"


Coordinate = dict[Axis, float]


def get_axis_letter(axis: Axis, mapping: AxisMapping) -> str:
    """Get G-code axis letter for logical axis based on dialect mapping."""
    return {
        Axis.CARRIAGE: mapping.carriage,
        Axis.MANDREL: mapping.mandrel,
        Axis.DELIVERY_HEAD: mapping.delivery_head,
    }[axis]


def serialize_coordinate(coordinate: Coordinate) -> str:
    serialized = " ".join(
        f"{axis.value}:{strip_precision(value)}" for axis, value in coordinate.items()
    )
    return "{" + serialized + "}"


def interpolate_coordinates(start: Coordinate, end: Coordinate, steps: int) -> list[Coordinate]:
    if steps <= 0:
        raise ValueError("Steps cannot be less than 1")
    if steps == 1:
        return [end]

    coordinates: list[Coordinate] = []
    delta = {axis: (end[axis] - start[axis]) / (steps - 1) for axis in Axis}
    for step in range(steps):
        coordinates.append({axis: start[axis] + step * delta[axis] for axis in Axis})
    return coordinates
