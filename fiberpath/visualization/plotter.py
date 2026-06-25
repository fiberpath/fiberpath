"""2D plotting helpers for unwrapped mandrel views."""

from __future__ import annotations

import ast
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from fiberpath.gcode.dialects import MarlinDialect

HEIGHT_DEGREES = 360.0


class PlotError(RuntimeError):
    """Raised when plotting fails due to malformed input."""


@dataclass(slots=True)
class PlotMetadata:
    mandrel_length_mm: float
    tow_width_mm: float


@dataclass(slots=True)
class PlotConfig:
    scale: float = 1.0
    height_degrees: float = HEIGHT_DEGREES
    background_color: tuple[int, int, int] = (255, 255, 255)
    primary_color: tuple[int, int, int] = (73, 0, 168)
    secondary_color: tuple[int, int, int] = (252, 211, 3)
    secondary_width_scale: float = 0.75


@dataclass(slots=True)
class PlotResult:
    image: Image.Image
    metadata: PlotMetadata
    segments_rendered: int

    def to_png_bytes(self) -> bytes:
        buffer = BytesIO()
        self.image.save(buffer, format="PNG")
        return buffer.getvalue()


def render_plot(
    program: Sequence[str],
    config: PlotConfig | None = None,
    dialect: MarlinDialect | None = None,
) -> PlotResult:
    if not program:
        raise PlotError("Program is empty; cannot plot")
    config = config or PlotConfig()
    if config.scale <= 0:
        raise PlotError("Scale must be positive")

    # Auto-detect dialect if not provided
    if dialect is None:
        dialect = _detect_dialect(program)

    metadata = _extract_metadata(program)
    segments = _collect_segments(program, config.height_degrees, dialect)

    width_px = max(1, int(round(metadata.mandrel_length_mm * config.scale)))
    height_px = max(1, int(round(config.height_degrees * config.scale)))
    image = Image.new("RGB", (width_px, height_px), color=config.background_color)

    primary_width = max(1, int(round(metadata.tow_width_mm * config.scale)))
    secondary_width = max(1, int(round(primary_width * config.secondary_width_scale)))

    drawer = ImageDraw.Draw(image)
    for segment in segments:
        points = [_screen_point(point, config.scale, config.height_degrees) for point in segment]
        drawer.line(points, fill=config.primary_color, width=primary_width)
        drawer.line(points, fill=config.secondary_color, width=secondary_width)

    return PlotResult(image=image, metadata=metadata, segments_rendered=len(segments))


@dataclass(slots=True, frozen=True)
class PlotSignature:
    metadata: PlotMetadata
    segments_rendered: int
    digest: str


def compute_plot_signature(
    program: Sequence[str],
    height_degrees: float = HEIGHT_DEGREES,
    dialect: MarlinDialect | None = None,
) -> PlotSignature:
    if dialect is None:
        dialect = _detect_dialect(program)
    metadata = _extract_metadata(program)
    segments = _collect_segments(program, height_degrees, dialect)
    digest = _hash_segments(segments)
    return PlotSignature(metadata=metadata, segments_rendered=len(segments), digest=digest)


def save_plot(
    program: Sequence[str],
    destination: Path,
    config: PlotConfig | None = None,
    dialect: MarlinDialect | None = None,
) -> Path:
    result = render_plot(program, config, dialect)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.image.save(destination, format="PNG")
    return destination


def _extract_metadata(program: Sequence[str]) -> PlotMetadata:
    for line in program:
        stripped = line.strip()
        if stripped.startswith("; Parameters "):
            payload = stripped.split(" ", 2)[2]
            data = ast.literal_eval(payload)
            mandrel = data["mandrel"]
            tow = data["tow"]
            return PlotMetadata(
                mandrel_length_mm=float(mandrel["windLength"]),
                tow_width_mm=float(tow["width"]),
            )
    raise PlotError("Unable to find Parameters header in program")


def _collect_segments(
    program: Sequence[str],
    height_degrees: float,
    dialect: MarlinDialect,
) -> list[list[tuple[float, float]]]:
    """Extract segments with axis-aware parsing."""
    # Get axis letters from dialect
    mapping = dialect.axis_mapping
    carriage_axis = mapping.carriage
    mandrel_axis = mapping.mandrel

    x_pos = 0.0
    y_pos = 0.0
    segments: list[list[tuple[float, float]]] = []

    for raw_line in program:
        line = raw_line.strip()
        if not line or line.startswith(";"):
            continue
        parts = line.split()
        if parts[0] != "G0":
            continue
        next_x = x_pos
        next_y = y_pos
        for token in parts[1:]:
            if token.startswith(carriage_axis):
                next_x = float(token[1:])
            elif token.startswith(mandrel_axis):
                next_y = float(token[1:])
        if math.isclose(next_x, x_pos) and math.isclose(next_y, y_pos):
            continue
        segments.extend(_split_segment((x_pos, y_pos), (next_x, next_y), height_degrees))
        x_pos, y_pos = next_x, next_y
    return segments


def _hash_segments(segments: Sequence[list[tuple[float, float]]]) -> str:
    normalized = [
        [[round(point[0], 6), round(point[1], 6)] for point in segment] for segment in segments
    ]
    payload = json.dumps(normalized, separators=(",", ":")).encode("utf-8")
    return sha256(payload).hexdigest()


def _split_segment(
    start: tuple[float, float],
    end: tuple[float, float],
    height_degrees: float,
) -> list[list[tuple[float, float]]]:
    start_band = math.floor(start[1] / height_degrees)
    end_band = math.floor(end[1] / height_degrees)
    if start_band == end_band or math.isclose(start[1], end[1]):
        return [
            [
                (start[0], _wrap(start[1], height_degrees)),
                (end[0], _wrap(end[1], height_degrees)),
            ]
        ]

    direction = 1.0 if end[1] > start[1] else -1.0
    boundary_band = math.floor(start[1] / height_degrees) + (1 if direction > 0 else 0)
    boundary_y = boundary_band * height_degrees
    dx = end[0] - start[0]
    if math.isclose(dx, 0.0):
        boundary_x = start[0]
    else:
        slope = (end[1] - start[1]) / dx
        boundary_x = start[0] + (boundary_y - start[1]) / slope

    exit_y = height_degrees if direction > 0 else 0.0
    first_segment = [
        [
            (start[0], _wrap(start[1], height_degrees)),
            (boundary_x, exit_y),
        ]
    ]
    epsilon = 0.001 * direction
    remainder_start = (boundary_x, boundary_y + epsilon)
    remainder = _split_segment(remainder_start, end, height_degrees)
    return first_segment + remainder


def _wrap(value: float, height_degrees: float) -> float:
    wrapped = value % height_degrees
    if math.isclose(wrapped, height_degrees):
        return 0.0
    return wrapped


def _screen_point(
    point: tuple[float, float],
    scale: float,
    height_degrees: float,
) -> tuple[float, float]:
    x_px = point[0] * scale
    y_px = (point[1] % height_degrees) * scale
    return (x_px, y_px)


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
                raise PlotError(
                    "Detected unsupported XYZ axis program; re-generate using XAB format."
                )

    return MARLIN_XAB_STANDARD
