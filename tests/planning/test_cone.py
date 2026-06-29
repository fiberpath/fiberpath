"""Cone (geodesic) helical winding — kinematics, development, and equivalence.

S2 (#307). Cones are not yet wired into the planner/.wind (S3); these drive the
cone builder directly and assert geodesic correctness via analytic invariants.
"""

from __future__ import annotations

import math

import pytest
from _equivalence import (
    assert_cone_coverage,
    assert_cone_geometry,
    cone_helical_layer_moves,
)
from fiberpath.config.schemas import HelicalLayer, MandrelParameters, TowParameters
from fiberpath.planning.calculations import (
    ConeReachabilityError,
    compute_cone_helical_kinematics,
    compute_helical_kinematics,
    cone_geodesic_theta_deg,
    cone_local_alpha_deg,
)
from fiberpath.planning.pattern import helical_spec
from fiberpath.planning.surface import Cone

# HPR reducer-style frustum: 98 -> 54 mm diameter over 120 mm (~10.4 deg half-angle).
CONE = Cone(r0=49.0, r1=27.0, length=120.0)
MANDREL = MandrelParameters.model_validate({"diameter": 98.0, "windLength": 120.0})
TOW = TowParameters.model_validate({"width": 6.0, "thickness": 0.5})
# windAngle=30 gives num_circuits=45 at the large end, divisible by patternNumber=3
# (the builder shares the cylinder's coverage precondition: the validators enforce
# num_circuits % patternNumber == 0; cones get that wired in S3).
LAYER = HelicalLayer.model_validate(
    {
        "windAngle": 30.0,
        "patternNumber": 3,
        "skipIndex": 1,
        "lockDegrees": 180.0,
        "leadInMM": 5.0,
        "leadOutDegrees": 15.0,
    }
)


def _kin(layer: HelicalLayer = LAYER, cone: Cone = CONE):
    return compute_cone_helical_kinematics(layer, cone, TOW)


def test_coverage_divisible_by_pattern_number() -> None:
    # The builder's precondition (mirrors the cylinder): the chosen pattern tiles.
    assert _kin().num_circuits % LAYER.pattern_number == 0


def test_angle_is_anchored_at_large_end() -> None:
    kin = _kin()
    # windAngle is the angle at r0 (z=0); it grows toward the small radius.
    assert cone_local_alpha_deg(0.0, kin) == pytest.approx(30.0, abs=1e-9)
    assert cone_local_alpha_deg(CONE.length, kin) > 30.0


def test_clairaut_constant_holds_along_the_geodesic() -> None:
    kin = _kin()
    c = kin.clairaut_const
    for z in (0.0, 30.0, 60.0, 90.0, 120.0):
        r = CONE.radius_at(z)
        alpha = math.radians(cone_local_alpha_deg(z, kin))
        assert r * math.sin(alpha) == pytest.approx(c, abs=1e-9)


def test_theta_is_monotonic_in_z() -> None:
    kin = _kin()
    thetas = [cone_geodesic_theta_deg(z, kin) for z in range(0, 121)]
    assert all(b >= a for a, b in zip(thetas, thetas[1:], strict=False))
    assert thetas[0] == 0.0


def test_unreachable_angle_is_rejected() -> None:
    # asin(r1/r0) = asin(27/49) ~= 33.4 deg is the steepest reachable angle.
    steep = HelicalLayer.model_validate({**LAYER.model_dump(by_alias=True), "windAngle": 40.0})
    with pytest.raises(ConeReachabilityError):
        compute_cone_helical_kinematics(steep, CONE, TOW)


def test_zero_taper_cone_is_rejected_use_cylinder() -> None:
    with pytest.raises(ValueError, match="zero-taper"):
        compute_cone_helical_kinematics(LAYER, Cone(r0=40.0, r1=40.0, length=120.0), TOW)


def test_expanding_cone_is_rejected() -> None:
    # The model anchors at the large end; an expanding frustum (r1 > r0) is not
    # supported yet and must be rejected rather than silently mis-anchored.
    with pytest.raises(ValueError, match="expanding"):
        compute_cone_helical_kinematics(LAYER, Cone(r0=27.0, r1=49.0, length=120.0), TOW)


def test_lowered_path_is_a_geodesic_clairaut_invariant() -> None:
    kin = _kin()
    moves = cone_helical_layer_moves(helical_spec(LAYER), kin, MANDREL)
    assert_cone_geometry(moves, kin)


def test_cone_coverage_tiles_large_end() -> None:
    assert_cone_coverage(_kin(), TOW)


def test_near_degenerate_cone_approaches_cylinder_rotation() -> None:
    # As r1 -> r0 the geodesic's full-pass rotation must approach the cylinder's
    # pass_rotation_degrees (the cylinder limit is handled correctly).
    near = Cone(r0=49.0, r1=48.9, length=120.0)
    kin = compute_cone_helical_kinematics(LAYER, near, TOW)
    cone_full = cone_geodesic_theta_deg(near.length, kin)
    cyl = compute_helical_kinematics(
        LAYER, MandrelParameters.model_validate({"diameter": 98.0, "windLength": 120.0}), TOW
    )
    assert cone_full == pytest.approx(cyl.pass_rotation_degrees, rel=2e-2)
