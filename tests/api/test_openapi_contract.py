"""Contract tests for the generated OpenAPI spec."""

from __future__ import annotations

import pytest
from fiberpath_api.main import create_app


@pytest.mark.parametrize("path", ["/plan", "/simulate", "/validate", "/plot"])
def test_compute_route_declares_400(path: str) -> None:
    """Each compute route documents the engine-validation 400 the GUI relies on."""
    spec = create_app().openapi()
    responses = spec["paths"][path]["post"]["responses"]
    assert "400" in responses, f"{path} does not declare a 400 response"


def test_api_error_schema_present() -> None:
    spec = create_app().openapi()
    assert "ApiError" in spec["components"]["schemas"]
