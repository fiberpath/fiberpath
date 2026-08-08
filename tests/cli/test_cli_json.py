from __future__ import annotations

import json
from pathlib import Path

from fiberpath_cli.main import app
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT.parent / "examples"
SIMPLE_WIND = EXAMPLES / "simple_cylinder" / "input.wind"

SIM_HEADER = (
    '; Parameters {"mandrel":{"diameter":50,"windLength":500},"tow":{"width":8,"thickness":0.4}}'
)
SIM_PROGRAM = [SIM_HEADER, "G0 F6000", "G0 X10", "G0 A180", "G0 X10 A360"]


def test_plan_command_json(tmp_path: Path) -> None:
    runner = CliRunner()
    output_file = tmp_path / "out.gcode"

    result = runner.invoke(
        app,
        ["plan", str(SIMPLE_WIND), "--output", str(output_file), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["output"] == str(output_file)
    assert payload["commands"] > 0


VK_FRICTION_WIND = EXAMPLES / "vk_nosecone_friction" / "input.wind"  # frictionLambda = 0.15


def _write_profile(tmp_path: Path, slip_limit: float) -> Path:
    profile = tmp_path / "machine.json"
    profile.write_text(
        json.dumps(
            {
                "id": "test",
                "name": "Test",
                "controller": "marlin",
                "requiredGcodes": ["G0"],
                "slipLimit": slip_limit,
            }
        ),
        encoding="utf-8",
    )
    return profile


def _write_vk_wind(tmp_path: Path, friction_lambda: float) -> Path:
    wind = tmp_path / "part.wind"
    wind.write_text(
        json.dumps(
            {
                "schemaVersion": "1.3",
                "mandrelParameters": {
                    "diameter": 98.0,
                    "windLength": 300.0,
                    "profile": {"type": "vonKarman"},
                },
                "towParameters": {"width": 7.0, "thickness": 0.5},
                "defaultFeedRate": 9000.0,
                "layers": [
                    {
                        "windType": "helical",
                        "windAngle": 30,
                        "patternNumber": 3,
                        "skipIndex": 1,
                        "lockDegrees": 180,
                        "leadInMM": 5,
                        "leadOutDegrees": 15,
                        "frictionLambda": friction_lambda,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return wind


def test_profile_raises_and_lowers_mu_relative_to_the_default(tmp_path: Path) -> None:
    # Discriminating BOTH directions, so neither case is vacuous under the default mu=0.2:
    #   - a lambda=0.25 layer is REJECTED by the default (0.25 > 0.2) but ACCEPTED by a
    #     loose --profile (slipLimit 0.3) -> proves --profile can RAISE mu;
    #   - a lambda=0.15 layer is ACCEPTED by the default (0.15 < 0.2) but REJECTED by a
    #     strict --profile (slipLimit 0.1) -> proves --profile can LOWER mu.
    runner = CliRunner()
    out = tmp_path / "out.gcode"
    high = _write_vk_wind(tmp_path, 0.25)

    default_rejects = runner.invoke(app, ["plan", str(high), "-o", str(out)])
    assert default_rejects.exit_code == 1
    assert "slip limit" in default_rejects.output.lower()

    loose_accepts = runner.invoke(
        app,
        [
            "plan",
            str(high),
            "-o",
            str(out),
            "--profile",
            str(_write_profile(tmp_path, 0.3)),
            "--json",
        ],
    )
    assert loose_accepts.exit_code == 0, loose_accepts.output
    assert json.loads(loose_accepts.stdout)["commands"] > 0

    strict_rejects = runner.invoke(
        app,
        [
            "plan",
            str(VK_FRICTION_WIND),
            "-o",
            str(out),
            "--profile",
            str(_write_profile(tmp_path, 0.1)),
        ],
    )
    assert strict_rejects.exit_code == 1
    assert "slip limit" in strict_rejects.output.lower()


def test_plan_rejects_a_missing_profile(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan",
            str(SIMPLE_WIND),
            "-o",
            str(tmp_path / "o.gcode"),
            "--profile",
            str(tmp_path / "nope.json"),
        ],
    )
    assert result.exit_code == 2  # BadParameter
    assert "profile" in result.output.lower()


def test_simulate_command_json(tmp_path: Path) -> None:
    gcode_file = tmp_path / "program.gcode"
    gcode_file.write_text("\n".join(SIM_PROGRAM) + "\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(app, ["simulate", str(gcode_file), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["commands_executed"] == 5


def test_simulate_command_rejects_directory(tmp_path: Path) -> None:
    """Passing a directory must fail cleanly (typer usage error), not leak a
    raw IsADirectoryError traceback."""
    a_dir = tmp_path / "adir"
    a_dir.mkdir()

    runner = CliRunner()
    result = runner.invoke(app, ["simulate", str(a_dir)])

    assert result.exit_code == 2  # typer usage error, not an unhandled crash


def test_validate_command_json() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["validate", str(SIMPLE_WIND), "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"


def test_stream_command_json(tmp_path: Path) -> None:
    gcode_file = tmp_path / "program.gcode"
    gcode_file.write_text("\n".join(SIM_PROGRAM) + "\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["stream", str(gcode_file), "--dry-run", "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["dryRun"] is True
    assert payload["commands"] > 0
