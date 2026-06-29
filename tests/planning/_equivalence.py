"""Equivalence-harness helpers for the developed-surface lowering (S2 #296).

These checks assert the lowered Motion IR is a *correct* winding path — coverage,
on-surface fiber angle, delivery-head lean — independent of the exact bytes, plus
an old-vs-new metric-parity comparator. Together they are the regression gate that
takes over from byte-equality as later slices (clean structural collapse, cones)
intentionally change the emitted bytes.

Not a shipped module (lives under ``tests/``); imported by ``test_pattern_equivalence``.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from fiberpath.config.schemas import HelicalLayer, HoopLayer, MandrelParameters, TowParameters
from fiberpath.planning.calculations import ConeHelicalKinematics, compute_helical_kinematics
from fiberpath.planning.developed import build_cone_helical_developed_path, lower_developed_path
from fiberpath.planning.helpers import Axis
from fiberpath.planning.ir import Move, MoveKind
from fiberpath.planning.layer_strategies import dispatch_layer
from fiberpath.planning.machine import WinderMachine
from fiberpath.planning.metrics import nominal_metrics
from fiberpath.planning.pattern import PatternSpec


def helical_layer_moves(
    layer: HelicalLayer,
    mandrel: MandrelParameters,
    tow: TowParameters,
    feed: float = 9000.0,
) -> list[Move]:
    """Plan a single helical layer in isolation and return its Motion IR moves."""
    machine = WinderMachine(mandrel.diameter)
    machine.set_feed_rate(feed)
    dispatch_layer(machine, layer, mandrel, tow)
    return machine.get_moves()


def hoop_layer_moves(
    layer: HoopLayer,
    mandrel: MandrelParameters,
    tow: TowParameters,
    feed: float = 9000.0,
) -> list[Move]:
    """Plan a single hoop layer in isolation and return its Motion IR moves."""
    machine = WinderMachine(mandrel.diameter)
    machine.set_feed_rate(feed)
    dispatch_layer(machine, layer, mandrel, tow)
    return machine.get_moves()


def _surface_segments(moves: Iterable[Move], mandrel_diameter: float) -> list[tuple[float, float]]:
    """(dz_mm, d_arc_mm) for each carriage-moving RAPID step, honoring G92 resets."""
    circumference = math.pi * mandrel_diameter
    last = {Axis.CARRIAGE: 0.0, Axis.MANDREL: 0.0, Axis.DELIVERY_HEAD: 0.0}
    segments: list[tuple[float, float]] = []
    for move in moves:
        if move.kind is MoveKind.SET_POSITION:
            for axis, value in move.targets.items():
                last[axis] = value
            continue
        if move.kind in (MoveKind.SET_FEED, MoveKind.COMMENT):
            continue
        d_z = move.targets.get(Axis.CARRIAGE, last[Axis.CARRIAGE]) - last[Axis.CARRIAGE]
        d_theta = move.targets.get(Axis.MANDREL, last[Axis.MANDREL]) - last[Axis.MANDREL]
        for axis, value in move.targets.items():
            last[axis] = value
        if abs(d_z) > 1e-9:
            segments.append((d_z, d_theta / 360.0 * circumference))
    return segments


def assert_geometry(
    moves: Iterable[Move], alpha_deg: float, mandrel_diameter: float, tol: float = 1e-6
) -> None:
    """Every carriage-moving (laying) segment sits at the fiber angle ``alpha_deg``."""
    segments = _surface_segments(moves, mandrel_diameter)
    if not segments:
        raise AssertionError("no laying (carriage-moving) segments found")
    for d_z, arc_mm in segments:
        angle = math.degrees(math.atan2(abs(arc_mm), abs(d_z)))
        if abs(angle - alpha_deg) > tol:
            raise AssertionError(
                f"laying segment at {angle:.9f} deg != alpha {alpha_deg} (dz={d_z}, arc={arc_mm})"
            )


def assert_hoop_geometry(
    moves: Iterable[Move], mandrel_diameter: float, tow_width: float, tol: float = 1e-6
) -> None:
    """A hoop lays at the densest-wrap angle ``atan(circumference / tow_width)``.

    This is the geometric wind angle of a hoop (close to, but not, 90 deg) -- set
    by the tow width, not by the delivery-head lean -- so it is checked separately
    from the helical ``alpha`` case.
    """
    circumference = math.pi * mandrel_diameter
    expected = math.degrees(math.atan(circumference / tow_width))
    segments = _surface_segments(moves, mandrel_diameter)
    if not segments:
        raise AssertionError("no laying (carriage-moving) segments found")
    for d_z, arc_mm in segments:
        angle = math.degrees(math.atan2(abs(arc_mm), abs(d_z)))
        if abs(angle - expected) > tol:
            raise AssertionError(
                f"hoop segment at {angle:.9f} deg != densest-wrap {expected:.9f} deg"
            )


def assert_lean(moves: Iterable[Move], alpha_deg: float, tol: float = 1e-6) -> None:
    """The peak delivery-head lean equals the laying lean ``90 - alpha`` (and never exceeds it)."""
    leans = [
        value
        for move in moves
        if move.kind is MoveKind.RAPID
        for axis, value in move.targets.items()
        if axis is Axis.DELIVERY_HEAD
    ]
    expected = abs(90.0 - alpha_deg)
    peak = max((abs(v) for v in leans), default=0.0)
    if abs(peak - expected) > tol:
        raise AssertionError(f"peak |lean| {peak} != laying lean {expected}")


def assert_coverage(layer: HelicalLayer, mandrel: MandrelParameters, tow: TowParameters) -> None:
    """Coverage tiles the circumference without gaps or aliasing."""
    if math.gcd(layer.skip_index, layer.pattern_number) != 1:
        raise AssertionError(
            f"skip_index {layer.skip_index} / pattern_number {layer.pattern_number} not coprime"
            " — circuits alias, leaving coverage gaps"
        )
    kinematics = compute_helical_kinematics(layer, mandrel, tow)
    circumference = math.pi * mandrel.diameter
    expected = math.ceil(circumference / kinematics.tow_arc_length)
    if kinematics.num_circuits != expected:
        raise AssertionError(f"num_circuits {kinematics.num_circuits} != ceil {expected}")
    if kinematics.num_circuits * kinematics.tow_arc_length + 1e-9 < circumference:
        raise AssertionError("coverage gap: circuits * tow_arc_length < circumference")


def cone_helical_layer_moves(
    spec: PatternSpec,
    kinematics: ConeHelicalKinematics,
    mandrel: MandrelParameters,
    feed: float = 9000.0,
) -> list[Move]:
    """Build + lower a single cone helical layer in isolation; return its IR moves.

    Cones are not yet wired into ``dispatch_layer`` (S3), so this drives the cone
    builder directly. The machine diameter is nominal (large end) -- it does not
    affect the emitted carriage/mandrel/delivery moves.
    """
    machine = WinderMachine(2.0 * kinematics.r0)
    machine.set_feed_rate(feed)
    lower_developed_path(machine, build_cone_helical_developed_path(spec, kinematics, mandrel))
    return machine.get_moves()


def _cone_laying_segments(moves: Iterable[Move]) -> list[tuple[float, float, float]]:
    """(z_mid, dz, d_theta_deg) for each carriage-moving step, honoring G92 resets."""
    last = {Axis.CARRIAGE: 0.0, Axis.MANDREL: 0.0, Axis.DELIVERY_HEAD: 0.0}
    segments: list[tuple[float, float, float]] = []
    for move in moves:
        if move.kind is MoveKind.SET_POSITION:
            for axis, value in move.targets.items():
                last[axis] = value
            continue
        if move.kind in (MoveKind.SET_FEED, MoveKind.COMMENT):
            continue
        z_old = last[Axis.CARRIAGE]
        z_new = move.targets.get(Axis.CARRIAGE, z_old)
        d_theta = move.targets.get(Axis.MANDREL, last[Axis.MANDREL]) - last[Axis.MANDREL]
        for axis, value in move.targets.items():
            last[axis] = value
        d_z = z_new - z_old
        if abs(d_z) > 1e-9:
            segments.append(((z_old + z_new) / 2.0, d_z, d_theta))
    return segments


def assert_cone_geometry(
    moves: Iterable[Move],
    kinematics: ConeHelicalKinematics,
    *,
    clairaut_tol: float = 5e-3,
    anchor_tol: float = 1.5e-1,
) -> None:
    """Every laying segment is a geodesic: Clairaut ``r·sin(alpha) = C`` holds.

    The achieved fiber angle varies along a cone, so "achieves the target angle"
    is checked as the Clairaut invariant (constant ``C``) rather than a single
    angle, plus the angle at the large-end anchor matching the reference angle.
    Tolerances absorb the machine's linear interpolation between ~1 mm samples.
    """
    r0, r1, length = kinematics.r0, kinematics.r1, kinematics.length
    cos_phi = math.cos(kinematics.half_angle_rad)
    segments = _cone_laying_segments(moves)
    if not segments:
        raise AssertionError("no laying (carriage-moving) segments found")
    anchor = min(segments, key=lambda s: s[0])  # nearest the large end (z=0)
    for z_mid, d_z, d_theta in segments:
        r = r0 + (r1 - r0) * (z_mid / length)
        alpha = math.atan(r * math.radians(d_theta) * cos_phi / abs(d_z))
        clairaut = r * math.sin(alpha)
        if abs(clairaut - kinematics.clairaut_const) > clairaut_tol:
            raise AssertionError(
                f"Clairaut drift at z={z_mid:.3f}: r·sin(alpha)={clairaut:.6f} "
                f"!= C={kinematics.clairaut_const:.6f}"
            )
    z_mid, d_z, d_theta = anchor
    r = r0 + (r1 - r0) * (z_mid / length)
    anchor_alpha = math.degrees(math.atan(r * math.radians(d_theta) * cos_phi / abs(d_z)))
    if abs(anchor_alpha - kinematics.alpha_ref_deg) > anchor_tol:
        raise AssertionError(
            f"large-end angle {anchor_alpha:.4f} deg != reference {kinematics.alpha_ref_deg} deg"
        )


def assert_cone_coverage(kinematics: ConeHelicalKinematics, tow: TowParameters) -> None:
    """Coverage anchored at the large end tiles the largest parallel without gaps."""
    tow_arc_length = tow.width / math.cos(math.radians(kinematics.alpha_ref_deg))
    circumference0 = 2.0 * math.pi * kinematics.r0
    if kinematics.num_circuits * tow_arc_length + 1e-9 < circumference0:
        raise AssertionError("coverage gap at the large end: circuits * tow_arc < circumference")


def assert_metrics_equal(
    moves_a: Sequence[Move],
    moves_b: Sequence[Move],
    mandrel_diameter: float,
    *,
    time_tol: float = 1e-6,
    dist_tol: float = 1e-6,
) -> None:
    """Two programs share nominal time, surface distance, and surface-move count."""
    a = nominal_metrics(moves_a, mandrel_diameter)
    b = nominal_metrics(moves_b, mandrel_diameter)
    if a.move_count != b.move_count:
        raise AssertionError(f"move_count {a.move_count} != {b.move_count}")
    if abs(a.distance_mm - b.distance_mm) > dist_tol:
        raise AssertionError(f"distance drift: {a.distance_mm} != {b.distance_mm}")
    if abs(a.time_s - b.time_s) > time_tol:
        raise AssertionError(f"time drift: {a.time_s} != {b.time_s}")
