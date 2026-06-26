"""Unit tests for the shared versioned output/wire schema."""

from __future__ import annotations

from pathlib import Path

from fiberpath.config import load_wind_definition
from fiberpath.planning import plan_wind
from fiberpath.simulation import simulate_program
from fiberpath.wire import (
    OUTPUT_SCHEMA_VERSION,
    PlanResultOut,
    SimulationResultOut,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "simple_cylinder" / "input.wind"
# Multi-layer so cumulative_* differs from per-layer values: a time/tow vs
# cumulative-time/tow swap in the mapper is then actually observable.
MULTI = ROOT / "examples" / "multi_layer" / "input.wind"


def test_plan_result_out_maps_engine_dataclass_faithfully() -> None:
    result = plan_wind(load_wind_definition(MULTI))
    wire = PlanResultOut.from_result(result)

    # Guard: the fixture must actually exercise distinct cumulative values,
    # otherwise the per-vs-cumulative assertions below are vacuous.
    assert any(m.cumulative_time_s != m.time_s for m in result.layers)
    assert any(m.cumulative_tow_m != m.tow_m for m in result.layers)

    assert wire.schemaVersion == OUTPUT_SCHEMA_VERSION
    assert wire.commandCount == len(result.commands)
    assert wire.gcode == "\n".join(result.commands)
    assert wire.timeSeconds == result.total_time_s
    assert wire.towMeters == result.total_tow_m
    assert len(wire.layers) == len(result.layers)

    # Assert every layer field maps 1:1 so a swapped/dropped field is caught.
    for wire_layer, engine_layer in zip(wire.layers, result.layers, strict=True):
        assert wire_layer.index == engine_layer.index
        assert wire_layer.windType == engine_layer.wind_type
        assert wire_layer.commandCount == engine_layer.commands
        assert wire_layer.timeSeconds == engine_layer.time_s
        assert wire_layer.cumulativeTimeSeconds == engine_layer.cumulative_time_s
        assert wire_layer.towMeters == engine_layer.tow_m
        assert wire_layer.cumulativeTowMeters == engine_layer.cumulative_tow_m
        assert wire_layer.terminal == engine_layer.terminal


def test_simulation_result_out_maps_engine_dataclass_faithfully() -> None:
    result = plan_wind(load_wind_definition(EXAMPLE))
    sim = simulate_program(result.commands)
    wire = SimulationResultOut.from_result(sim)

    assert wire.schemaVersion == OUTPUT_SCHEMA_VERSION
    assert wire.commandsExecuted == sim.commands_executed
    assert wire.moves == sim.moves
    assert wire.estimatedTimeSeconds == sim.estimated_time_s
    assert wire.totalDistanceMm == sim.total_distance_mm
    assert wire.towLengthMm == sim.tow_length_mm
    assert wire.averageFeedRateMmpm == sim.average_feed_rate_mmpm


def test_wire_schema_is_all_camelcase_and_versioned() -> None:
    """Every field that crosses the wire is camelCase and carries a version."""
    for model in (PlanResultOut, SimulationResultOut):
        fields = set(model.model_fields)
        assert "schemaVersion" in fields
        assert all("_" not in name for name in fields), fields
