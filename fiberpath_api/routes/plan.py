"""Planning endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fiberpath.config import WindDefinition
from fiberpath.planning import plan_wind
from fiberpath.wire import PlanResultOut

from ..schemas import BAD_REQUEST_RESPONSE

router = APIRouter()


@router.post("", response_model=PlanResultOut, responses=BAD_REQUEST_RESPONSE)
def plan(definition: WindDefinition) -> PlanResultOut:
    """Plan a wind from an in-memory definition and return the G-code program."""
    return PlanResultOut.from_result(plan_wind(definition))
