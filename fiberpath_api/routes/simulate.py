"""Simulation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fiberpath.simulation import simulate_program

from ..schemas import GcodeRequest, SimulationResponse

router = APIRouter()


@router.post("", response_model=SimulationResponse)
def simulate(payload: GcodeRequest) -> SimulationResponse:
    commands = payload.gcode.splitlines()
    if not any(line.strip() for line in commands):
        raise HTTPException(status_code=400, detail="gcode contained no commands")
    result = simulate_program(commands)
    return SimulationResponse(
        commands=result.commands_executed,
        moves=result.moves,
        estimated_time_s=result.estimated_time_s,
        total_distance_mm=result.total_distance_mm,
        tow_length_mm=result.tow_length_mm,
        average_feed_rate_mmpm=result.average_feed_rate_mmpm,
    )
