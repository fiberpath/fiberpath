from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from fiberpath_api.main import create_app

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


def _example_body() -> dict:
    src = (EXAMPLES / "simple_cylinder" / "input.wind").read_text(encoding="utf-8")
    return json.loads(src)


def _bad_helical_body() -> dict:
    # windAngle 95 is a valid PositiveFloat (passes the schema) but is rejected
    # by validate_layer_numeric_bounds (must be 1-89 deg) -> LayerValidationError.
    return {
        "layers": [
            {
                "windType": "helical",
                "windAngle": 95.0,
                "patternNumber": 1,
                "skipIndex": 1,
                "lockDegrees": 180.0,
                "leadInMM": 10.0,
                "leadOutDegrees": 90.0,
            }
        ],
        "mandrelParameters": {"diameter": 50.0, "windLength": 500.0},
        "towParameters": {"width": 8.0, "thickness": 0.4},
        "defaultFeedRate": 6000.0,
    }


def test_plan_returns_gcode_and_metrics() -> None:
    client = TestClient(create_app())
    response = client.post("/plan", json=_example_body())

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["commands"] > 0
    # The body carries the actual program text (no disk round-trip).
    assert payload["gcode"].startswith("; Parameters")
    assert "G0" in payload["gcode"]
    assert payload["timeSeconds"] > 0
    assert payload["towMeters"] > 0
    assert payload["layers"]


def test_plan_rejects_semantic_error() -> None:
    """A body that parses but fails layer validation returns 400, not 500."""
    client = TestClient(create_app())
    response = client.post("/plan", json=_bad_helical_body())

    assert response.status_code == 400, response.text
    assert "wind angle" in response.json()["detail"].lower()


def test_plan_rejects_malformed_body() -> None:
    """Structurally invalid bodies are rejected by pydantic with 422."""
    client = TestClient(create_app())
    response = client.post("/plan", json={"layers": []})

    assert response.status_code == 422, response.text


def test_validate_accepts_valid_definition() -> None:
    client = TestClient(create_app())
    response = client.post("/validate", json=_example_body())

    assert response.status_code == 200, response.text
    assert response.json()["valid"] is True


def test_validate_rejects_semantic_error() -> None:
    client = TestClient(create_app())
    response = client.post("/validate", json=_bad_helical_body())

    assert response.status_code == 400, response.text
    assert "wind angle" in response.json()["detail"].lower()
