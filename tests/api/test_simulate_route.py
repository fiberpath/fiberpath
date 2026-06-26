"""Tests for the body-only simulation API route."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from fiberpath_api.main import create_app

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"

_PROGRAM = "\n".join(
    [
        '; Parameters {"mandrel":{"diameter":50,"windLength":500},'
        '"tow":{"width":8,"thickness":0.4}}',
        "G0 F6000",
        "G0 X10",
        "G0 A180",
        "G0 X10 A360",
    ]
)


def test_simulate_from_gcode_body() -> None:
    client = TestClient(create_app())
    response = client.post("/simulate", json={"gcode": _PROGRAM})

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["commands"] == 5
    assert payload["moves"] == 3
    assert payload["estimated_time_s"] > 0


def test_simulate_rejects_empty_program() -> None:
    """An empty/whitespace program is a client error (400), not a 500."""
    client = TestClient(create_app())
    response = client.post("/simulate", json={"gcode": "   \n  "})

    assert response.status_code == 400, response.text


def test_plan_simulate_roundtrip() -> None:
    """The gcode returned by /plan feeds straight into /simulate."""
    client = TestClient(create_app())
    body = json.loads((EXAMPLES / "simple_cylinder" / "input.wind").read_text(encoding="utf-8"))

    plan = client.post("/plan", json=body)
    assert plan.status_code == 200, plan.text
    gcode = plan.json()["gcode"]

    sim = client.post("/simulate", json={"gcode": gcode})
    assert sim.status_code == 200, sim.text
    assert sim.json()["commands"] > 0
