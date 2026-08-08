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

from .calculations import (
    ConeHelicalKinematics,
    HelicalKinematics,
    ProfileHelicalKinematics,
    compute_cone_helical_kinematics,
    compute_helical_kinematics,
    compute_profile_helical_kinematics,
)
from .developed import (
    build_cone_helical_developed_path,
    build_helical_developed_path,
    build_hoop_developed_path,
    build_profile_helical_developed_path,
    build_skip_developed_path,
    lower_developed_path,
)
from .machine import WinderMachine
from .pattern import pattern_spec
from .surface import Cone, VonKarman, surface_from_mandrel


def build_layer_summary(index: int, total: int, layer: LayerModel) -> str:
    return f"Layer {index} of {total}: {layer.wind_type}"


def dispatch_layer(
    machine: WinderMachine,
    layer: LayerModel,
    mandrel_parameters: MandrelParameters,
    tow_parameters: TowParameters,
    *,
    helical_kinematics: HelicalKinematics | None = None,
    cone_kinematics: ConeHelicalKinematics | None = None,
    profile_kinematics: ProfileHelicalKinematics | None = None,
) -> None:
    """Build the layer's developed-surface path and lower it to Motion IR.

    Every pattern type goes through one lowering (:func:`lower_developed_path`);
    the per-type builders differ only in how they shape the developed path. The
    mandrel's surface (cylinder or cone) selects the helical builder; skip is
    surface-independent and hoop-on-cone is not supported (the validators reject
    it before dispatch).
    """
    spec = pattern_spec(layer)
    surface = surface_from_mandrel(mandrel_parameters)
    if isinstance(surface, Cone):
        if isinstance(layer, HelicalLayer):
            cone_kin = cone_kinematics or compute_cone_helical_kinematics(
                layer, surface, tow_parameters
            )
            path = build_cone_helical_developed_path(spec, cone_kin)
        elif isinstance(layer, SkipLayer):
            path = build_skip_developed_path(spec)
        else:
            raise TypeError(f"hoop layers on a cone are not supported: {layer}")
    elif isinstance(surface, VonKarman):
        if isinstance(layer, HelicalLayer):
            profile_kin = profile_kinematics or compute_profile_helical_kinematics(
                layer, surface, tow_parameters
            )
            path = build_profile_helical_developed_path(spec, profile_kin)
        elif isinstance(layer, SkipLayer):
            path = build_skip_developed_path(spec)
        else:
            raise TypeError(f"hoop layers on a profile surface are not supported: {layer}")
    elif isinstance(layer, HoopLayer):
        path = build_hoop_developed_path(spec, mandrel_parameters, tow_parameters)
    elif isinstance(layer, HelicalLayer):
        cyl_kin = helical_kinematics or compute_helical_kinematics(
            layer, mandrel_parameters, tow_parameters
        )
        path = build_helical_developed_path(spec, cyl_kin, mandrel_parameters)
    elif isinstance(layer, SkipLayer):
        path = build_skip_developed_path(spec)
    else:
        raise TypeError(f"Unsupported layer type: {layer}")
    lower_developed_path(machine, path)
