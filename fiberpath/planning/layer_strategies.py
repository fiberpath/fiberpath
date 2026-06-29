"""Layer dispatch: lower any layer to Motion IR via the developed-surface path."""

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
    build_skip_developed_path,
    lower_developed_path,
)
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
    """Build the layer's developed-surface path and lower it to Motion IR.

    Every pattern type goes through one lowering (:func:`lower_developed_path`);
    the per-type builders differ only in how they shape the developed path.
    """
    spec = pattern_spec(layer)
    if isinstance(layer, HoopLayer):
        path = build_hoop_developed_path(spec, mandrel_parameters, tow_parameters)
    elif isinstance(layer, HelicalLayer):
        kinematics = helical_kinematics or compute_helical_kinematics(
            layer, mandrel_parameters, tow_parameters
        )
        path = build_helical_developed_path(spec, kinematics, mandrel_parameters)
    elif isinstance(layer, SkipLayer):
        path = build_skip_developed_path(spec)
    else:
        raise TypeError(f"Unsupported layer type: {layer}")
    lower_developed_path(machine, path)
