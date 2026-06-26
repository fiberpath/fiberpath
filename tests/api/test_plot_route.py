"""Tests for the body-only plot/preview API route."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from fiberpath_api.main import create_app

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_plot_returns_png() -> None:
    client = TestClient(create_app())
    body = json.loads((EXAMPLES / "simple_cylinder" / "input.wind").read_text(encoding="utf-8"))
    gcode = client.post("/plan", json=body).json()["gcode"]

    response = client.post("/plot", json={"gcode": gcode})

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(_PNG_MAGIC)


def test_plot_rejects_empty_program() -> None:
    client = TestClient(create_app())
    response = client.post("/plot", json={"gcode": "   "})

    assert response.status_code == 400, response.text
