"""Reusable numeric helpers for planner kinematics."""

from __future__ import annotations

import math
from dataclasses import dataclass

from fiberpath.config.schemas import HelicalLayer, MandrelParameters, TowParameters
from fiberpath.math_utils import deg_to_rad

from .surface import Cylinder


@dataclass(slots=True)
class HelicalKinematics:
    mandrel_circumference: float
    tow_arc_length: float
    num_circuits: int
    pattern_step_degrees: float
    pass_rotation_mm: float
    pass_rotation_degrees: float
    pass_degrees_per_mm: float
    lead_in_degrees: float
    main_pass_degrees: float


def compute_helical_kinematics(
    layer: HelicalLayer,
    mandrel_parameters: MandrelParameters,
    tow_parameters: TowParameters,
) -> HelicalKinematics:
    surface = Cylinder(radius=mandrel_parameters.diameter / 2.0)
    mandrel_circumference = surface.circumference_at(0.0)
    tow_arc_length = tow_parameters.width / math.cos(deg_to_rad(layer.wind_angle))
    num_circuits = math.ceil(mandrel_circumference / tow_arc_length)
    pattern_step_degrees = 360.0 * (1 / num_circuits)
    pass_rotation_mm = mandrel_parameters.wind_length * math.tan(deg_to_rad(layer.wind_angle))
    pass_rotation_degrees = 360.0 * (pass_rotation_mm / mandrel_circumference)
    pass_degrees_per_mm = pass_rotation_degrees / mandrel_parameters.wind_length
    lead_in_degrees = pass_degrees_per_mm * layer.lead_in_mm
    main_pass_degrees = pass_degrees_per_mm * (mandrel_parameters.wind_length - layer.lead_in_mm)

    return HelicalKinematics(
        mandrel_circumference=mandrel_circumference,
        tow_arc_length=tow_arc_length,
        num_circuits=num_circuits,
        pattern_step_degrees=pattern_step_degrees,
        pass_rotation_mm=pass_rotation_mm,
        pass_rotation_degrees=pass_rotation_degrees,
        pass_degrees_per_mm=pass_degrees_per_mm,
        lead_in_degrees=lead_in_degrees,
        main_pass_degrees=main_pass_degrees,
    )
