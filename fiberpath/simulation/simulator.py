"""Feed-rate aware simulator for generated G-code programs."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fiberpath.gcode.dialects import MarlinDialect


class SimulationError(RuntimeError):
    """Raised when a program cannot be simulated."""


@dataclass(slots=True)
class SimulationResult:
    commands_executed: int
    moves: int
    estimated_time_s: float
    total_distance_mm: float
    tow_length_mm: float
    average_feed_rate_mmpm: float


HEADER_PREFIX = "; Parameters "
DEFAULT_FEED_RATE = 6000.0


def simulate_program(
    commands: Iterable[str],
    *,
    default_feed_rate: float = DEFAULT_FEED_RATE,
    dialect: MarlinDialect | None = None,
) -> SimulationResult:
    """Estimate execution time/tow usage for a G-code program.

    Parameters
    ----------
    commands:
        Iterable of G-code lines (typically `plan_wind(...).commands`).
    default_feed_rate:
        Default feed rate to use until the program sets one explicitly.
    dialect:
        Dialect specifying axis mapping. If None, attempts auto-detection from G-code.
    """

    program = list(commands)
    if not program:
        raise SimulationError("Program is empty")

    # Auto-detect dialect if not provided
    if dialect is None:
        dialect = _detect_dialect(program)

    metadata = _extract_metadata(program)
    mandrel_circumference = math.pi * metadata["mandrel_diameter"]

    feed_rate = default_feed_rate
    if feed_rate <= 0:
        raise SimulationError("Default feed rate must be positive")

    # Get axis letters from dialect
    mapping = dialect.axis_mapping
    carriage_axis = mapping.carriage
    mandrel_axis = mapping.mandrel
    delivery_axis = mapping.delivery_head

    last_carriage = 0.0
    last_mandrel = 0.0
    last_delivery = 0.0

    commands_executed = 0
    moves = 0
    total_distance = 0.0
    tow_length = 0.0
    total_time = 0.0

    for raw_line in program:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(";"):
            commands_executed += 1
            continue

        parts = line.split()
        opcode = parts[0]
        commands_executed += 1

        if opcode not in {"G0", "G1"}:
            # Control commands still count toward execution but contain no motion.
            for token in parts[1:]:
                if token.startswith("F"):
                    feed_rate = float(token[1:])
            continue

        next_carriage = last_carriage
        next_mandrel = last_mandrel
        next_delivery = last_delivery

        for token in parts[1:]:
            axis = token[0]
            value = token[1:]

            if axis == carriage_axis:
                next_carriage = float(value)
            elif axis == mandrel_axis:
                next_mandrel = float(value)
            elif axis == delivery_axis:
                next_delivery = float(value)
            elif axis == "F":
                feed_rate = float(value)

        carriage_delta = next_carriage - last_carriage
        mandrel_delta_deg = next_mandrel - last_mandrel
        delivery_delta = next_delivery - last_delivery

        mandrel_delta_mm = mandrel_delta_deg / 360.0 * mandrel_circumference
        distance_sq = carriage_delta**2 + mandrel_delta_mm**2

        if math.isclose(distance_sq, 0.0) and math.isclose(delivery_delta, 0.0):
            last_carriage, last_mandrel, last_delivery = (
                next_carriage,
                next_mandrel,
                next_delivery,
            )
            continue

        distance = math.sqrt(distance_sq)
        if feed_rate <= 0:
            raise SimulationError("Encountered non-positive feed rate during simulation")

        total_time += distance / feed_rate * 60.0
        total_distance += distance
        # tow length per move equals the Euclidean carriage+mandrel distance
        tow_length += distance
        moves += 1

        last_carriage, last_mandrel, last_delivery = (
            next_carriage,
            next_mandrel,
            next_delivery,
        )

    average_feed_rate = total_distance / total_time * 60.0 if total_time > 0 else feed_rate

    return SimulationResult(
        commands_executed=commands_executed,
        moves=moves,
        estimated_time_s=total_time,
        total_distance_mm=total_distance,
        tow_length_mm=tow_length,
        average_feed_rate_mmpm=average_feed_rate,
    )


def _extract_metadata(program: Sequence[str]) -> dict[str, float]:
    for line in program:
        stripped = line.strip()
        if stripped.startswith(HEADER_PREFIX):
            payload = stripped[len(HEADER_PREFIX) :]
            data = json.loads(payload)
            mandrel = data["mandrel"]
            return {"mandrel_diameter": float(mandrel["diameter"])}
    raise SimulationError("Unable to locate Parameters header in program")


def _detect_dialect(program: Sequence[str]) -> MarlinDialect:
    """Resolve dialect from G-code by examining axis letters in first move command."""
    from fiberpath.gcode.dialects import MARLIN_XAB_STANDARD

    for line in program:
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        parts = stripped.split()
        if parts[0] in {"G0", "G1", "G92"}:
            # Check which axes are present
            axes_found = {token[0] for token in parts[1:] if token[0].isalpha() and token[0] != "F"}

            # XAB is the only supported builtin format in v0.7.0+
            if "A" in axes_found or "B" in axes_found:
                return MARLIN_XAB_STANDARD
            if "Y" in axes_found or "Z" in axes_found:
                raise SimulationError(
                    "Detected unsupported XYZ axis program; re-generate using XAB format."
                )

    return MARLIN_XAB_STANDARD
