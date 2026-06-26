"""Pydantic schemas shared by API routes.

Requests and responses are body-only: planning and validation take a
``WindDefinition`` body, while simulation and plotting take a G-code program.
No filesystem paths cross the API boundary.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GcodeRequest(BaseModel):
    gcode: str = Field(
        ...,
        max_length=10_000_000,
        description="G-code program to process, newline separated.",
    )


class PlanLayer(BaseModel):
    index: int
    wind_type: str
    commands: int
    time_s: float
    cumulative_time_s: float
    tow_m: float
    cumulative_tow_m: float
    terminal: bool


class PlanResponse(BaseModel):
    commands: int
    gcode: str = Field(..., description="The generated G-code program.")
    timeSeconds: float
    towMeters: float
    layers: list[PlanLayer]


class SimulationResponse(BaseModel):
    commands: int
    moves: int
    estimated_time_s: float
    total_distance_mm: float
    tow_length_mm: float
    average_feed_rate_mmpm: float


class ValidateResponse(BaseModel):
    valid: bool
