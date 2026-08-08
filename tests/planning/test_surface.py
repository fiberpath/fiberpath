"""Unit tests for the mandrel surface model."""

from __future__ import annotations

import math
from itertools import pairwise

import pytest
from fiberpath.planning.surface import Cone, Cylinder, VonKarman


def test_cylinder_is_developable() -> None:
    assert Cylinder(radius=35.0).is_developable() is True


def test_cone_is_developable() -> None:
    assert Cone(r0=49.0, r1=27.0, length=80.0).is_developable() is True


def test_cylinder_radius_constant_along_z() -> None:
    surface = Cylinder(radius=35.0)
    assert surface.radius_at(0.0) == 35.0
    assert surface.radius_at(100.0) == 35.0


def test_cylinder_reproduces_legacy_diameter_reads_bit_exactly() -> None:
    # The S1 cut-over is byte-safe only if a Cylinder built from `diameter / 2`
    # reproduces the legacy `mandrel.diameter` / `math.pi * diameter` reads to
    # the bit. Verify across awkward (non-power-of-two) diameters.
    for diameter in (70.0, 98.0, 12.7, 123.456):
        surface = Cylinder(radius=diameter / 2.0)
        assert surface.diameter_at(0.0) == diameter
        assert surface.circumference_at(0.0) == math.pi * diameter


def test_cone_radius_interpolates_linearly() -> None:
    cone = Cone(r0=49.0, r1=27.0, length=80.0)
    assert cone.radius_at(0.0) == 49.0
    assert cone.radius_at(80.0) == 27.0
    assert cone.radius_at(40.0) == (49.0 + 27.0) / 2.0


def test_cone_diameter_and_circumference_track_radius() -> None:
    cone = Cone(r0=49.0, r1=27.0, length=80.0)
    z = 20.0
    assert cone.diameter_at(z) == 2.0 * cone.radius_at(z)
    assert cone.circumference_at(z) == math.pi * cone.diameter_at(z)


# --- Von Kármán (LD-Haack) profile — first non-developable surface (#326) --- #


def test_vonkarman_is_not_developable() -> None:
    assert VonKarman(base_radius=49.0, length=300.0).is_developable() is False


def test_vonkarman_radius_reference_points() -> None:
    # Independent reference values, not the same formula echoed back:
    #   base (z=0):   r = R
    #   tip  (z=L):   r = 0
    #   midpoint (z=L/2, theta_p = pi/2): V = pi/2, so r = R*sqrt((pi/2)/pi) = R/sqrt(2)
    r_base, length = 49.0, 300.0
    vk = VonKarman(base_radius=r_base, length=length)
    assert vk.radius_at(0.0) == pytest.approx(r_base, abs=1e-9)
    assert vk.radius_at(length) == pytest.approx(0.0, abs=1e-9)
    assert vk.radius_at(length / 2.0) == pytest.approx(r_base / math.sqrt(2.0), rel=1e-12)


def test_vonkarman_radius_decreases_monotonically_from_base_to_tip() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    radii = [vk.radius_at(z) for z in range(0, 301, 5)]
    assert all(later <= earlier for earlier, later in pairwise(radii))
    assert radii[0] == pytest.approx(49.0, abs=1e-9)


def test_vonkarman_slope_is_zero_at_base_and_undefined_at_tip() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    # r'(0) = 0 cleanly (the cancelled closed form; the naive chain rule is 0/0 here).
    assert vk.radius_slope_at(0.0) == pytest.approx(0.0, abs=1e-12)
    # The meridian goes vertical at the tip: the slope is undefined there.
    with pytest.raises(ValueError, match="tip"):
        vk.radius_slope_at(300.0)


def test_vonkarman_slope_matches_central_difference() -> None:
    # The analytic derivative is the only genuinely new piece unchecked by the
    # cone-limit integrator oracle (that runs on a linear profile with constant r').
    # Pin it against a high-order central difference at interior points.
    vk = VonKarman(base_radius=49.0, length=300.0)
    h = 1e-4
    for z in range(10, 291, 10):  # interior only (endpoints are singular/limiting)
        fd = (vk.radius_at(z + h) - vk.radius_at(z - h)) / (2.0 * h)
        assert vk.radius_slope_at(float(z)) == pytest.approx(fd, abs=1e-6)


def test_vonkarman_diameter_and_circumference_track_radius() -> None:
    vk = VonKarman(base_radius=49.0, length=300.0)
    z = 120.0
    assert vk.diameter_at(z) == 2.0 * vk.radius_at(z)
    assert vk.circumference_at(z) == math.pi * vk.diameter_at(z)
