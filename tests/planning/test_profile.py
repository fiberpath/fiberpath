"""Von Kármán (profile) geodesic — surface kinematics and the numeric Clairaut quadrature.

Stage 3b Phase 1 (#326). These drive the profile kinematics directly (no schema, no
dispatch yet) and validate the one genuinely new piece — the numeric geodesic
theta(z) — against the known-good cone closed form and against direct quadrature.
"""

from __future__ import annotations

import dataclasses
import math
from itertools import pairwise
from pathlib import Path

import pytest
from _equivalence import (
    assert_profile_circuit_count,
    assert_profile_coverage,
    assert_profile_geometry,
    profile_helical_layer_moves,
)
from fiberpath.config import load_wind_definition
from fiberpath.config.schemas import (
    HelicalLayer,
    MandrelParameters,
    TowParameters,
    WindDefinition,
)
from fiberpath.gcode.dialects import MARLIN_XAB_STANDARD
from fiberpath.gcode.reader import read_program
from fiberpath.gcode.serializer import serialize
from fiberpath.planning.calculations import (
    ProfileHelicalKinematics,
    ProfileReachabilityError,
    _integrate_nongeodesic,
    _profile_theta_integrand,
    compute_cone_helical_kinematics,
    compute_profile_helical_kinematics,
    cone_geodesic_theta_deg,
    profile_geodesic_theta_deg,
    profile_local_alpha_deg,
)
from fiberpath.planning.exceptions import LayerValidationError
from fiberpath.planning.pattern import helical_spec
from fiberpath.planning.planner import _profile_cap_comment, plan_wind
from fiberpath.planning.surface import Cone, VonKarman, surface_from_mandrel
from fiberpath.planning.validators import (
    validate_cone_helical_layer,
    validate_helical_layer,
    validate_layer,
    validate_profile_helical_layer,
)

TOW = TowParameters(width=10.0, thickness=0.3)
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _layer(angle: float) -> HelicalLayer:
    return HelicalLayer(
        wind_type="helical",
        wind_angle=angle,
        pattern_number=3,
        skip_index=1,
        lock_degrees=360.0,
        lead_in_mm=20.0,
        lead_out_degrees=60.0,
    )


class _LinearProfile:
    """A cone as a profile surface (linear r, constant r') — drives the general
    integrand so it can be checked against the cone's analytic closed form."""

    def __init__(self, r0: float, r1: float, length: float) -> None:
        self.r0, self.r1, self.length = r0, r1, length

    def radius_at(self, z: float) -> float:
        return self.r0 + (self.r1 - self.r0) * z / self.length

    def radius_slope_at(self, z: float) -> float:  # noqa: ARG002 - constant slope
        return (self.r1 - self.r0) / self.length


def _trapezoid_theta_deg(surface: object, c: float, z_to: float, n: int) -> float:
    """Direct cumulative-trapezoid of the production integrand from 0 to z_to."""
    h = z_to / n
    total = 0.5 * (
        _profile_theta_integrand(surface, 0.0, c)  # type: ignore[arg-type]
        + _profile_theta_integrand(surface, z_to, c)  # type: ignore[arg-type]
    )
    for k in range(1, n):
        total += _profile_theta_integrand(surface, k * h, c)  # type: ignore[arg-type]
    return math.degrees(total * h)


# --- Differential oracle: the general integrand reproduces the cone closed form --- #


def test_integrand_matches_cone_closed_form_on_a_linear_profile() -> None:
    # The one piece of genuinely new math is the numeric Clairaut quadrature. On a
    # LINEAR profile it must reproduce the cone's analytic theta(z) (known-good code).
    r0, r1, length, angle = 49.0, 30.0, 200.0, 35.0
    lin = _LinearProfile(r0, r1, length)
    c = r0 * math.sin(math.radians(angle))
    cone_kin = compute_cone_helical_kinematics(
        _layer(angle), Cone(r0=r0, r1=r1, length=length), TOW
    )
    for z in (40.0, 100.0, 160.0):
        numeric = _trapezoid_theta_deg(lin, c, z, 4000)
        assert numeric == pytest.approx(cone_geodesic_theta_deg(z, cone_kin), abs=1e-3)


