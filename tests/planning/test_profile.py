"""Von Kármán (profile) geodesic — surface kinematics and the numeric Clairaut quadrature.

Stage 3b Phase 1 (#326). These drive the profile kinematics directly (no schema, no
dispatch yet) and validate the one genuinely new piece — the numeric geodesic
theta(z) — against the known-good cone closed form and against direct quadrature.
"""

from __future__ import annotations

import math
from itertools import pairwise

import pytest
from fiberpath.config.schemas import HelicalLayer, TowParameters
from fiberpath.planning.calculations import (
    ProfileReachabilityError,
    _profile_theta_integrand,
    compute_cone_helical_kinematics,
    compute_profile_helical_kinematics,
    cone_geodesic_theta_deg,
    profile_geodesic_theta_deg,
    profile_local_alpha_deg,
)
from fiberpath.planning.surface import Cone, VonKarman

TOW = TowParameters(width=10.0, thickness=0.3)


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


def test_radius_domain_clamps_hold_at_and_beyond_the_ends() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    # Float drift can push z a hair outside [0, L]; radius_at must not raise.
    assert vk.radius_at(-1e-9) == pytest.approx(49.0, abs=1e-6)
    assert vk.radius_at(300.0 + 1e-9) == pytest.approx(0.0, abs=1e-6)
