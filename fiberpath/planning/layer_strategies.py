"""Layer-specific planning helpers."""

from __future__ import annotations

import logging
import math

from fiberpath.config.schemas import (
    HelicalLayer,
    HoopLayer,
    LayerModel,
    MandrelParameters,
    SkipLayer,
    TowParameters,
)
from fiberpath.math_utils import rad_to_deg

from .calculations import HelicalKinematics, compute_helical_kinematics
from .helpers import Axis
from .machine import WinderMachine

LOGGER = logging.getLogger(__name__)


def build_layer_summary(index: int, total: int, layer: LayerModel) -> str:
    return f"Layer {index} of {total}: {layer.wind_type}"


def dispatch_layer(
    machine: WinderMachine,
    layer: LayerModel,
    mandrel_parameters: MandrelParameters,
    tow_parameters: TowParameters,
    *,
    helical_kinematics: HelicalKinematics | None = None,
) -> None:
    if isinstance(layer, HoopLayer):
        plan_hoop_layer(machine, layer, mandrel_parameters, tow_parameters)
        return
    if isinstance(layer, HelicalLayer):
        plan_helical_layer(
            machine,
            layer,
            mandrel_parameters,
            tow_parameters,
            helical_kinematics=helical_kinematics,
        )
        return
    if isinstance(layer, SkipLayer):
        plan_skip_layer(machine, layer)
        return
    raise TypeError(f"Unsupported layer type: {layer}")


def plan_hoop_layer(
    machine: WinderMachine,
    layer: HoopLayer,
    mandrel_parameters: MandrelParameters,
    tow_parameters: TowParameters,
) -> None:
    lock_degrees = 180.0
    wind_angle = 90.0 - rad_to_deg(math.atan(mandrel_parameters.diameter / tow_parameters.width))
    mandrel_rotations = mandrel_parameters.wind_length / tow_parameters.width
    far_mandrel = lock_degrees + mandrel_rotations * 360.0
    far_lock = far_mandrel + lock_degrees
    near_mandrel = far_lock + mandrel_rotations * 360.0
    near_lock = near_mandrel + lock_degrees

    machine.move({Axis.CARRIAGE: 0.0, Axis.MANDREL: lock_degrees, Axis.DELIVERY_HEAD: 0.0})
    machine.move({Axis.DELIVERY_HEAD: -wind_angle})
    machine.move({Axis.CARRIAGE: mandrel_parameters.wind_length, Axis.MANDREL: far_mandrel})
    machine.move({Axis.MANDREL: far_lock, Axis.DELIVERY_HEAD: 0.0})

    if layer.terminal:
        return

    machine.move({Axis.DELIVERY_HEAD: wind_angle})
    machine.move({Axis.CARRIAGE: 0.0, Axis.MANDREL: near_mandrel})
    machine.move({Axis.MANDREL: near_lock, Axis.DELIVERY_HEAD: 0.0})
    machine.zero_axes(near_lock)


def plan_helical_layer(
    machine: WinderMachine,
    layer: HelicalLayer,
    mandrel_parameters: MandrelParameters,
    tow_parameters: TowParameters,
    *,
    helical_kinematics: HelicalKinematics | None = None,
) -> None:
    delivery_head_pass_start_angle = -10.0
    lead_out_degrees = layer.lead_out_degrees
    wind_lead_in_mm = layer.lead_in_mm
    lock_degrees = layer.lock_degrees
    delivery_head_angle = -1.0 * (90.0 - layer.wind_angle)
    pattern_number = layer.pattern_number

    kinematics = helical_kinematics or compute_helical_kinematics(
        layer, mandrel_parameters, tow_parameters
    )
    num_circuits = kinematics.num_circuits
    pattern_step_degrees = kinematics.pattern_step_degrees
    pass_rotation_degrees = kinematics.pass_rotation_degrees
    lead_in_degrees = kinematics.lead_in_degrees
    main_pass_degrees = kinematics.main_pass_degrees
    number_of_patterns = num_circuits / pattern_number
    start_position_increment = layer.skip_index * (360.0 / pattern_number)
    pass_parameters = [
        {
            "delivery_head_sign": 1,
            "lead_in_end_mm": wind_lead_in_mm,
            "full_pass_end_mm": mandrel_parameters.wind_length,
        },
        {
            "delivery_head_sign": -1,
            "lead_in_end_mm": mandrel_parameters.wind_length - wind_lead_in_mm,
            "full_pass_end_mm": 0.0,
        },
    ]

    LOGGER.debug("Helical wind with %s circuits", num_circuits)

    if not layer.skip_initial_near_lock:
        machine.move({Axis.CARRIAGE: 0.0, Axis.MANDREL: lock_degrees, Axis.DELIVERY_HEAD: 0.0})
        machine.set_position({Axis.MANDREL: 0.0})

    mandrel_position = 0.0
    patterns = int(number_of_patterns)
    for pattern_index in range(patterns):
        for in_pattern_index in range(pattern_number):
            machine.insert_comment(
                f"\tPattern: {pattern_index + 1}/{patterns} "
                f"Circuit: {in_pattern_index + 1}/{pattern_number}"
            )

            for pass_params in pass_parameters:
                sign = pass_params["delivery_head_sign"]
                machine.move({Axis.MANDREL: mandrel_position, Axis.DELIVERY_HEAD: 0.0})
                machine.move({Axis.DELIVERY_HEAD: sign * delivery_head_pass_start_angle})

                mandrel_position += lead_in_degrees
                machine.move(
                    {
                        Axis.CARRIAGE: pass_params["lead_in_end_mm"],
                        Axis.MANDREL: mandrel_position,
                        Axis.DELIVERY_HEAD: sign * delivery_head_angle,
                    }
                )

                mandrel_position += main_pass_degrees
                machine.move(
                    {
                        Axis.CARRIAGE: pass_params["full_pass_end_mm"],
                        Axis.MANDREL: mandrel_position,
                    }
                )

                mandrel_position += lead_out_degrees
                machine.move(
                    {
                        Axis.MANDREL: mandrel_position,
                        Axis.DELIVERY_HEAD: sign * delivery_head_pass_start_angle,
                    }
                )

                mandrel_position += (
                    lock_degrees - lead_out_degrees - (pass_rotation_degrees % 360.0)
                )

            mandrel_position += start_position_increment

        mandrel_position += pattern_step_degrees

    mandrel_position += lock_degrees
    machine.move({Axis.MANDREL: mandrel_position, Axis.DELIVERY_HEAD: 0.0})
    machine.zero_axes(mandrel_position)


def plan_skip_layer(machine: WinderMachine, layer: SkipLayer) -> None:
    machine.move(
        {
            Axis.CARRIAGE: 0.0,
            Axis.MANDREL: layer.mandrel_rotation,
            Axis.DELIVERY_HEAD: 0.0,
        }
    )
    machine.set_position({Axis.MANDREL: 0.0})