def test_integrand_matches_cone_near_the_turnaround_radius() -> None:
    # Near-cap-stressed: the integrand steepens as r -> C. Pick C only 0.3 mm below
    # the small end and integrate to it; the quadrature must still track the closed form.
    r0, r1, length = 49.0, 25.0, 200.0
    c = r1 - 0.3  # Clairaut radius just inside the small end
    angle = math.degrees(math.asin(c / r0))
    lin = _LinearProfile(r0, r1, length)
    cone_kin = compute_cone_helical_kinematics(
        _layer(angle), Cone(r0=r0, r1=r1, length=length), TOW
    )
    z_end = length - 0.5  # stay a hair off the exact small end
    numeric = _trapezoid_theta_deg(lin, c, z_end, 20000)
    assert numeric == pytest.approx(cone_geodesic_theta_deg(z_end, cone_kin), abs=5e-2)


def test_quadrature_error_shrinks_with_grid_density() -> None:
    r0, r1, length, angle = 49.0, 30.0, 200.0, 35.0
    lin = _LinearProfile(r0, r1, length)
    c = r0 * math.sin(math.radians(angle))
    cone_kin = compute_cone_helical_kinematics(
        _layer(angle), Cone(r0=r0, r1=r1, length=length), TOW
    )
    exact = cone_geodesic_theta_deg(160.0, cone_kin)
    errors = [abs(_trapezoid_theta_deg(lin, c, 160.0, n) - exact) for n in (500, 1000, 2000, 4000)]
    assert all(later < earlier for earlier, later in pairwise(errors))


# --- VK kinematics --- #


def test_kinematics_clairaut_and_anchor() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)
    assert kin.clairaut_const == pytest.approx(49.0 * math.sin(math.radians(30.0)))
    # Angle is anchored at the base (largest radius).
    assert profile_local_alpha_deg(0.0, kin) == pytest.approx(30.0, abs=1e-9)


def test_alpha_grows_toward_the_tip() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)
    alphas = [profile_local_alpha_deg(z, kin) for z in (0.0, 50.0, 100.0, kin.z_cap)]
    assert all(later >= earlier for earlier, later in pairwise(alphas))
    assert alphas[-1] < 90.0


def test_theta_is_zero_at_base_and_monotone_increasing() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)
    assert profile_geodesic_theta_deg(0.0, kin) == 0.0
    thetas = [profile_geodesic_theta_deg(z, kin) for z in range(0, int(kin.z_cap) + 1, 5)]
    assert all(later >= earlier for earlier, later in pairwise(thetas))


def test_cap_diameter_is_reported_near_twice_clairaut() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)
    # The bare cap is 2*r(z_cap); with the small guard it sits just above 2C.
    assert kin.cap_diameter == pytest.approx(2.0 * vk.radius_at(kin.z_cap), rel=1e-12)
    assert 2.0 * kin.clairaut_const < kin.cap_diameter < 2.0 * kin.clairaut_const + 3.0
    # z_cap is on the integer station lattice (stable move count across platforms).
    assert kin.z_cap == math.floor(kin.z_cap)


def test_table_interpolation_matches_direct_quadrature_off_grid() -> None:
    # Validates the cumulative-table + interpolation machinery: profile_geodesic_theta_deg
    # (0.05 mm table + linear interp) must match a direct fine quadrature of the same
    # integrand at OFF-grid points. (Integrand *correctness* is covered separately by the
    # cone-limit and Simpson oracles; this isolates the table/interpolation step.)
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)
    for z in (17.3, 88.8, 150.15, kin.z_cap - 0.37):
        direct = _trapezoid_theta_deg(vk, kin.clairaut_const, z, 8000)
        assert profile_geodesic_theta_deg(z, kin) == pytest.approx(direct, abs=2e-3)


