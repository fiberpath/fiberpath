"""Validation helpers for planner inputs."""

from __future__ import annotations

from math import asin, degrees, gcd, radians, sin

from fiberpath.config.schemas import (
    HelicalLayer,
    LayerModel,
    MandrelParameters,
    TowParameters,
)

from .calculations import (
    ConeHelicalKinematics,
    HelicalKinematics,
    compute_cone_helical_kinematics,
    compute_helical_kinematics,
)
from .exceptions import LayerValidationError
from .pattern import PatternSpec, pattern_spec
from .surface import Cone

MIN_WIND_ANGLE = 1.0
MAX_WIND_ANGLE = 89.0


def _nearest_valid_lock_degrees(
    lock_degrees: float, pattern_step_deg: float, skip_index: int
) -> str:
    """Return up to three nearby lockDegrees values that satisfy both coverage conditions."""
    half_step = pattern_step_deg / 2.0
    P = round(360.0 / pattern_step_deg)
    centre = round(lock_degrees / half_step)
    candidates: list[float] = []
    for delta in range(-16, 17):
        v = (centre + delta) * half_step
        if v <= 0:
            continue
        pcm = (2.0 * v) % 360.0
        if round(pcm % pattern_step_deg, 6) != 0:
            continue
        ss = (pcm + skip_index * pattern_step_deg) % 360.0
        j = round(ss / pattern_step_deg) % P
        if gcd(j, P) == 1:
            candidates.append(v)
        if len(candidates) >= 3:
            break
    return ", ".join(f"{v:.6g}°" for v in candidates) or "multiples of 180°"


def validate_layer_sequence(layer_index: int, encountered_terminal: bool) -> None:
    if encountered_terminal:
        raise LayerValidationError(
            layer_index,
            "terminal layer must be the final entry in the definition",
        )


def validate_layer_numeric_bounds(layer_index: int, layer: LayerModel) -> None:
    wind_angle = getattr(layer, "wind_angle", None)
    if wind_angle is not None and not (MIN_WIND_ANGLE <= wind_angle <= MAX_WIND_ANGLE):
        raise LayerValidationError(
            layer_index,
            f"wind angle {wind_angle}° must be between {MIN_WIND_ANGLE}° and {MAX_WIND_ANGLE}°",
        )


def validate_layer(
    layer_index: int,
    layer: LayerModel,
    mandrel: MandrelParameters,
    tow: TowParameters,
) -> HelicalKinematics | None:
    """Validate any layer over its declarative pattern primitive.

    The single validation surface for every pattern type: numeric bounds apply
    to layers with a free wind angle, and the coverage checks apply to laying
    layers that carry a coverage pattern (helical). Hoop and skip have no
    coverage pattern, so they pass through with nothing to constrain. Returns the
    helical kinematics when applicable (for the planner to reuse), else ``None``.
    """
    validate_layer_numeric_bounds(layer_index, layer)
    if isinstance(layer, HelicalLayer):
        return validate_helical_layer(layer_index, layer, mandrel, tow)
    return None


