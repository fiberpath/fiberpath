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
#: Integrator ceiling for the non-geodesic march (deg). The turnaround is a *coordinate*
# singularity (dalpha/dz ∝ 1/cos(alpha) → ∞ at 90°, at every friction level), so the RK4
# march stops at this fixed angle — comfortably in the Lipschitz region — and the exact
# crossing is bisected within the last cell. Phase 2 (#327) non-geodesic winding only.
_ALPHA_MAX_DEG = 88.0
#: Max fibre-angle advance (deg) per adaptive RK4 step. The step shrinks to hold this bound
# where dalpha/dz stiffens (the base r'' spike and the near-cap tail), keeping z_cross
# converged and platform-stable; the flat region is unaffected (capped at the grid step).
_ALPHA_STEP_CAP_DEG = 0.1
#: Where the alpha-march begins (mm). The analytic r'' diverges exactly at the base (z=0);
# starting a hair in avoids it. Small enough that the un-marched [0, z_start] seed shifts
# z_cross by << the floor tolerance (verified by z_start-refinement in the tests).
_MARCH_START_MM = 1.0e-3


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
    #: Non-geodesic (#327) only: local fibre angle alpha(z) (deg), parallel to ``grid_z``,
    # read by ``profile_local_alpha_deg`` when present. ``None`` on a geodesic layer, whose
    # angle is the closed-form ``asin(C/r)`` instead of a marched table.
    alpha_table: tuple[float, ...] | None = None
    #: Turnaround slip demand at the cap: ``|r'(z_cap)|`` (the friction the circumferential
    # reversal needs). Reported by the Phase-2 validator; ``> mu`` flags a Phase-3 (#328)
    # 4th-axis delivery. Grows toward the tip.
    cap_dwell_slope: float = 0.0


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


# --------------------------------------------------------------------------- #
# Non-geodesic (friction-assisted) profile winding — Stage 3b Phase 2 (#327)   #
#                                                                             #
# Letting the fibre slip up to k_g/k_n = lambda lets a pass climb PAST the     #
# geodesic turnaround at r=C toward the tip. There is no closed form even on   #
# a developable surface, so alpha(z) is forward-integrated (RK4) alongside      #
# theta(z). lambda = lambda_user >= 0 steers toward the tip (engine sign is    #
# -lambda). lambda = 0 recovers the geodesic exactly (the -sin(a)r'/r term).   #
# --------------------------------------------------------------------------- #


def _nongeodesic_derivs(
    surface: VonKarman, z: float, alpha: float, friction_lambda: float
) -> tuple[float, float]:
    """``(dalpha/dz, dtheta/dz)`` for the non-geodesic ODE at ``(z, alpha)`` (rad, rad/mm).

        dalpha/dz = [ -lambda·k_n·sqrt(1+r'^2) - sin(a)·r'/r ] / cos(a)
        k_n       = -r''·cos^2(a)/(1+r'^2)^{3/2} + sin^2(a)/(r·sqrt(1+r'^2))
        dtheta/dz = tan(a)·sqrt(1+r'^2)/r

    ``sqrt(1+r'^2)`` is ``math.hypot`` and ``(1+r'^2)^{3/2}`` is ``meridian**3`` — neither
    uses the ``math.sqrt`` call reserved to metrics.py by the Motion IR single-source guard.
    """
    r = surface.radius_at(z)
    r_prime = surface.radius_slope_at(z)
    r_curv = surface.radius_curvature_at(z)
    meridian = math.hypot(1.0, r_prime)  # sqrt(1 + r'^2)
    sin_a, cos_a = math.sin(alpha), math.cos(alpha)
    k_n = -r_curv * cos_a * cos_a / meridian**3 + sin_a * sin_a / (r * meridian)
    d_alpha = (-friction_lambda * k_n * meridian - sin_a * r_prime / r) / cos_a
    d_theta = (sin_a / cos_a) * meridian / r
    return d_alpha, d_theta


def _nongeodesic_rk4_step(
    surface: VonKarman, z: float, alpha: float, theta: float, dz: float, friction_lambda: float
) -> tuple[float, float]:
    """One classic RK4 step of the coupled ``(alpha, theta)`` system over ``[z, z+dz]``."""
    a1, t1 = _nongeodesic_derivs(surface, z, alpha, friction_lambda)
    a2, t2 = _nongeodesic_derivs(surface, z + dz / 2, alpha + dz / 2 * a1, friction_lambda)
    a3, t3 = _nongeodesic_derivs(surface, z + dz / 2, alpha + dz / 2 * a2, friction_lambda)
    a4, t4 = _nongeodesic_derivs(surface, z + dz, alpha + dz * a3, friction_lambda)
    return (
        alpha + dz / 6 * (a1 + 2 * a2 + 2 * a3 + a4),
        theta + dz / 6 * (t1 + 2 * t2 + 2 * t3 + t4),
    )


