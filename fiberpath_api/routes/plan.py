"""Planning endpoint."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from fiberpath.config import WindDefinition
from fiberpath.planning import plan_wind

from ..schemas import PlanLayer, PlanResponse

router = APIRouter()


@router.post("", response_model=PlanResponse)
def plan(definition: WindDefinition) -> PlanResponse:
    """Plan a wind from an in-memory definition and return the G-code program."""
    result = plan_wind(definition)
    layers = [PlanLayer(**asdict(metric)) for metric in result.layers]
    return PlanResponse(
        commands=len(result.commands),
        gcode="\n".join(result.commands),
        timeSeconds=result.total_time_s,
        towMeters=result.total_tow_m,
        layers=layers,
    )