def test_vk_theta_matches_independent_simpson_quadrature() -> None:
    # Independent oracle for the VK geodesic theta with a *varying* r' — the cone-limit
    # oracle only exercises a constant r'. Recompute the integrand from the surface's own
    # radius/slope with math.sqrt (allowed in tests) and integrate by Simpson's rule:
    # independent of both the production integrand helper and its trapezoid + table.
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)
    c = kin.clairaut_const

    def integrand(z: float) -> float:
        r = vk.radius_at(z)
        r_prime = vk.radius_slope_at(z)
        return c / (r * math.sqrt(r * r - c * c)) * math.sqrt(1.0 + r_prime * r_prime)

    z_to = kin.z_cap
    n = 6000  # even, for Simpson
    h = z_to / n
    total = integrand(0.0) + integrand(z_to)
    for k in range(1, n):
        total += (4.0 if k % 2 else 2.0) * integrand(k * h)
    simpson_theta_deg = math.degrees(total * h / 3.0)
    assert profile_geodesic_theta_deg(z_to, kin) == pytest.approx(simpson_theta_deg, abs=2e-3)


def test_theta_is_clamped_outside_the_band() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)
    assert profile_geodesic_theta_deg(-5.0, kin) == 0.0
    assert profile_geodesic_theta_deg(kin.z_cap + 10.0, kin) == pytest.approx(
        profile_geodesic_theta_deg(kin.z_cap, kin)
    )


# --- Non-geodesic (friction-assisted) integrator — Phase 2 (#327) --- #


def _lerp(grid: tuple[float, ...], values: tuple[float, ...], z: float) -> float:
    """Independent linear interpolation of a marched table (not the production helper)."""
    if z <= grid[0]:
        return values[0]
    if z >= grid[-1]:
        return values[-1]
    hi = next(i for i in range(1, len(grid)) if grid[i] >= z)
    frac = (z - grid[hi - 1]) / (grid[hi] - grid[hi - 1])
    return values[hi - 1] + frac * (values[hi] - values[hi - 1])


class _CylinderProfile:
    """Constant-radius surface stub (r' = r'' = 0): isolates the friction k_n term."""

    def __init__(self, radius: float, length: float = 60.0) -> None:
        self.radius, self.length = radius, length

    def radius_at(self, z: float) -> float:  # noqa: ARG002 - constant
        return self.radius

    def radius_slope_at(self, z: float) -> float:  # noqa: ARG002 - flat
        return 0.0

    def radius_curvature_at(self, z: float) -> float:  # noqa: ARG002 - flat
        return 0.0


def test_nongeodesic_reduces_to_the_geodesic_at_zero_friction() -> None:
    # lambda = 0 => dalpha/dz = -tan(a) r'/r and dtheta/dz = tan(a) sqrt(1+r'^2)/r, which
    # analytically preserve the Clairaut geodesic. The marched alpha(z)/theta(z) must
    # reproduce the production geodesic tables element-wise (the correctness anchor).
    vk = VonKarman(base_radius=49.0, length=300.0)
    geo = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)  # geodesic branch
    grid, alpha_deg, theta_deg = _integrate_nongeodesic(vk, 30.0, 0.0)
    # The march runs past the guarded geodesic cap (to alpha_max); compare only within
    # the geodesic band [0, z_cap].
    for z in (10.0, 50.0, 120.0, geo.z_cap - 1.0):
        assert _lerp(grid, alpha_deg, z) == pytest.approx(profile_local_alpha_deg(z, geo), abs=2e-3)
        assert _lerp(grid, theta_deg, z) == pytest.approx(
            profile_geodesic_theta_deg(z, geo), abs=1e-2
        )


