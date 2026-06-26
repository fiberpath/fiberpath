"""Validation endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from fiberpath.config import WindDefinition
from fiberpath.planning import plan_wind

from ..schemas import BAD_REQUEST_RESPONSE, ValidateResponse

router = APIRouter()


@router.post("", response_model=ValidateResponse, responses=BAD_REQUEST_RESPONSE)
def validate(definition: WindDefinition) -> ValidateResponse:
    """Validate a wind definition.

    The body is schema-checked by pydantic (malformed -> 422). A full plan run
    surfaces semantic errors (e.g. out-of-range wind angle) as PlanningError,
    which the app maps to 400.
    """
    # minimal: reuse the planner for semantic validation rather than duplicating
    # its layer-bound checks; planning is cheap and stays the single source of truth.
    plan_wind(definition)
    return ValidateResponse(valid=True)
