"""Round-trip gate for the boundary G-code reader (#282 / S-bnd of #136).

``read_program`` is the inverse of ``serialize``. Its acceptance is that, for
every frozen golden, ``serialize(read_program(g), dialect)`` reproduces ``g``
**byte-for-byte** — the same kind of empty-diff gate #274 used to prove the
emitter. If this stays green, the reader is faithful and the simulator/plotter
can consume the IR without changing any observable output.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fiberpath.gcode import read_program
from fiberpath.gcode.dialects import MARLIN_XAB_STANDARD
from fiberpath.gcode.reader import ProgramReadError
from fiberpath.gcode.serializer import serialize
from fiberpath.planning.helpers import Axis
from fiberpath.planning.ir import MoveKind

REPO_ROOT = Path(__file__).resolve().parents[2]

# Reuse the frozen golden corpus (smallest first).
GOLDENS: list[str] = [
    "examples/simple_cylinder/expected.gcode",
    "examples/sized_simple_cylinder/expected.gcode",
    "examples/multi_layer/expected.gcode",
    "examples/rocketry/AvBay(470mm)single.gcode",
    "examples/rocketry/AvBay(470mm)triple.gcode",
    "examples/rocketry/MainChute(585mm).gcode",
    "examples/rocketry/CarbonMotorTube(1295mm).gcode",
]


@pytest.mark.parametrize("golden_rel", GOLDENS, ids=GOLDENS)
def test_reader_round_trips_golden_byte_equal(golden_rel: str) -> None:
    expected = (REPO_ROOT / golden_rel).read_text(encoding="utf-8")
    program = read_program(expected.splitlines())
    rendered = "\n".join(serialize(program, MARLIN_XAB_STANDARD)) + "\n"

    if rendered != expected:
        r_lines = rendered.splitlines()
        e_lines = expected.splitlines()
        for i, (r, e) in enumerate(zip(r_lines, e_lines, strict=False)):
            if r != e:
                pytest.fail(
                    f"{golden_rel} round-trip differs at line {i + 1} "
                    f"(rendered {len(r_lines)} lines, golden {len(e_lines)}):\n"
                    f"  expected: {e[:120]!r}\n"
                    f"  rendered: {r[:120]!r}",
                    pytrace=False,
                )
        pytest.fail(
            f"{golden_rel} round-trip matches for "
            f"{min(len(r_lines), len(e_lines))} lines but lengths/newline differ "
            f"(rendered {len(r_lines)}, golden {len(e_lines)}).",
            pytrace=False,
        )


HEADER = (
    '; Parameters {"mandrel":{"diameter":50,"windLength":500},"tow":{"width":8,"thickness":0.4}}'
)


def test_reads_header_into_meta() -> None:
    program = read_program([HEADER, "G0 F6000", "G0 X10"])
    assert program.meta.mandrel_diameter == 50.0
    assert program.meta.wind_length == 500.0
    assert program.meta.tow_width == 8.0
    assert program.meta.tow_thickness == 0.4


def test_lowers_each_opcode() -> None:
    program = read_program([HEADER, "G0 F6000", "; Layer 1", "G92 X0 A90", "G0 X10 A360"])
    kinds = [m.kind for m in program.moves]
    assert kinds == [
        MoveKind.SET_FEED,
        MoveKind.COMMENT,
        MoveKind.SET_POSITION,
        MoveKind.RAPID,
    ]
    assert program.moves[0].feed == 6000.0
    assert program.moves[1].text == "Layer 1"
    assert program.moves[2].targets == {Axis.CARRIAGE: 0.0, Axis.MANDREL: 90.0}
    assert program.moves[3].targets == {Axis.CARRIAGE: 10.0, Axis.MANDREL: 360.0}


def test_modal_preamble_lines_are_skipped() -> None:
    # The serialized preamble (mm / absolute / units-per-minute) carries no motion;
    # the reader drops it and serialize() regenerates it, so round-trips stay
    # byte-exact.
    program = read_program(
        [
            HEADER,
            "G21 ; millimeter units",
            "G90 ; absolute positioning",
            "G94 ; feed rate in units per minute",
            "G0 X10",
        ]
    )
    assert [m.kind for m in program.moves] == [MoveKind.RAPID]
    assert program.moves[0].targets == {Axis.CARRIAGE: 10.0}


@pytest.mark.parametrize("opcode", ["G20", "G91", "G93"])
def test_unhonorable_modes_still_raise(opcode: str) -> None:
    # inch / relative / inverse-time change how coordinates are read and the reader
    # cannot honor them, so they must fail loud rather than be skipped and silently
    # misread as absolute mm.
    with pytest.raises(ProgramReadError, match=opcode):
        read_program([HEADER, opcode, "G0 X10"])


def test_mixed_feed_and_motion_splits_into_two_moves() -> None:
    # External G-code may put feed on a motion line; generated G-code never does.
    program = read_program([HEADER, "G0 X10 F3000"])
    assert [m.kind for m in program.moves] == [MoveKind.SET_FEED, MoveKind.RAPID]
    assert program.moves[0].feed == 3000.0
    assert program.moves[1].targets == {Axis.CARRIAGE: 10.0}


def test_missing_header_raises() -> None:
    with pytest.raises(ProgramReadError):
        read_program(["G0 X1"])


def test_unsupported_opcode_raises() -> None:
    with pytest.raises(ProgramReadError):
        read_program([HEADER, "M104 S200"])


def test_xyz_axis_program_rejected() -> None:
    with pytest.raises(ProgramReadError):
        read_program([HEADER, "G0 Y10 Z5"])
