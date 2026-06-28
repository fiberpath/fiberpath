"""Serialize the Motion IR to G-code text — the dialect post-processor.

``serialize(program, dialect)`` is the single place that knows axis letters,
number formatting, and the ``; Parameters`` header. It turns the machine-agnostic
:class:`~fiberpath.planning.ir.Program` (metadata + Moves) into the exact G-code
line stream; G-code is a build artifact, not a source of truth.

Number formatting and key order here must reproduce the legacy emitter
byte-for-byte (gated by ``tests/planning/test_example_goldens.py``).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fiberpath.gcode.generator import sanitize_program
from fiberpath.math_utils import strip_precision
from fiberpath.planning.helpers import get_axis_letter
from fiberpath.planning.ir import Move, MoveKind, Program, ProgramMeta

if TYPE_CHECKING:
    from fiberpath.gcode.dialects import AxisMapping, MarlinDialect


def _normalize(value: float) -> float | int:
    """Mirror ``WindDefinition.dump_header``: integral floats render as ints."""
    return int(value) if value.is_integer() else value


def _render_header(meta: ProgramMeta) -> str:
    # Key order (diameter, windLength, width, thickness) reproduces the pydantic
    # model_dump(by_alias=True) order the legacy header relied on.
    payload = {
        "mandrel": {
            "diameter": _normalize(meta.mandrel_diameter),
            "windLength": _normalize(meta.wind_length),
        },
        "tow": {
            "width": _normalize(meta.tow_width),
            "thickness": _normalize(meta.tow_thickness),
        },
    }
    return f"; Parameters {json.dumps(payload, separators=(',', ':'))}"


def render_move(move: Move, mapping: AxisMapping) -> str:
    """Render one Move to exactly one G-code line."""
    if move.kind is MoveKind.COMMENT:
        return f"; {move.text}"
    if move.kind is MoveKind.SET_FEED:
        assert move.feed is not None  # SET_FEED always carries a feed rate
        return f"G0 F{strip_precision(move.feed)}"
    opcode = "G92" if move.kind is MoveKind.SET_POSITION else "G0"
    parts = [opcode]
    for axis, value in move.targets.items():
        parts.append(f"{get_axis_letter(axis, mapping)}{strip_precision(value)}")
    return " ".join(parts)


def serialize(program: Program, dialect: MarlinDialect) -> list[str]:
    """Render a Program to G-code lines: header from metadata, then each move."""
    mapping = dialect.axis_mapping
    lines = [_render_header(program.meta)]
    lines.extend(render_move(move, mapping) for move in program.moves)
    return sanitize_program(lines)
