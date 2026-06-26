"""Request/response schemas specific to the API surface.

Compute *results* (plan/simulate) use the shared versioned wire schema in
``fiberpath.wire``. This module holds only the API-local request bodies and the
validation status response.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GcodeRequest(BaseModel):
    gcode: str = Field(
        ...,
        max_length=10_000_000,
        description="G-code program to process, newline separated.",
    )


class ValidateResponse(BaseModel):
    valid: bool