def _integrate_nongeodesic(
    surface: VonKarman,
    alpha_base_deg: float,
    friction_lambda: float,
    alpha_step_cap_deg: float = _ALPHA_STEP_CAP_DEG,
    alpha_max_deg: float = _ALPHA_MAX_DEG,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Adaptive RK4-march of ``(alpha, theta)`` from the base to the ``alpha_max`` crossing.

    Returns parallel tuples ``(grid_z, alpha_deg, cum_theta_deg)`` over ``[0, z_cross]``, where
    ``z_cross`` (the last grid point) is where ``alpha`` reaches ``alpha_max``, pinned by
    bisection within the final cell so the floored ``z_cap`` is deterministic.

    **Adaptive step (the reason a fixed step fails).** ``dalpha/dz`` blows up in two places:
    near the base ``r'' ∝ z^{-1/2}`` spikes the friction term, and near the cap the geodesic
    term ``sin(a)·r'/r`` diverges as ``r → 0`` (and ``1/cos(a)`` as ``a → 90``). A fixed
    0.05 mm step there advances ``alpha`` by *degrees* per step — an RK4 stage can overshoot
    90°, sign-flipping ``dalpha/dz`` — so ``z_cross`` came out mm-wrong and step-dependent. Each
    step is instead capped to advance ``alpha`` by at most ``alpha_step_cap_deg`` (and by
    ``_THETA_GRID_STEP_MM`` in the flat region), so the step shrinks smoothly where the ODE
    stiffens and ``z_cross`` converges. The march starts a hair in from the base (``r''``
    diverges at z=0); the sub-mm seed sits far below the ~1 mm station lattice the builder
    samples, and ``theta(0)`` is anchored at 0.
    """
    alpha_max = math.radians(alpha_max_deg)
    alpha_step_cap = math.radians(alpha_step_cap_deg)
    alpha0 = math.radians(alpha_base_deg)

    # Base anchor at z=0, then begin marching a hair in (r'' is singular exactly at the base).
    grid_z = [0.0, _MARCH_START_MM]
    alpha_rad = [alpha0, alpha0]
    theta_rad = [0.0, 0.0]  # theta over [0, z_start] is ~1e-5 rad — negligible, anchored at 0.
    z, alpha, theta = _MARCH_START_MM, alpha0, 0.0

    while alpha < alpha_max and z < surface.length:
        d_alpha, _dt = _nongeodesic_derivs(surface, z, alpha, friction_lambda)
        # Bound the per-step fibre-angle advance; cap at the flat-region step and the tip.
        step = _THETA_GRID_STEP_MM
        if abs(d_alpha) > 1e-12:
            step = min(step, alpha_step_cap / abs(d_alpha))
        step = min(step, surface.length - z)
        a_next, t_next = _nongeodesic_rk4_step(surface, z, alpha, theta, step, friction_lambda)

        if a_next >= alpha_max:
            # Bisect [z, z+step] for the exact alpha == alpha_max crossing (deterministic).
            lo, hi = 0.0, step
            for _ in range(80):
                mid = 0.5 * (lo + hi)
                a_mid, _tm = _nongeodesic_rk4_step(surface, z, alpha, theta, mid, friction_lambda)
                if a_mid < alpha_max:
                    lo = mid
                else:
                    hi = mid
            step = 0.5 * (lo + hi)
            alpha, theta = _nongeodesic_rk4_step(surface, z, alpha, theta, step, friction_lambda)
            z += step
            grid_z.append(z)
            alpha_rad.append(alpha)
            theta_rad.append(theta)
            break

        z += step
        alpha, theta = a_next, t_next
        grid_z.append(z)
        alpha_rad.append(alpha)
        theta_rad.append(theta)

    return (
        tuple(grid_z),
        tuple(math.degrees(a) for a in alpha_rad),
        tuple(math.degrees(t) for t in theta_rad),
    )


def compute_profile_helical_kinematics(
    layer: HelicalLayer,
    surface: VonKarman,
    tow_parameters: TowParameters,
    friction_lambda: float = 0.0,
) -> ProfileHelicalKinematics:
    """Kinematics for a helical layer on a non-developable profile.

    ``friction_lambda == 0`` (the default) is the **geodesic** (Phase 1, #326) path: anchored
    at the base, ``C = base_radius*sin(alpha)`` is the Clairaut invariant, ``alpha(z)`` is the
    closed-form ``asin(C/r)``, and ``theta(z)`` is the numeric Clairaut quadrature; the pass
    turns around at the cap radius ``C + guard`` (not the tip). ``friction_lambda > 0`` is the
    **non-geodesic** (Phase 2, #327) path: ``alpha(z)`` and ``theta(z)`` are forward-integrated
    so the pass climbs past the geodesic cap toward the tip, stopping at the ``alpha_max``
    turnaround; the marched ``alpha`` table and the cap slip demand ``|r'(z_cap)|`` are reported.
    """
    r_base = surface.base_radius
    alpha = layer.wind_angle
    clairaut_const = r_base * math.sin(deg_to_rad(alpha))

    if friction_lambda != 0.0:
        return _compute_nongeodesic_kinematics(
            layer, surface, tow_parameters, friction_lambda, clairaut_const
        )

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
        cap_dwell_slope=abs(surface.radius_slope_at(z_cap)),
    )


def _compute_nongeodesic_kinematics(
    layer: HelicalLayer,
    surface: VonKarman,
    tow_parameters: TowParameters,
    friction_lambda: float,
    clairaut_const: float,
) -> ProfileHelicalKinematics:
    """Friction-assisted (``lambda > 0``) kinematics — the marched non-geodesic path (#327).

    ``clairaut_const`` is retained as the base-anchor reference only (it is NOT an invariant
    once the path leaves the geodesic). The wound band ends at the marched ``alpha_max``
    turnaround, floored to the integer station lattice like the geodesic cap.
    """
    alpha = layer.wind_angle
    grid_z, alpha_deg, cum_theta_deg = _integrate_nongeodesic(surface, alpha, friction_lambda)

    z_cap = float(math.floor(grid_z[-1] + 1e-6))
    if z_cap < 1.0:
        raise ProfileReachabilityError(
            f"wind angle {alpha}° with friction lambda={friction_lambda:g} leaves a wound band "
            f"shorter than one station (z_cap={z_cap}mm); reduce the wind angle."
        )

    # Coverage is set at the base (largest radius), same rule as the geodesic path — friction
    # changes the reachable cap, not the base circuit count.
    circumference0 = 2.0 * math.pi * surface.base_radius
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
        cum_theta_deg=cum_theta_deg,
        alpha_table=alpha_deg,
        cap_dwell_slope=abs(surface.radius_slope_at(z_cap)),
    )


def _interp_table(z: float, grid: tuple[float, ...], values: tuple[float, ...]) -> float:
    """Linear interpolation of ``values`` sampled at monotone ``grid``; clamped at both ends."""
    if z <= grid[0]:
        return values[0]
    if z >= grid[-1]:
        return values[-1]
    lo, hi = 0, len(grid) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if grid[mid] <= z:
            lo = mid
        else:
            hi = mid
    frac = (z - grid[lo]) / (grid[hi] - grid[lo])
    return values[lo] + frac * (values[hi] - values[lo])


def profile_geodesic_theta_deg(z: float, kin: ProfileHelicalKinematics) -> float:
    """Absolute mandrel rotation (deg) at axial ``z``, interpolating the cumulative table.

    ``theta(0) = 0``, monotone increasing toward the cap. ``z`` outside ``[0, z_cap]`` is
    clamped to the table ends (the builder samples within the band). Serves both the geodesic
    quadrature table and the non-geodesic marched table (the field is shared).
    """
    return _interp_table(z, kin.grid_z, kin.cum_theta_deg)


def profile_local_alpha_deg(z: float, kin: ProfileHelicalKinematics) -> float:
    """Local fiber angle (deg from the meridian) at axial ``z``.

    Non-geodesic layers (#327) carry a marched ``alpha_table`` and interpolate it; geodesic
    layers use the closed-form Clairaut angle ``asin(C/r(z))``.
    """
    if kin.alpha_table is not None:
        return _interp_table(z, kin.grid_z, kin.alpha_table)
    return math.degrees(math.asin(min(1.0, kin.clairaut_const / kin.surface.radius_at(z))))