def _validate_coverage(
    layer_index: int,
    spec: PatternSpec,
    num_circuits: int,
    wind_length: float,
) -> None:
    """Coverage checks shared by cylinder and cone helical layers.

    These are pattern-stepping conditions in mandrel degrees (skip/pattern
    coprimality, lead-in bound, circuit divisibility, the lockDegrees slot math)
    and are surface-independent: a cone steps its circuit starts at the large-end
    datum with the same arithmetic, so the same conditions guarantee coverage.
    """
    if spec.skip_index >= spec.pattern_number:
        raise LayerValidationError(
            layer_index,
            "skipIndex must be less than patternNumber",
        )

    if gcd(spec.skip_index, spec.pattern_number) != 1:
        raise LayerValidationError(
            layer_index,
            "skipIndex and patternNumber must be coprime for full coverage",
        )

    if spec.lead_in_mm >= wind_length:
        raise LayerValidationError(
            layer_index,
            (
                f"leadInMM ({spec.lead_in_mm}mm) must be less than the mandrel "
                f"windLength ({wind_length}mm); a longer lead-in drives the "
                "carriage off the mandrel into negative coordinates"
            ),
        )

    if num_circuits % spec.pattern_number != 0:
        raise LayerValidationError(
            layer_index,
            (
                "computed circuit count is not divisible by patternNumber "
                f"({num_circuits} % {spec.pattern_number} != 0)"
            ),
        )

    # Validate that lockDegrees is compatible with patternNumber and skipIndex.
    #
    # The net mandrel advance per complete circuit (out + return pass) mod 360° equals
    # (2 × lockDegrees) % 360°, independent of wind angle, mandrel geometry, or lead
    # parameters.  For the patternNumber in-pattern circuits to land at evenly distributed,
    # non-overlapping angular positions two conditions must hold:
    #
    #   Condition 1 — divisibility:
    #     per_circuit_mod must be divisible by 360/patternNumber (one slot width).
    #     Equivalently: lockDegrees must be a multiple of 180/patternNumber.
    #
    #   Condition 2 — non-aliasing:
    #     The intra-pattern slot stride (in units of 360/patternNumber) must be coprime
    #     with patternNumber, otherwise all in-pattern circuits alias onto fewer positions.
    #
    # When patternNumber == 1, start_position_increment = 360° ≡ 0°, so every circuit
    # begins at the same mandrel position.  Coverage is guaranteed entirely by the tow
    # width × circuit count calculation and lockDegrees is not constrained here.
    if spec.pattern_number > 1:
        pattern_step_deg = 360.0 / spec.pattern_number
        per_circuit_mod = (2.0 * spec.lock_degrees) % 360.0

        if round(per_circuit_mod % pattern_step_deg, 6) != 0:
            suggestions = _nearest_valid_lock_degrees(
                spec.lock_degrees, pattern_step_deg, spec.skip_index
            )
            raise LayerValidationError(
                layer_index,
                (
                    f"lockDegrees {spec.lock_degrees}° produces a per-circuit mandrel advance of "
                    f"{per_circuit_mod:.6g}° (mod 360°), which is not divisible by the in-pattern "
                    f"slot width of {pattern_step_deg:.6g}°"
                    f" (= 360 / patternNumber {spec.pattern_number}). "
                    f"Circuits will overlap and leave bare mandrel strips. "
                    f"lockDegrees must be a multiple of {pattern_step_deg / 2:.6g}°. "
                    f"Nearest valid values: {suggestions}"
                ),
            )

        slot_step = (per_circuit_mod + spec.skip_index * pattern_step_deg) % 360.0
        j = round(slot_step / pattern_step_deg) % spec.pattern_number
        if gcd(j, spec.pattern_number) != 1:
            suggestions = _nearest_valid_lock_degrees(
                spec.lock_degrees, pattern_step_deg, spec.skip_index
            )
            raise LayerValidationError(
                layer_index,
                (
                    f"lockDegrees {spec.lock_degrees}° with skipIndex {spec.skip_index} and "
                    f"patternNumber {spec.pattern_number} produces an"
                    f" intra-pattern slot stride of "
                    f"{j} (in units of {pattern_step_deg:.6g}°), which is not coprime with "
                    f"patternNumber (gcd = {gcd(j, spec.pattern_number)}). "
                    f"All in-pattern circuits will alias onto fewer positions,"
                    f" leaving bare strips. "
                    f"Nearest valid lockDegrees values: {suggestions}"
                ),
            )


def validate_helical_layer(
    layer_index: int,
    layer: HelicalLayer,
    mandrel: MandrelParameters,
    tow: TowParameters,
) -> HelicalKinematics:
    # Read the coverage pattern from the declarative primitive (PatternSpec), so
    # this is a type-checker over the primitive rather than the raw schema. This
    # is equivalent to the raw layer only while helical_spec is a verbatim
    # projection of the coverage fields (it is); the kinematics below are still
    # derived from the layer, which is the single motion-math source.
    spec = pattern_spec(layer)
    kinematics = compute_helical_kinematics(layer, mandrel, tow)
    _validate_coverage(layer_index, spec, kinematics.num_circuits, mandrel.wind_length)
    return kinematics


def validate_cone_helical_layer(
    layer_index: int,
    layer: HelicalLayer,
    surface: Cone,
    tow: TowParameters,
) -> ConeHelicalKinematics:
    """Validate a helical layer wound on a cone, as a type-check over the primitive.

    Cone-specific guards (orientation, geodesic reachability) raised as
    ``LayerValidationError`` for a consistent planner-facing error, then the
    shared coverage conditions over the large-end circuit count. Not yet wired
    into the planner (S3b) -- cones reach this only via direct construction.
    """
    validate_layer_numeric_bounds(layer_index, layer)

    if surface.r1 >= surface.r0:
        raise LayerValidationError(
            layer_index,
            (
                f"cone requires a reducing frustum with r0 > r1 (got r0={surface.r0}, "
                f"r1={surface.r1}); the wind angle anchors at the large end r0, so mount "
                "the large end at z=0"
            ),
        )

    clairaut_const = surface.r0 * sin(radians(layer.wind_angle))
    if clairaut_const > surface.r1:
        max_angle = degrees(asin(surface.r1 / surface.r0))
        raise LayerValidationError(
            layer_index,
            (
                f"wind angle {layer.wind_angle}° is too steep for the cone: the geodesic "
                f"(Clairaut C={clairaut_const:.4g}mm) cannot reach the small-end radius "
                f"{surface.r1:.4g}mm. Reduce the wind angle to <= {max_angle:.4g}°"
            ),
        )

    spec = pattern_spec(layer)
    kinematics = compute_cone_helical_kinematics(layer, surface, tow)
    _validate_coverage(layer_index, spec, kinematics.num_circuits, surface.length)
    return kinematics
