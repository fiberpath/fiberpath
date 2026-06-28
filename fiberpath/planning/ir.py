"""Typed, machine-agnostic Motion IR for FiberPath toolpaths.

``plan_wind`` lowers a validated ``WindDefinition`` to a :class:`Program` of
:class:`Move` s; a dialect post-processor (``serialize(program, dialect)``, added
in #274) turns that into G-code text. The IR is the single place motion math
lives — the simulator, plotter, and metrics consume it instead of re-parsing
G-code text.

It deliberately carries only what is emitted today (an opcode audit of the
committed goldens found nothing but ``G0`` / ``G92`` / comment lines), so it is
the smallest representation that is also a clean lowering target for the unified
pattern primitive (#137) and cones (#138). Logical axes stay in the IR; the
X/A/B letters, opcode strings, and header formatting are dialect concerns
resolved only in ``serialize()``.

This module is a pure data vocabulary — construction is the lowering's job, so
there is intentionally no per-kind validation here (the IR is internal, not a
trust boundary; the byte-equal golden gate catches lowering mistakes).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from fiberpath.planning.helpers import Axis

__all__ = ["Move", "MoveKind", "Program", "ProgramMeta"]


class MoveKind(Enum):
    """A toolpath operation kind. Each lowers to exactly one emitted line."""

    RAPID = "rapid"  # absolute positioning -> "G0 <axes>" (also the all-zero init move)
    SET_FEED = "set_feed"  # feed-rate state op -> "G0 F<rate>" (no targets; not a G1 cut)
    SET_POSITION = "set_position"  # zero/redefine axes -> "G92 <subset>"
    COMMENT = "comment"  # annotation -> "; <text>"


@dataclass(slots=True, frozen=True)
class Move:
    """One toolpath operation.

    ``targets`` is absolute and ordered: a ``RAPID`` carries all three axes in
    CARRIAGE, MANDREL, DELIVERY_HEAD order, while a ``SET_POSITION`` carries only
    the axes it sets, in caller order (``serialize()`` relies on this). ``feed``
    is set only for ``SET_FEED``; ``text`` only for ``COMMENT``.
    """

    kind: MoveKind
    targets: dict[Axis, float] = field(default_factory=dict)
    feed: float | None = None
    text: str | None = None


@dataclass(slots=True, frozen=True)
class ProgramMeta:
    """Program-level parameters the consumers need without re-parsing the header."""

    mandrel_diameter: float
    wind_length: float
    tow_width: float
    tow_thickness: float


@dataclass(slots=True)
class Program:
    """A complete toolpath: metadata plus an ordered list of moves."""

    meta: ProgramMeta
    moves: list[Move] = field(default_factory=list)
