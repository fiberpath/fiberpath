"""Unit tests for the mandrel surface model."""

from __future__ import annotations

import math

from fiberpath.planning.surface import Cone, Cylinder


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