def test_nongeodesic_on_a_cylinder_matches_the_closed_form() -> None:
    # Independent analytic oracle isolating the k_n term (no r'/r term on a cylinder):
    #   r' = r'' = 0  =>  dalpha/dz = -lambda*sin^2(a)/(r*cos(a)),
    # whose closed form is 1/sin(alpha(z)) = 1/sin(alpha_0) + lambda*z/r. Pins the k_n
    # coefficient AND sign, independent of the RK4 structure (a copied-k_n bug can't hide).
    r = 40.0
    cyl = _CylinderProfile(r)
    a0 = math.radians(30.0)
    for lam in (0.05, 0.1, 0.2):
        grid, alpha_deg, _ = _integrate_nongeodesic(cyl, 30.0, lam, alpha_max_deg=80.0)  # type: ignore[arg-type]
        for z in (5.0, 20.0, 50.0):
            predicted = 1.0 / math.sin(a0) + lam * z / r
            alpha = math.radians(_lerp(grid, alpha_deg, z))
            assert 1.0 / math.sin(alpha) == pytest.approx(predicted, rel=5e-4)


def test_nongeodesic_matches_an_independently_written_integrator() -> None:
    # A freshly transcribed ODE (catches a coefficient/sign typo in the production derivs)
    # solved by a DIFFERENT, independently adaptive method — midpoint RK2 whose step shrinks
    # with |dalpha/dz| so it stays accurate through the steep near-cap tail (where a fixed
    # step is under-resolved). Sampled up into that tail, not just the flat region.
    vk = VonKarman(base_radius=49.0, length=300.0)
    lam = 0.1

    def d_alpha(z: float, a: float) -> float:
        r, rp, rpp = vk.radius_at(z), vk.radius_slope_at(z), vk.radius_curvature_at(z)
        m = math.sqrt(1.0 + rp * rp)
        k_n = -rpp * math.cos(a) ** 2 / m**3 + math.sin(a) ** 2 / (r * m)
        return (-lam * k_n * m - math.sin(a) * rp / r) / math.cos(a)

    def alpha_indep_deg(z_target: float) -> float:
        a, z = math.radians(30.0), 1.0e-3
        while z < z_target:
            da = d_alpha(z, a)
            h = min(0.02, math.radians(0.05) / max(abs(da), 1e-12), z_target - z)
            a += h * d_alpha(z + h / 2, a + h / 2 * da)  # midpoint (RK2)
            z += h
        return math.degrees(a)

    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW, friction_lambda=lam)
    grid, alpha_deg = kin.grid_z, kin.alpha_table
    assert alpha_deg is not None
    # Includes the steep tail: alpha ~ 82 deg at z_cap-2, still climbing hard toward 88.
    for z in (30.0, 90.0, 180.0, 240.0, kin.z_cap - 2.0):
        assert _lerp(grid, alpha_deg, z) == pytest.approx(alpha_indep_deg(z), abs=8e-2)


def test_friction_reaches_past_the_geodesic_cap() -> None:
    # The headline: friction lets a pass climb past the geodesic turnaround toward the tip.
    vk = VonKarman(base_radius=49.0, length=300.0)
    geo = compute_profile_helical_kinematics(_layer(30.0), vk, TOW)
    fric = compute_profile_helical_kinematics(_layer(30.0), vk, TOW, friction_lambda=0.1)
    assert fric.z_cap > geo.z_cap  # winds deeper (further toward the tip)
    assert fric.cap_diameter < geo.cap_diameter  # leaves a smaller bare cap
    assert fric.alpha_table is not None  # non-geodesic carries a marched angle table
    assert geo.alpha_table is None  # geodesic uses the closed-form asin(C/r)


def test_cap_shrinks_monotonically_as_friction_rises() -> None:
    # Direction is the sign-error catch: more friction must strictly shrink the bare cap
    # (and raise the turnaround slip demand). A wrong-signed k_n would grow the cap instead.
    vk = VonKarman(base_radius=49.0, length=300.0)
    kins = [
        compute_profile_helical_kinematics(_layer(30.0), vk, TOW, friction_lambda=lam)
        for lam in (0.05, 0.1, 0.2, 0.3)
    ]
    caps = [k.cap_diameter for k in kins]
    dwells = [k.cap_dwell_slope for k in kins]
    assert all(later < earlier for earlier, later in pairwise(caps))
    assert all(later > earlier for earlier, later in pairwise(dwells))


