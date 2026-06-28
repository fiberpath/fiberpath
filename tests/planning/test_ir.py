"""Unit tests for the Motion IR vocabulary (fiberpath.planning.ir)."""

from __future__ import annotations

from fiberpath.planning.helpers import Axis
from fiberpath.planning.ir import Move, MoveKind, Program, ProgramMeta


def test_move_defaults() -> None:
    move = Move(kind=MoveKind.RAPID)
    assert move.targets == {}
    assert move.feed is None
    assert move.text is None


def test_construct_each_kind() -> None:
    rapid = Move(
        kind=MoveKind.RAPID,
        targets={Axis.CARRIAGE: 0.0, Axis.MANDREL: 540.0, Axis.DELIVERY_HEAD: 0.0},
    )
    set_feed = Move(kind=MoveKind.SET_FEED, feed=10000.0)
    set_position = Move(kind=MoveKind.SET_POSITION, targets={Axis.MANDREL: 0.0})
    comment = Move(kind=MoveKind.COMMENT, text="\tPattern: 1/14 Circuit: 1/3")

    assert rapid.kind is MoveKind.RAPID
    assert set_feed.feed == 10000.0 and set_feed.targets == {}
    assert set_position.targets == {Axis.MANDREL: 0.0}
    assert comment.text == "\tPattern: 1/14 Circuit: 1/3"


def test_targets_preserve_insertion_order() -> None:
    # serialize() relies on RAPID emitting axes in CARRIAGE, MANDREL, DELIVERY order.
    targets = {Axis.CARRIAGE: 1.0, Axis.MANDREL: 2.0, Axis.DELIVERY_HEAD: 3.0}
    move = Move(kind=MoveKind.RAPID, targets=targets)
    assert list(move.targets.keys()) == [Axis.CARRIAGE, Axis.MANDREL, Axis.DELIVERY_HEAD]


def test_move_value_equality() -> None:
    a = Move(kind=MoveKind.RAPID, targets={Axis.CARRIAGE: 1.0})
    b = Move(kind=MoveKind.RAPID, targets={Axis.CARRIAGE: 1.0})
    assert a == b


def test_move_is_frozen() -> None:
    move = Move(kind=MoveKind.COMMENT, text="x")
    try:
        move.text = "y"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("Move should be frozen")


def test_program_meta_and_program() -> None:
    meta = ProgramMeta(mandrel_diameter=152.0, wind_length=1460.0, tow_width=8.2, tow_thickness=0.5)
    program = Program(meta=meta)
    assert program.moves == []

    program.moves.append(Move(kind=MoveKind.SET_FEED, feed=9000.0))
    assert len(program.moves) == 1
    assert program.meta.mandrel_diameter == 152.0
