"""Shared, versioned output/wire schema for compute results.

This module is the single source of truth for the shape of plan and simulation
results as they cross a process boundary (HTTP responses, the OpenAPI-generated
client, persisted output). It is intentionally decoupled from the engine
dataclasses (``PlanResult``, ``SimulationResult``) so the wire format is not
hostage to internal engine refactors: engine results are mapped in via the
``from_result`` constructors, which are the one place renames happen.

Fields are camelCase by design — this is the wire contract, not Python-internal
state — and every result carries ``schemaVersion`` so consumers can evolve
safely. Plot output is binary (``image/png``) and therefore has no JSON wire
schema; its "version" is the image format itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from fiberpath.planning import PlanResult
    from fiberpath.simulation import SimulationResult

# The wire format version. Pinned as a Literal so it surfaces as a required
# const in the OpenAPI/JSON schema: the generated client can rely on it always
# being present and exactly this value. Bump the Literal and the constant
# together (an explicit, reviewable change) when the wire shape evolves.
SchemaVersion = Literal["1.0"]
OUTPUT_SCHEMA_VERSION: SchemaVersion = "1.0"


class PlanLayerOut(BaseModel):
    index: int
    windType: str
    commandCount: int
    timeSeconds: float
    cumulativeTimeSeconds: float
    towMeters: float
    cumulativeTowMeters: float
    terminal: bool


class PlanResultOut(BaseModel):
    schemaVersion: SchemaVersion
    commandCount: int
    gcode: str
    timeSeconds: float
    towMeters: float
    layers: list[PlanLayerOut]

    @classmethod
    def from_result(cls, result: PlanResult) -> PlanResultOut:
        return cls(
            schemaVersion=OUTPUT_SCHEMA_VERSION,
            commandCount=len(result.commands),
            gcode="\n".join(result.commands),
            timeSeconds=result.total_time_s,
            towMeters=result.total_tow_m,
            layers=[
                PlanLayerOut(
                    index=metric.index,
                    windType=metric.wind_type,
                    commandCount=metric.commands,
                    timeSeconds=metric.time_s,
                    cumulativeTimeSeconds=metric.cumulative_time_s,
                    towMeters=metric.tow_m,
                    cumulativeTowMeters=metric.cumulative_tow_m,
                    terminal=metric.terminal,
                )
                for metric in result.layers
            ],
        )


class SimulationResultOut(BaseModel):
    schemaVersion: SchemaVersion
    commandsExecuted: int
    moves: int
    estimatedTimeSeconds: float
    totalDistanceMm: float
    towLengthMm: float
    averageFeedRateMmpm: float

    @classmethod
    def from_result(cls, result: SimulationResult) -> SimulationResultOut:
        return cls(
            schemaVersion=OUTPUT_SCHEMA_VERSION,
            commandsExecuted=result.commands_executed,
            moves=result.moves,
            estimatedTimeSeconds=result.estimated_time_s,
            totalDistanceMm=result.total_distance_mm,
            towLengthMm=result.tow_length_mm,
            averageFeedRateMmpm=result.average_feed_rate_mmpm,
        )