def test_nongeodesic_z_cap_is_converged_and_step_stable() -> None:
    # The whole no-byte-goldens scheme rests on a CONVERGED, platform-stable floored z_cap.
    # A fixed-step march is NOT converged in the steep near-cap tail (z_cross came out mm-wrong
    # and step-dependent for moderate lambda); the adaptive step fixes that. Assert the floored
    # z_cap is unchanged when the per-step angle cap is halved, across an adversarial
    # lambda x base-angle grid that includes the values a fixed step got wrong (0.17/0.28/0.33).
    vk = VonKarman(base_radius=49.0, length=300.0)
    for lam in (0.1, 0.17, 0.28, 0.33, 0.4):
        for angle in (20.0, 30.0, 45.0):
            g_full, _, _ = _integrate_nongeodesic(vk, angle, lam)
            g_half, _, _ = _integrate_nongeodesic(vk, angle, lam, alpha_step_cap_deg=0.05)
            assert math.floor(g_full[-1] + 1e-6) == math.floor(g_half[-1] + 1e-6), (
                f"z_cap not step-stable at lambda={lam}, angle={angle}: "
                f"{g_full[-1]:.4f} vs {g_half[-1]:.4f}"
            )


def test_nongeodesic_alpha_is_read_from_the_table_and_grows_toward_the_tip() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = compute_profile_helical_kinematics(_layer(30.0), vk, TOW, friction_lambda=0.1)
    assert profile_local_alpha_deg(0.0, kin) == pytest.approx(30.0, abs=1e-6)  # base anchor
    alphas = [profile_local_alpha_deg(z, kin) for z in (0.0, 60.0, 150.0, kin.z_cap)]
    assert all(later >= earlier for earlier, later in pairwise(alphas))
    # z_cap floors just below the alpha_max=88 crossing (alpha rockets up in the last steep
    # sub-mm near the coordinate singularity); the marched table tops out at ~88 deg.
    assert 80.0 < alphas[-1] < 88.0
    assert kin.alpha_table[-1] == pytest.approx(88.0, abs=1e-6)


def test_nongeodesic_steep_base_angle_leaves_no_band() -> None:
    # A base angle already at/above the integrator ceiling yields no wound band.
    vk = VonKarman(base_radius=49.0, length=300.0)
    with pytest.raises(ProfileReachabilityError, match="shorter than one station"):
        compute_profile_helical_kinematics(_layer(89.0), vk, TOW, friction_lambda=0.1)


# --- Reachability / degenerate guards --- #


def test_steep_angle_leaving_no_band_is_rejected() -> None:
    # sin(89) * 49 = 48.99 mm ~ base radius: C + guard exceeds the base, no wound band.
    vk = VonKarman(base_radius=49.0, length=300.0)
    with pytest.raises(ProfileReachabilityError, match="no usable"):
        compute_profile_helical_kinematics(_layer(89.0), vk, TOW)


def test_shallow_angle_gives_a_large_band_and_small_cap() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    shallow = compute_profile_helical_kinematics(_layer(10.0), vk, TOW)
    steeper = compute_profile_helical_kinematics(_layer(45.0), vk, TOW)
    # A shallower angle -> smaller Clairaut radius -> longer band, smaller bare cap.
    assert shallow.z_cap > steeper.z_cap
    assert shallow.cap_diameter < steeper.cap_diameter


# --- Layer validator (planner-facing surface) --- #


def test_validator_returns_kinematics_on_a_valid_layer() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    kin = validate_profile_helical_layer(0, _EXAMPLE_LAYER, vk, TOW)
    assert isinstance(kin, ProfileHelicalKinematics)
    assert kin.num_circuits == 27


def test_validator_re_raises_vanishing_band_as_layer_error() -> None:
    # ProfileReachabilityError from the kinematics is surfaced as the planner-facing
    # LayerValidationError (index-prefixed), not the raw ValueError subclass.
    vk = VonKarman(base_radius=49.0, length=300.0)
    with pytest.raises(LayerValidationError, match="no usable"):
        validate_profile_helical_layer(2, _layer(89.0), vk, TOW)


