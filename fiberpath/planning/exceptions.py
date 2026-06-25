"""Custom exceptions raised during planning."""

from __future__ import annotations


class PlanningError(RuntimeError):
    """Raised when the planner encounters a recoverable validation error."""


class LayerValidationError(PlanningError):
    """Raised when layer-specific validation fails."""

    def __init__(self, layer_index: int, message: str) -> None:
        super().__init__(f"Layer {layer_index}: {message}")
