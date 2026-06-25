from pathlib import Path

from fiberpath.gcode import GCodeProgram, sanitize_program, write_gcode


def test_write_gcode(tmp_path: Path) -> None:
    program = GCodeProgram(commands=["G90", "M2"])
    destination = tmp_path / "test.gcode"

    write_gcode(program, destination)

    assert destination.read_text(encoding="utf-8").strip().splitlines() == ["G90", "M2"]


def test_write_gcode_creates_missing_parent_dirs(tmp_path: Path) -> None:
    # `plan --output subdir/out.gcode` into a non-existent directory previously
    # crashed with a raw FileNotFoundError traceback (plot already guarded this).
    program = GCodeProgram(commands=["G90", "M2"])
    destination = tmp_path / "nested" / "deep" / "out.gcode"

    write_gcode(program, destination)

    assert destination.read_text(encoding="utf-8").strip().splitlines() == ["G90", "M2"]


def test_sanitize_program_trims_whitespace() -> None:
    commands = ["  G0 X0  ", "", "M2   "]
    assert sanitize_program(commands) == ["G0 X0", "M2"]