def test_validator_rejects_lead_in_longer_than_the_wound_band() -> None:
    # Coverage is checked over the reachable band [0, z_cap] (~207 mm here), not the
    # full length: a lead-in that exceeds the band must be rejected.
    vk = VonKarman(base_radius=49.0, length=300.0)
    layer = HelicalLayer(
        wind_type="helical",
        wind_angle=30.0,
        pattern_number=3,
        skip_index=1,
        lock_degrees=360.0,
        lead_in_mm=250.0,
        lead_out_degrees=60.0,
    )
    with pytest.raises(LayerValidationError, match="leadInMM"):
        validate_profile_helical_layer(0, layer, vk, TOW)


def test_radius_domain_clamps_hold_at_and_beyond_the_ends() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    # Float drift can push z a hair outside [0, L]; radius_at must not raise.
    assert vk.radius_at(-1e-9) == pytest.approx(49.0, abs=1e-6)
    assert vk.radius_at(300.0 + 1e-9) == pytest.approx(0.0, abs=1e-6)


# --- Non-geodesic validation + slip limit + reporting (Phase 2, #327) --- #

_VK = VonKarman(base_radius=49.0, length=300.0)


def _cylinder_mandrel() -> MandrelParameters:
    return MandrelParameters.model_validate({"diameter": 98.0, "windLength": 300.0})


def test_friction_over_the_slip_limit_is_rejected() -> None:
    with pytest.raises(LayerValidationError, match="slip limit"):
        validate_profile_helical_layer(
            0, _layer(30.0), _VK, TOW, friction_lambda=0.3, slip_limit=0.2
        )


def test_friction_at_the_slip_limit_boundary_is_accepted() -> None:
    # Boundary lambda == mu passes and takes the non-geodesic path (marched alpha table).
    kin = validate_profile_helical_layer(
        0, _layer(30.0), _VK, TOW, friction_lambda=0.2, slip_limit=0.2
    )
    assert kin.alpha_table is not None


def test_negative_friction_is_rejected() -> None:
    with pytest.raises(LayerValidationError, match=">= 0"):
        validate_profile_helical_layer(0, _layer(30.0), _VK, TOW, friction_lambda=-0.1)


def test_slip_check_precedes_the_integration() -> None:
    # A steep angle that ALSO leaves no wound band, but with lambda > mu: the scalar slip
    # check must fire first (cheap), so the error is about slip, not reachability.
    with pytest.raises(LayerValidationError, match="slip limit"):
        validate_profile_helical_layer(
            0, _layer(89.0), _VK, TOW, friction_lambda=0.5, slip_limit=0.2
        )


def test_friction_on_a_cylinder_is_rejected() -> None:
    with pytest.raises(LayerValidationError, match="requires a Von Kármán"):
        validate_helical_layer(0, _layer(30.0), _cylinder_mandrel(), TOW, friction_lambda=0.1)


def test_friction_on_a_cone_is_rejected() -> None:
    cone = Cone(r0=49.0, r1=27.0, length=200.0)
    with pytest.raises(LayerValidationError, match="requires a Von Kármán"):
        validate_cone_helical_layer(0, _layer(30.0), cone, TOW, friction_lambda=0.1)


def test_validate_layer_rejects_friction_on_the_cylinder_surface() -> None:
    with pytest.raises(LayerValidationError, match="requires a Von Kármán"):
        validate_layer(0, _layer(30.0), _cylinder_mandrel(), TOW, friction_lambda=0.1)


def test_geodesic_layer_is_unchanged_when_zero_friction_is_threaded_explicitly() -> None:
    # The lambda=0 regression lock: threading friction_lambda=0.0 must be a no-op vs the
    # default call — same kinematics, element-wise identical move list.
    default_kin = validate_profile_helical_layer(0, _EXAMPLE_LAYER, _EXAMPLE_VK, TOW)
    zero_kin = validate_profile_helical_layer(
        0, _EXAMPLE_LAYER, _EXAMPLE_VK, TOW, friction_lambda=0.0
    )
    assert zero_kin.alpha_table is None
    assert zero_kin.z_cap == default_kin.z_cap
    spec = helical_spec(_EXAMPLE_LAYER)
    assert profile_helical_layer_moves(spec, zero_kin) == profile_helical_layer_moves(
        spec, default_kin
    )


