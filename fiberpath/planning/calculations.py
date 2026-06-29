"""Reusable numeric helpers for planner kinematics."""

from __future__ import annotations

import math
from dataclasses import dataclass

from fiberpath.config.schemas import HelicalLayer, MandrelParameters, TowParameters
from fiberpath.math_utils import deg_to_rad

from .surface import Cone, Cylinder


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


class ConeReachabilityError(ValueError):
    """A geodesic at the requested angle cannot reach the cone's small end.

    Raised when the Clairaut constant ``C = r0·sin(alpha)`` exceeds the smallest
    radius: the geodesic turns around before reaching it (``sin(alpha) > 1`` would
    be required). S3 surfaces this through the layer validators.
    """


@dataclass(slots=True)
class ConeHelicalKinematics:
    r0: float
    r1: float
    length: float
    half_angle_rad: float
    #: Clairaut constant ``C = r0·sin(alpha_ref)`` in length units (mm).
    clairaut_const: float
    alpha_ref_deg: float
    num_circuits: int
    pattern_step_degrees: float


def compute_cone_helical_kinematics(
    layer: HelicalLayer,
    surface: Cone,
    tow_parameters: TowParameters,
) -> ConeHelicalKinematics:
    """Geodesic (Clairaut) kinematics for a helical layer on a frustum.

    The wind angle is anchored at the large end ``r0`` (z=0): ``C = r0·sin(alpha)``
    is the Clairaut invariant, so the local angle ``alpha(z) = asin(C/r(z))`` grows
    toward the small radius. Assumes a reducing frustum (``r0 >= r1``); expanding
    cones are deferred to a later slice.
    """
    r0, r1, length = surface.r0, surface.r1, surface.length
    if r0 == r1:
        # A zero-taper cone is a cylinder; the geodesic integral divides by
        # sin(half_angle). Model it as a Cylinder instead (S3's .wind mapping does).
        raise ValueError("zero-taper cone (r0 == r1); model a cylinder as Cylinder, not Cone")
    # minimal: reducing-frustum orientation only (r0 is the large/anchor end).
    # Expanding cones (r1 > r0) and multi-segment profiles are a later slice;
    # guard the contract rather than emit small-end-anchored (wrong) output.
    if r1 > r0:
        raise ValueError(
            f"expanding cone (r1={r1} > r0={r0}) is not supported yet; "
            "the wind angle anchors at the large end r0 (mount the large end at z=0)"
        )
    alpha = layer.wind_angle
    clairaut_const = r0 * math.sin(deg_to_rad(alpha))

    if clairaut_const > r1:
        raise ConeReachabilityError(
            f"wind angle {alpha}° (Clairaut C={clairaut_const:.4g}mm) exceeds the "
            f"small-end radius {r1:.4g}mm; the geodesic cannot reach the small end. "
            f"Reduce the wind angle to <= {math.degrees(math.asin(r1 / r0)):.4g}°."
        )

    half_angle_rad = math.atan((r0 - r1) / length)

    # Coverage anchored at the large end (the no-gap-everywhere choice: the count
    # of circuits needed to tile a parallel, 2*pi*sqrt(r^2 - C^2)/tow_width, is
    # maximised at the largest radius). Reduces to the cylinder formula at r0.
    circumference0 = 2.0 * math.pi * r0
    tow_arc_length = tow_parameters.width / math.cos(deg_to_rad(alpha))
    num_circuits = math.ceil(circumference0 / tow_arc_length)
    pattern_step_degrees = 360.0 * (1 / num_circuits)

    return ConeHelicalKinematics(
        r0=r0,
        r1=r1,
        length=length,
        half_angle_rad=half_angle_rad,
        clairaut_const=clairaut_const,
        alpha_ref_deg=alpha,
        num_circuits=num_circuits,
        pattern_step_degrees=pattern_step_degrees,
    )


def _cone_radius_at(z: float, kin: ConeHelicalKinematics) -> float:
    return kin.r0 + (kin.r1 - kin.r0) * (z / kin.length)


def cone_geodesic_theta_deg(z: float, kin: ConeHelicalKinematics) -> float:
    """Absolute mandrel rotation (deg) at axial ``z`` along the geodesic, ``theta(0)=0``.

    Closed form (no ODE): ``theta(z) = (1/sin phi)·[arccos(C/r0) - arccos(C/r(z))]``.
    Monotonically increasing in ``z`` for a reducing frustum.
    """
    c = kin.clairaut_const
    return math.degrees(
        (math.acos(c / kin.r0) - math.acos(min(1.0, c / _cone_radius_at(z, kin))))
        / math.sin(kin.half_angle_rad)
    )


def cone_local_alpha_deg(z: float, kin: ConeHelicalKinematics) -> float:
    """Local fiber angle (deg from the meridian) at axial ``z``: ``asin(C/r(z))``."""
    return math.degrees(math.asin(min(1.0, kin.clairaut_const / _cone_radius_at(z, kin))))
