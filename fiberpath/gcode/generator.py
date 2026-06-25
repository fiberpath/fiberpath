"""Utilities for generating and persisting G-code programs."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class GCodeProgram:
    commands: list[str]

    def as_text(self) -> str:
        return "\n".join(self.commands) + "\n"


def sanitize_program(commands: Iterable[str]) -> list[str]:
    return [stripped for line in commands if (stripped := line.strip())]


def write_gcode(program: GCodeProgram | Sequence[str], destination: str | Path) -> Path:
    target = Path(destination)
    lines = program.commands if isinstance(program, GCodeProgram) else list(program)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