def test_cap_comment_reports_dwell_within_slip_limit_for_the_geodesic() -> None:
    kin = validate_profile_helical_layer(0, _layer(30.0), _VK, TOW)
    lines = _profile_cap_comment(kin, friction_lambda=0.0, slip_limit=0.2)
    assert any("Bare polar cap" in ln and "geodesic" in ln for ln in lines)
    assert any("within slip limit" in ln for ln in lines)
    assert not any("#328" in ln for ln in lines)  # geodesic dwell is below mu here


def test_cap_comment_flags_phase_3_when_the_turnaround_dwell_exceeds_the_slip_limit() -> None:
    # A friction path deep enough that the turnaround dwell |r'(cap)| exceeds mu: the laying
    # reaches the cap but the reversal needs 4th-axis delivery (Phase 3, #328).
    kin = validate_profile_helical_layer(
        0, _layer(30.0), _VK, TOW, friction_lambda=0.2, slip_limit=0.2
    )
    assert kin.cap_dwell_slope > 0.2
    lines = _profile_cap_comment(kin, friction_lambda=0.2, slip_limit=0.2)
    assert any("non-geodesic turnaround" in ln and "frictionLambda=0.2" in ln for ln in lines)
    assert any("Phase 3, #328" in ln and "4th-axis" in ln for ln in lines)


# --- Developed path (build + lower) via the equivalence harness --- #

_EXAMPLE_LAYER = _layer(30.0)
_EXAMPLE_VK = VonKarman(base_radius=49.0, length=300.0)


def _example_kinematics():  # type: ignore[no-untyped-def]
    return compute_profile_helical_kinematics(_EXAMPLE_LAYER, _EXAMPLE_VK, TOW)


def test_vk_layer_lowers_to_a_valid_geodesic_program() -> None:
    kin = _example_kinematics()
    moves = profile_helical_layer_moves(helical_spec(_EXAMPLE_LAYER), kin)
    # Geometry (Clairaut re-derived from the emitted IR), coverage, and circuit count.
    assert_profile_geometry(moves, kin)
    assert_profile_coverage(_EXAMPLE_LAYER, kin, TOW)
    assert_profile_circuit_count(moves, kin.num_circuits)
    # Integer structural gate: cross-platform stable where transcendental coords are not.
    assert len(moves) == 22552


def test_geometry_check_rejects_a_perturbed_clairaut_constant() -> None:
    # A real build, judged against a kinematics whose Clairaut constant disagrees with
    # the emitted geometry, must fail — proves the check is not vacuous.
    kin = _example_kinematics()
    moves = profile_helical_layer_moves(helical_spec(_EXAMPLE_LAYER), kin)
    wrong = dataclasses.replace(kin, clairaut_const=kin.clairaut_const + 2.0)
    with pytest.raises(AssertionError, match="Clairaut"):
        assert_profile_geometry(moves, wrong)


def test_geometry_check_rejects_a_theta_table_missing_the_meridian_factor() -> None:
    # Build a theta table WITHOUT the sqrt(1+r'^2) meridian factor — a plausible integrand
    # bug — and confirm the (independent-meridian) geometry check catches the resulting
    # non-geodesic path. This proves the checker's meridian factor is truly independent.
    kin = _example_kinematics()
    c = kin.clairaut_const

    def bad_integrand(z: float) -> float:
        r = _EXAMPLE_VK.radius_at(z)
        return c / (r * math.sqrt(r * r - c * c))  # missing * sqrt(1 + r'^2)

    grid = kin.grid_z
    cum = 0.0
    bad_theta = [0.0]
    prev = bad_integrand(grid[0])
    for i in range(1, len(grid)):
        cur = bad_integrand(grid[i])
        cum += 0.5 * (prev + cur) * (grid[i] - grid[i - 1])
        prev = cur
        bad_theta.append(math.degrees(cum))
    bad_kin = dataclasses.replace(kin, cum_theta_deg=tuple(bad_theta))

    moves = profile_helical_layer_moves(helical_spec(_EXAMPLE_LAYER), bad_kin)
    with pytest.raises(AssertionError, match="Clairaut"):
        assert_profile_geometry(moves, bad_kin)


