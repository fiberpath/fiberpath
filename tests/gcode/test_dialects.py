"""Tests for G-code dialect configurations."""

from __future__ import annotations

from fiberpath.gcode.dialects import MARLIN_XAB_STANDARD, AxisMapping, MarlinDialect


def test_axis_mapping_defaults() -> None:
    """Verify AxisMapping default axis assignments."""
    mapping = AxisMapping()
    assert mapping.carriage == "X"
    assert mapping.mandrel == "A"
    assert mapping.delivery_head == "B"


def test_axis_mapping_rotational_detection() -> None:
    """Verify rotational axis detection for common mappings."""
    linear_mapping = AxisMapping(carriage="X", mandrel="Y", delivery_head="Z")
    assert not linear_mapping.is_rotational_mandrel
    assert not linear_mapping.is_rotational_delivery

    xab_mapping = AxisMapping(carriage="X", mandrel="A", delivery_head="B")
    assert xab_mapping.is_rotational_mandrel
    assert xab_mapping.is_rotational_delivery


def test_marlin_dialect_predefined_xab() -> None:
    """Verify MARLIN_XAB_STANDARD dialect configuration."""
    assert MARLIN_XAB_STANDARD.axis_mapping.carriage == "X"
    assert MARLIN_XAB_STANDARD.axis_mapping.mandrel == "A"
    assert MARLIN_XAB_STANDARD.axis_mapping.delivery_head == "B"
    assert MARLIN_XAB_STANDARD.axis_mapping.is_rotational_mandrel
    assert MARLIN_XAB_STANDARD.axis_mapping.is_rotational_delivery


def test_custom_marlin_dialect() -> None:
    """Verify that custom MarlinDialect instances can be created."""
    custom_axes = AxisMapping(carriage="X", mandrel="C", delivery_head="A")
    custom_dialect = MarlinDialect(axis_mapping=custom_axes)

    assert custom_dialect.axis_mapping.mandrel == "C"
    assert custom_dialect.axis_mapping.is_rotational_mandrel


def test_marlin_dialect_prologue() -> None:
    """The preamble sets units, absolute positioning, and feed mode (in order)."""
    prologue = MarlinDialect().prologue()

    assert [line.split(";")[0].strip() for line in prologue] == ["G21", "G90", "G94"]
