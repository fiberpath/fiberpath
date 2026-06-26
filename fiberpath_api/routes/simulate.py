"""Simulation endpoint."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fiberpath.simulation import simulate_program
from fiberpath.wire import SimulationResultOut

from ..schemas import BAD_REQUEST_RESPONSE, GcodeRequest

router = APIRouter()


@router.post("", response_model=SimulationResultOut, responses=BAD_REQUEST_RESPONSE)
def simulate(payload: GcodeRequest) -> SimulationResultOut:
    commands = payload.gcode.splitlines()
    if not any(line.strip() for line in commands):
        raise HTTPException(status_code=400, detail="gcode contained no commands")
    return SimulationResultOut.from_result(simulate_program(commands))
