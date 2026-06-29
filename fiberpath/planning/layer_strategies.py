"""Layer-specific planning helpers."""

from __future__ import annotations

from fiberpath.config.schemas import (
    HelicalLayer,
    HoopLayer,
    LayerModel,
    MandrelParameters,
    SkipLayer,
    TowParameters,
)

from .calculations import HelicalKinematics, compute_helical_kinematics
from .developed import (
    build_helical_developed_path,
    build_hoop_developed_path,
    lower_developed_path,
)
from .helpers import Axis
from .machine import WinderMachine
from .pattern import pattern_spec


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
    # Cut over to the developed-surface primitive (S3 #297): hoop is the alpha->90
    # case feeding the same lowering as helical. Byte-identical to the prior emitter.
    path = build_hoop_developed_path(pattern_spec(layer), mandrel_parameters, tow_parameters)
    lower_developed_path(machine, path)


def plan_helical_layer(
    machine: WinderMachine,
    layer: HelicalLayer,
    mandrel_parameters: MandrelParameters,
    tow_parameters: TowParameters,
    *,
    helical_kinematics: HelicalKinematics | None = None,
) -> None:
    # Cut over to the developed-surface primitive (S2 #296): build the (z, theta)
    # path from the declarative spec + the single kinematics source, then lower it
    # to Motion IR. Byte-identical to the prior imperative emitter.
    kinematics = helical_kinematics or compute_helical_kinematics(
        layer, mandrel_parameters, tow_parameters
    )
    path = build_helical_developed_path(pattern_spec(layer), kinematics, mandrel_parameters)
    lower_developed_path(machine, path)


def plan_skip_layer(machine: WinderMachine, layer: SkipLayer) -> None:
    machine.move(
        {
            Axis.CARRIAGE: 0.0,
            Axis.MANDREL: layer.mandrel_rotation,
            Axis.DELIVERY_HEAD: 0.0,
        }
    )
    machine.set_position({Axis.MANDREL: 0.0})
