"""Mandrel surface model — typed analytic profile segments.

A constant-angle winding path is closed-form on any *developable* surface: the
surface unrolls to a flat plane (cylinder) or sector (cone) with no distortion,
so no ODE/friction solver is needed. ``is_developable()`` is O(1) by type.

Stage 3a (#138) introduced this model for the developable surfaces (cylinder,
cone). Stage 3b (#326) adds the first *non-developable* surface, the Von Kármán
nose ``VonKarman`` (``is_developable() -> False``): its geodesic winding path has
no closed form and is integrated numerically (see ``calculations`` — the profile
Clairaut quadrature).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fiberpath.config.schemas import MandrelParameters


@dataclass(frozen=True, slots=True)
class Cylinder:
    """Constant-radius surface (the only surface planned before Stage 3a)."""

    radius: float

    def is_developable(self) -> bool:
        return True

    def radius_at(self, z: float) -> float:  # noqa: ARG002 - constant by definition
        return self.radius

    def diameter_at(self, z: float) -> float:
        # 2 * (d / 2) is bit-exact for all normal floats (both steps are pure
        # exponent shifts), so a Cylinder built from `diameter / 2` reproduces
        # the legacy `mandrel.diameter` reads exactly — this is what keeps the
        # S1 cut-over byte-identical.
        return 2.0 * self.radius_at(z)

    def circumference_at(self, z: float) -> float:
        return math.pi * self.diameter_at(z)


@dataclass(frozen=True, slots=True)
class Cone:
    """Frustum: radius varies linearly from ``r0`` (z=0) to ``r1`` (z=length).

    Defined in S1 but not yet planned; the z-dependent winding kinematics
    (varying circumference, pitch, dwell) land in S2.
    """

    r0: float
    r1: float
    length: float

    def is_developable(self) -> bool:
        return True

    def radius_at(self, z: float) -> float:
        # minimal: no length>0 / positivity guard — nothing constructs a Cone
        # from input yet. S2 validates these at the .wind schema boundary when
        # cones become plannable (length==0 would raise ZeroDivisionError here).
        return self.r0 + (self.r1 - self.r0) * (z / self.length)

    def diameter_at(self, z: float) -> float:
        return 2.0 * self.radius_at(z)

    def circumference_at(self, z: float) -> float:
        return math.pi * self.diameter_at(z)


@dataclass(frozen=True, slots=True)
class VonKarman:
    """Von Kármán (LD-Haack) nose profile — a non-developable surface of revolution.

    The radius runs from ``base_radius`` at the base (z=0) to 0 at the tip
    (z=``length``). Non-developable (nonzero Gaussian curvature: it does not unroll
    flat), so a constant-angle path is *not* a straight line — the winding path is a
    geodesic obeying the Clairaut relation, integrated numerically in
    ``calculations``. First surface with ``is_developable() -> False`` (Stage 3b, #326).

    Engine axial coordinate ``z`` measures from the base; distance from the tip is
    ``length - z``, so with ``theta_p = arccos(2z/length - 1)`` the LD-Haack meridian is
    ``r(z) = (base_radius / sqrt(pi)) * sqrt(theta_p - sin(2*theta_p)/2)``.
    """

    base_radius: float
    length: float

    def is_developable(self) -> bool:
        return False

    def _theta_p(self, z: float) -> float:
        # minimal: no length>0 / base_radius>0 guard — nothing constructs a VonKarman
        # from input in this slice. PR3 validates positivity at the .wind schema
        # boundary; unlike the developable surfaces this profile also feeds a numeric
        # integrator, so length==0 here would raise ZeroDivisionError.
        # theta_p(z) = arccos(2z/length - 1). Clamp the argument to [-1, 1]: float
        # drift in z (accumulated stations, windLength round-trips) can push it a
        # hair outside and math.acos would raise ValueError.
        u = 2.0 * z / self.length - 1.0
        return math.acos(max(-1.0, min(1.0, u)))

    def _shape_v(self, theta_p: float) -> float:
        # V = theta_p - sin(2*theta_p)/2, the squared normalised radius. max(0, .)
        # guards the ** 0.5 below: in Python a tiny-negative base to a fractional
        # power returns a *silent complex* (no exception), which would poison the
        # planner. (The math.sqrt call is reserved to metrics.py by the Motion IR
        # single-source guard, so radii use ** 0.5 and slopes use math.hypot.)
        return max(0.0, theta_p - math.sin(2.0 * theta_p) / 2.0)

    def radius_at(self, z: float) -> float:
        v = self._shape_v(self._theta_p(z))
        # float() wraps the ** results (typeshed types float ** float as Any).
        return float(self.base_radius * math.pi**-0.5 * v**0.5)

    def radius_slope_at(self, z: float) -> float:
        """``dr/dz`` (analytic, cancelled closed form).

        ``r'(z) = -(2*base_radius / (sqrt(pi)*length)) * sin(theta_p) / sqrt(V)``. The
        ``sin(theta_p)`` numerator cancels the ``1/sin(theta_p)`` from ``d(theta_p)/dz``,
        so ``r'(0) = 0`` cleanly (the naive chain rule is 0/0 at the base). It diverges
        at the tip (``z = length``, ``V = 0``), which the geodesic never reaches.
        """
        theta_p = self._theta_p(z)
        v = self._shape_v(theta_p)
        if v == 0.0:
            raise ValueError("radius_slope_at is undefined at the tip (r=0, vertical tangent)")
        return float(
            -(2.0 * self.base_radius * math.pi**-0.5 / self.length) * math.sin(theta_p) / v**0.5
        )

    def radius_curvature_at(self, z: float) -> float:
        """``d²r/dz²`` (analytic, cancelled closed form) — needed by the non-geodesic solver.

        Differentiating ``r'(z) = -(2R/(sqrt(pi)L))·sin(theta_p)/sqrt(V)`` gives

            r''(z) = (4R / (sqrt(pi)·L²)) · [ cos(theta_p)/(sin(theta_p)·sqrt(V))
                                              − sin²(theta_p)/V^{3/2} ] .

        Unlike ``r'`` (which is 0 at the base and only singular at the tip), ``r''`` is
        **singular at BOTH ends**: near the base the LD-Haack meridian is
        ``r ≈ R − a·z^{3/2}`` so ``r'' ∝ −z^{-1/2} → −∞`` at z=0, and it diverges again at
        the tip (V→0). The singularities are integrable, but the closed form must not be
        evaluated there — the non-geodesic integrator starts one grid step in from the
        base and stops well below the tip. Raises on the open-interval boundary.
        """
        if not 0.0 < z < self.length:
            raise ValueError(
                "radius_curvature_at is undefined at the base (z=0) and tip (z=length): "
                f"r'' diverges at both ends; got z={z}"
            )
        theta_p = self._theta_p(z)
        v = self._shape_v(theta_p)
        sin_tp = math.sin(theta_p)
        coeff = 4.0 * self.base_radius * math.pi**-0.5 / (self.length * self.length)
        # ** 0.5 / ** 1.5 (not math.sqrt — reserved to metrics.py by the Motion IR guard).
        return float(coeff * (math.cos(theta_p) / (sin_tp * v**0.5) - sin_tp * sin_tp / v**1.5))

    def diameter_at(self, z: float) -> float:
        return 2.0 * self.radius_at(z)

    def circumference_at(self, z: float) -> float:
        return math.pi * self.diameter_at(z)


Surface = Cylinder | Cone | VonKarman


def surface_from_mandrel(mandrel: MandrelParameters) -> Surface:
    """Map the .wind mandrel parameters onto the analytic surface model.

    A reducing ``endDiameter`` (set and below ``diameter``) yields a ``Cone``
    (large end ``diameter`` at z=0, small end ``endDiameter`` at z=windLength);
    an absent or equal ``endDiameter`` is a ``Cylinder``. A *larger* ``endDiameter``
    falls through to the cone branch so the layer validators reject it (expanding
    frusta are not supported yet) with a clear message.
    """
    if mandrel.profile is not None and mandrel.profile.type == "vonKarman":
        return VonKarman(base_radius=mandrel.diameter / 2.0, length=mandrel.wind_length)
    if mandrel.end_diameter is not None and mandrel.end_diameter != mandrel.diameter:
        return Cone(
            r0=mandrel.diameter / 2.0,
            r1=mandrel.end_diameter / 2.0,
            length=mandrel.wind_length,
        )
    return Cylinder(radius=mandrel.diameter / 2.0)
