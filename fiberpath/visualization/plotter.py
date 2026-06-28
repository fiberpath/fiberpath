"""2D plotting helpers for unwrapped mandrel views.

The plotter consumes a typed :class:`~fiberpath.planning.ir.Program` and reads
geometry straight from its ``RAPID`` moves and metadata — it no longer parses
G-code text or the ``; Parameters`` header. Segment tracking honors ``G92``:
``SET_POSITION`` resets the reference frame (as in ``nominal_metrics``), so the
unwrapped path measures from each reset instead of drawing a spurious backward
sweep at the carriage-parked boundary.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from fiberpath.planning.helpers import Axis
from fiberpath.planning.ir import MoveKind, Program

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
    program: Program,
    config: PlotConfig | None = None,
) -> PlotResult:
    if not program.moves:
        raise PlotError("Program is empty; cannot plot")
    config = config or PlotConfig()
    if config.scale <= 0:
        raise PlotError("Scale must be positive")

    metadata = _extract_metadata(program)
    segments = _collect_segments(program, config.height_degrees)

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
    program: Program,
    height_degrees: float = HEIGHT_DEGREES,
) -> PlotSignature:
    metadata = _extract_metadata(program)
    segments = _collect_segments(program, height_degrees)
    digest = _hash_segments(segments)
    return PlotSignature(metadata=metadata, segments_rendered=len(segments), digest=digest)


def save_plot(
    program: Program,
    destination: Path,
    config: PlotConfig | None = None,
) -> Path:
    result = render_plot(program, config)
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.image.save(destination, format="PNG")
    return destination


def _extract_metadata(program: Program) -> PlotMetadata:
    return PlotMetadata(
        mandrel_length_mm=float(program.meta.wind_length),
        tow_width_mm=float(program.meta.tow_width),
    )


def _collect_segments(
    program: Program,
    height_degrees: float,
) -> list[list[tuple[float, float]]]:
    """Extract unwrapped (carriage, mandrel) segments from the RAPID moves."""
    x_pos = 0.0
    y_pos = 0.0
    segments: list[list[tuple[float, float]]] = []

    for move in program.moves:
        if move.kind is MoveKind.SET_POSITION:
            # G92 redefines the coordinate origin (no motion) — honor it exactly as
            # nominal_metrics does, so the unwrapped path measures from the reset
            # frame instead of drawing a spurious backward sweep at the boundary.
            x_pos = move.targets.get(Axis.CARRIAGE, x_pos)
            y_pos = move.targets.get(Axis.MANDREL, y_pos)
            continue
        if move.kind is not MoveKind.RAPID:
            continue
        next_x = move.targets.get(Axis.CARRIAGE, x_pos)
        next_y = move.targets.get(Axis.MANDREL, y_pos)
        if math.isclose(next_x, x_pos) and math.isclose(next_y, y_pos):
            continue
        segments.extend(_split_segment((x_pos, y_pos), (next_x, next_y), height_degrees))
        x_pos, y_pos = next_x, next_y
    return segments


def _hash_segments(segments: list[list[tuple[float, float]]]) -> str:
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
