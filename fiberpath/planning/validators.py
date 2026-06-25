"""Validation helpers for planner inputs."""

from __future__ import annotations

from math import gcd

from fiberpath.config.schemas import (
    HelicalLayer,
    LayerModel,
    MandrelParameters,
    TowParameters,
)

from .calculations import HelicalKinematics, compute_helical_kinematics
from .exceptions import LayerValidationError

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


def validate_helical_layer(
    layer_index: int,
    layer: HelicalLayer,
    mandrel: MandrelParameters,
    tow: TowParameters,
) -> HelicalKinematics:
    if layer.skip_index >= layer.pattern_number:
        raise LayerValidationError(
            layer_index,
            "skipIndex must be less than patternNumber",
        )

    if gcd(layer.skip_index, layer.pattern_number) != 1:
        raise LayerValidationError(
            layer_index,
            "skipIndex and patternNumber must be coprime for full coverage",
        )

    if layer.lead_in_mm >= mandrel.wind_length:
        raise LayerValidationError(
            layer_index,
            (
                f"leadInMM ({layer.lead_in_mm}mm) must be less than the mandrel "
                f"windLength ({mandrel.wind_length}mm); a longer lead-in drives the "
                "carriage off the mandrel into negative coordinates"
            ),
        )

    kinematics = compute_helical_kinematics(layer, mandrel, tow)
    if kinematics.num_circuits % layer.pattern_number != 0:
        raise LayerValidationError(
            layer_index,
            (
                "computed circuit count is not divisible by patternNumber "
                f"({kinematics.num_circuits} % {layer.pattern_number} != 0)"
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
    if layer.pattern_number > 1:
        pattern_step_deg = 360.0 / layer.pattern_number
        per_circuit_mod = (2.0 * layer.lock_degrees) % 360.0

        if round(per_circuit_mod % pattern_step_deg, 6) != 0:
            suggestions = _nearest_valid_lock_degrees(
                layer.lock_degrees, pattern_step_deg, layer.skip_index
            )
            raise LayerValidationError(
                layer_index,
                (
                    f"lockDegrees {layer.lock_degrees}° produces a per-circuit mandrel advance of "
                    f"{per_circuit_mod:.6g}° (mod 360°), which is not divisible by the in-pattern "
                    f"slot width of {pattern_step_deg:.6g}°"
                    f" (= 360 / patternNumber {layer.pattern_number}). "
                    f"Circuits will overlap and leave bare mandrel strips. "
                    f"lockDegrees must be a multiple of {pattern_step_deg / 2:.6g}°. "
                    f"Nearest valid values: {suggestions}"
                ),
            )

        slot_step = (per_circuit_mod + layer.skip_index * pattern_step_deg) % 360.0
        j = round(slot_step / pattern_step_deg) % layer.pattern_number
        if gcd(j, layer.pattern_number) != 1:
            suggestions = _nearest_valid_lock_degrees(
                layer.lock_degrees, pattern_step_deg, layer.skip_index
            )
            raise LayerValidationError(
                layer_index,
                (
                    f"lockDegrees {layer.lock_degrees}° with skipIndex {layer.skip_index} and "
                    f"patternNumber {layer.pattern_number} produces an"
                    f" intra-pattern slot stride of "
                    f"{j} (in units of {pattern_step_deg:.6g}°), which is not coprime with "
                    f"patternNumber (gcd = {gcd(j, layer.pattern_number)}). "
                    f"All in-pattern circuits will alias onto fewer positions,"
                    f" leaving bare strips. "
                    f"Nearest valid lockDegrees values: {suggestions}"
                ),
            )

    return kinematics
