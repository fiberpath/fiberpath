"""Tests for simulation API route."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from fiberpath_api.main import create_app


def test_simulate_from_file_nonexistent(tmp_path: Path) -> None:
    """Verify that simulating a nonexistent file returns 404."""
    app = create_app()
    client = TestClient(app)
    import os

    os.environ["FIBERPATH_API_ALLOWED_ROOTS"] = str(tmp_path)

    response = client.post(
        "/simulate/from-file",
        json={"path": "missing.gcode"},
    )

    assert response.status_code == 404
    assert "No file found" in response.json()["detail"]


def test_simulate_from_file_success(tmp_path: Path) -> None:
    """Verify that simulating a valid G-code file returns metrics."""
    app = create_app()
    client = TestClient(app)
    import os

    os.environ["FIBERPATH_API_ALLOWED_ROOTS"] = str(tmp_path)

    gcode_file = tmp_path / "test.gcode"
    gcode_file.write_text(
        """; Parameters {"mandrel": {"diameter": 100.0}, "tow": {"width": 3.0}}
G21
G90
G92 X0 A0 B0
F1000
G1 X10 A20 B30
G1 X20 A40 B60
""",
        encoding="utf-8",
    )

    response = client.post(
        "/simulate/from-file",
        json={"path": "test.gcode"},
    )

    assert response.status_code == 200
    data = response.json()

    # Should have 2 moves (G1 commands), positive time/distance
    assert data["moves"] == 2
    assert data["estimated_time_s"] > 0
    assert data["total_distance_mm"] > 0


def test_simulate_from_file_rejects_absolute_path(tmp_path: Path) -> None:
    """Absolute paths are rejected with 400 regardless of root membership."""
    import os

    app = create_app()
    client = TestClient(app)
    os.environ["FIBERPATH_API_ALLOWED_ROOTS"] = str(tmp_path)

    # Pass an absolute path – must be rejected even if it is within the root.
    absolute_path = str(tmp_path / "test.gcode")
    response = client.post("/simulate/from-file", json={"path": absolute_path})

    assert response.status_code == 400
    assert "absolute" in response.json()["detail"].lower()


def test_simulate_from_file_simulation_error_returns_400(tmp_path: Path) -> None:
    """An empty program raises SimulationError, mapped to 400 (not 500)."""
    import os

    app = create_app()
    client = TestClient(app)
    os.environ["FIBERPATH_API_ALLOWED_ROOTS"] = str(tmp_path)

    empty = tmp_path / "empty.gcode"
    empty.write_text("", encoding="utf-8")

    response = client.post("/simulate/from-file", json={"path": "empty.gcode"})

    assert response.status_code == 400, response.text
    assert response.status_code != 500
    assert "empty" in response.json()["detail"].lower()