# --- End-to-end: the shipped .wind example through the real loader/planner --- #


def test_vk_nosecone_example_is_a_valid_geodesic() -> None:
    # Loads the shipped example through the .wind loader + surface_from_mandrel (the
    # user-facing path), then locks it by geodesic invariants + an integer move count.
    # Equivalence-gated, not byte-goldened (transcendental coords aren't bit-stable).
    definition = load_wind_definition(_REPO_ROOT / "examples/vk_nosecone/input.wind")
    surface = surface_from_mandrel(definition.mandrel_parameters)
    assert isinstance(surface, VonKarman)
    layer = definition.layers[0]
    assert isinstance(layer, HelicalLayer)
    kin = compute_profile_helical_kinematics(layer, surface, definition.tow_parameters)
    moves = profile_helical_layer_moves(helical_spec(layer), kin)
    assert_profile_geometry(moves, kin)
    assert_profile_coverage(layer, kin, definition.tow_parameters)
    assert_profile_circuit_count(moves, kin.num_circuits)
    assert len(moves) == 32572


def test_vk_example_plans_end_to_end_and_round_trips_through_the_reader() -> None:
    # Full pipeline: a dispatch bug that silently planned the VK mandrel as a cylinder
    # would change the geometry — caught here because the emitted program must both be a
    # non-empty XAB program AND round-trip byte-identically through read_program (the
    # golden-based round-trip suite never sees VK, which ships no expected.gcode).
    definition = load_wind_definition(_REPO_ROOT / "examples/vk_nosecone/input.wind")
    result = plan_wind(definition)
    assert result.commands, "planned an empty program"
    assert any("G21" in c for c in result.commands[:6]), "missing modal preamble"
    assert not any(("Y" in c or "Z" in c) and c.startswith("G") for c in result.commands)
    # The bare polar cap is surfaced to the operator as a program comment.
    assert any("cap" in c.lower() for c in result.commands), "bare-cap not reported in G-code"

    program = read_program(result.commands)
    assert serialize(program, MARLIN_XAB_STANDARD) == result.commands


def _profile_wind(layers: list[dict[str, object]]) -> WindDefinition:
    return WindDefinition.model_validate(
        {
            "schemaVersion": "1.2",
            "mandrelParameters": {
                "diameter": 98.0,
                "windLength": 300.0,
                "profile": {"type": "vonKarman"},
            },
            "towParameters": {"width": 7.0, "thickness": 0.5},
            "defaultFeedRate": 9000.0,
            "layers": layers,
        }
    )


def test_hoop_layer_on_a_profile_is_rejected() -> None:
    # A hoop (~90 deg) is not a geodesic, so it is rejected on a profile surface — the
    # same policy as hoop-on-cone, wired through the profile dispatch branch.
    definition = _profile_wind([{"windType": "hoop"}])
    with pytest.raises(LayerValidationError, match="hoop layers on a profile"):
        plan_wind(definition)


def test_skip_layer_on_a_profile_plans() -> None:
    # Skip is surface-independent (a mandrel reposition), so it is allowed on a profile.
    definition = _profile_wind(
        [
            {
                "windType": "helical",
                "windAngle": 30,
                "patternNumber": 3,
                "skipIndex": 1,
                "lockDegrees": 180,
                "leadInMM": 5,
                "leadOutDegrees": 15,
            },
            {"windType": "skip", "mandrelRotation": 90},
        ]
    )
    result = plan_wind(definition)
    assert result.commands
    assert len(result.layers) == 2
