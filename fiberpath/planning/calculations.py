"""Reusable numeric helpers for planner kinematics."""

from __future__ import annotations

import math
from dataclasses import dataclass

from fiberpath.config.schemas import HelicalLayer, MandrelParameters, TowParameters
from fiberpath.math_utils import deg_to_rad

from .surface import Cone, Cylinder, VonKarman


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


# --------------------------------------------------------------------------- #
# Non-developable (profile) geodesic — Stage 3b (#326)                         #
#                                                                             #
# A cone's theta(z) is closed form only because it unrolls flat. A general    #
# surface of revolution (VonKarman) needs the *same* Clairaut relation        #
# integrated numerically:                                                     #
#     theta(z) = integral C / (r*sqrt(r^2 - C^2)) * sqrt(1 + r'^2) dz ,        #
# anchored at the base (largest radius), C = base_radius * sin(alpha). The     #
# geodesic turns around at r = C (theta diverges), so every profile helical    #
# leaves a bare polar cap of diameter ~2C; full tip coverage is Phase 2 (#327).#
# --------------------------------------------------------------------------- #

#: Radial margin (mm) above the Clairaut radius C where the pass turns around.
# minimal: a small conservative guard so alpha stays < 90 and theta stays finite; the
# wound band reaches close to the cap (bare cap ~ 2C). Phase 2 (#327) sets this from
# the friction/slip limit.
_CAP_GUARD_MM = 0.5
#: Fine integration-grid step (mm) for the cumulative theta table — much finer than
# the ~1 mm emitted lay stations. Sized so the table (0.05 mm trapezoid + linear
# interpolation) holds theta(z) to well under 1e-3 deg even in the steep near-cap
# region; trapezoid error is O(h^2), so this is ~4x tighter than a 0.1 mm grid.
_THETA_GRID_STEP_MM = 0.05


class ProfileReachabilityError(ValueError):
    """A helical layer leaves no usable wound band on a profile surface.

    The geodesic turns around at the Clairaut radius ``C = base_radius*sin(alpha)``;
    if ``C`` plus the cap guard is already at/above the base radius there is no band
    to wind. Surfaced to the operator through the layer validators.
    """


@dataclass(slots=True)
class ProfileHelicalKinematics:
    surface: VonKarman
    #: Clairaut constant ``C = base_radius*sin(alpha_ref)`` (mm).
    clairaut_const: float
    alpha_ref_deg: float
    #: Axial extent of the wound band [0, z_cap] (mm); the pass turns around here, not
    # at the tip. Floored to the integer 1 mm station lattice for a stable move count.
    z_cap: float
    #: Diameter of the bare polar cap actually left (2*r(z_cap)); ~2C at a small guard.
    cap_diameter: float
    num_circuits: int
    pattern_step_degrees: float
    #: Cumulative geodesic rotation table over [0, z_cap] on the fine grid (deg),
    # interpolated by ``profile_geodesic_theta_deg``. Parallel, monotone in z.
    grid_z: tuple[float, ...]
    cum_theta_deg: tuple[float, ...]


def _profile_theta_integrand(surface: VonKarman, z: float, c: float) -> float:
    """Geodesic ``d(theta)/dz`` (rad/mm) at ``z``: ``C / (r*sqrt(r^2-C^2)) * sqrt(1+r'^2)``.

    ``sqrt(r^2 - C^2)`` uses the factored ``((r-C)*(r+C))**0.5`` (better conditioned as
    r -> C than ``r*r - C*C``); ``sqrt(1 + r'^2)`` uses ``math.hypot``. Both avoid the
    ``math.sqrt`` call reserved to ``metrics.py`` by the Motion IR single-source guard.
    """
    r = surface.radius_at(z)
    r_prime = surface.radius_slope_at(z)
    meridian = math.hypot(1.0, r_prime)
    radial = float(((r - c) * (r + c)) ** 0.5)  # float(): typeshed types ** as Any
    return c / (r * radial) * meridian


