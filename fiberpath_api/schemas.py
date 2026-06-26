"""Request/response schemas specific to the API surface.

Compute *results* (plan/simulate) use the shared versioned wire schema in
``fiberpath.wire``. This module holds only the API-local request bodies and the
validation status response.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GcodeRequest(BaseModel):
    gcode: str = Field(
        ...,
        max_length=10_000_000,
        description="G-code program to process, newline separated.",
    )


class ValidateResponse(BaseModel):
    valid: bool


class ApiError(BaseModel):
    """Error envelope returned for 4xx responses (``{"detail": "..."}``)."""

    detail: str


# Reusable OpenAPI declaration for the 400 the compute routes can return when the
# engine rejects otherwise well-formed input (PlanningError/SimulationError/
# PlotError -> 400 via the app's exception handlers). Declaring it makes the
# contract explicit and lets the generated client type the error body.
BAD_REQUEST_RESPONSE: dict[int | str, dict[str, Any]] = {
    400: {"model": ApiError, "description": "Input rejected by the compute engine."}
}