def _profile_z_at_radius(surface: VonKarman, target_r: float) -> float:
    """Axial ``z`` where ``r(z) == target_r``, by bisection.

    ``r(z)`` decreases monotonically from ``base_radius`` (z=0) to 0 (z=length), so a
    single root exists for ``0 < target_r < base_radius``.
    """
    lo, hi = 0.0, surface.length
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if surface.radius_at(mid) > target_r:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def compute_profile_helical_kinematics(
    layer: HelicalLayer,
    surface: VonKarman,
    tow_parameters: TowParameters,
) -> ProfileHelicalKinematics:
    """Geodesic (Clairaut) kinematics for a helical layer on a non-developable profile.

    Anchored at the base (largest radius): ``C = base_radius*sin(alpha)`` is the Clairaut
    invariant, ``alpha(z) = asin(C/r(z))`` grows toward the tip, and ``theta(z)`` is the
    numeric Clairaut quadrature (fine cumulative table). The pass turns around at the
    cap radius ``C + guard`` (not the tip); the bare-cap diameter is reported.
    """
    r_base = surface.base_radius
    alpha = layer.wind_angle
    clairaut_const = r_base * math.sin(deg_to_rad(alpha))
    r_stop = clairaut_const + _CAP_GUARD_MM
    if r_base <= r_stop:
        raise ProfileReachabilityError(
            f"wind angle {alpha}° (Clairaut C={clairaut_const:.4g}mm) leaves no usable "
            f"wound band: the turnaround radius plus guard ({r_stop:.4g}mm) is at or above "
            f"the base radius {r_base:.4g}mm. Reduce the wind angle."
        )

    # Wound band [0, z_cap]. Snap-floor z_cap to the integer 1 mm station lattice so the
    # emitted station count (and the len(moves) equivalence gate) agrees across the 3-OS
    # libm matrix: the +1e-6 tolerance keeps a crossing that lands within float noise of
    # an integer from flooring to different integers on different platforms. Flooring
    # keeps z_cap near the r_stop = C + guard crossing, so r(z_cap) - C stays ~guard mm
    # (>> 0) — the geodesic never approaches the theta singularity at r = C.
    z_cap = float(math.floor(_profile_z_at_radius(surface, r_stop) + 1e-6))
    if z_cap < 1.0:
        raise ProfileReachabilityError(
            f"wind angle {alpha}° leaves a wound band shorter than one station "
            f"(z_cap={z_cap}mm); reduce the wind angle."
        )

    # Fine cumulative-theta table over [0, z_cap] (trapezoid).
    n = max(2, math.ceil(z_cap / _THETA_GRID_STEP_MM))
    grid_z = tuple(z_cap * i / n for i in range(n + 1))
    cum_theta_deg: list[float] = [0.0]
    cum = 0.0
    prev = _profile_theta_integrand(surface, grid_z[0], clairaut_const)
    for i in range(1, n + 1):
        cur = _profile_theta_integrand(surface, grid_z[i], clairaut_const)
        cum += 0.5 * (prev + cur) * (grid_z[i] - grid_z[i - 1])
        cum_theta_deg.append(math.degrees(cum))
        prev = cur

    # Coverage anchored at the base (largest radius), same rule as the cone.
    circumference0 = 2.0 * math.pi * r_base
    tow_arc_length = tow_parameters.width / math.cos(deg_to_rad(alpha))
    num_circuits = math.ceil(circumference0 / tow_arc_length)
    pattern_step_degrees = 360.0 * (1 / num_circuits)

    return ProfileHelicalKinematics(
        surface=surface,
        clairaut_const=clairaut_const,
        alpha_ref_deg=alpha,
        z_cap=z_cap,
        cap_diameter=2.0 * surface.radius_at(z_cap),
        num_circuits=num_circuits,
        pattern_step_degrees=pattern_step_degrees,
        grid_z=grid_z,
        cum_theta_deg=tuple(cum_theta_deg),
    )


def profile_geodesic_theta_deg(z: float, kin: ProfileHelicalKinematics) -> float:
    """Absolute mandrel rotation (deg) at axial ``z``, interpolating the cumulative table.

    ``theta(0) = 0``, monotone increasing toward the cap. ``z`` outside ``[0, z_cap]`` is
    clamped to the table ends (the builder samples within the band).
    """
    grid, theta = kin.grid_z, kin.cum_theta_deg
    if z <= grid[0]:
        return theta[0]
    if z >= grid[-1]:
        return theta[-1]
    lo, hi = 0, len(grid) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if grid[mid] <= z:
            lo = mid
        else:
            hi = mid
    frac = (z - grid[lo]) / (grid[hi] - grid[lo])
    return theta[lo] + frac * (theta[hi] - theta[lo])


def profile_local_alpha_deg(z: float, kin: ProfileHelicalKinematics) -> float:
    """Local fiber angle (deg from the meridian) at axial ``z``: ``asin(C/r(z))``."""
    return math.degrees(math.asin(min(1.0, kin.clairaut_const / kin.surface.radius_at(z))))
