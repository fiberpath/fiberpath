from __future__ import annotations

from pathlib import Path

from fiberpath.config import load_wind_definition
from fiberpath.gcode import read_program
from fiberpath.planning import plan_wind
from fiberpath.planning.ir import Program
from fiberpath.visualization.plotter import (
    PlotConfig,
    compute_plot_signature,
    render_plot,
)
from fiberpath_cli.main import app
from typer.testing import CliRunner

SIMPLE_CYLINDER_WIND = Path(__file__).parents[2] / "examples" / "simple_cylinder" / "input.wind"

SIMPLE_CYLINDER_SIGNATURE_DIGEST = (
    "1642dc1a96eba53330a5c21da544470a1956e71190a6ad533a1096c1c446e67c"
)


def _plan_simple_cylinder_commands() -> list[str]:
    definition = load_wind_definition(SIMPLE_CYLINDER_WIND)
    return plan_wind(definition).commands


def _plan_simple_cylinder_program() -> Program:
    return read_program(_plan_simple_cylinder_commands())


def test_render_plot_produces_stable_geometry_signature() -> None:
    program = _plan_simple_cylinder_program()
    signature = compute_plot_signature(program)
    assert signature.digest == SIMPLE_CYLINDER_SIGNATURE_DIGEST
    # G92-aware: the parked-end backward-sweep artifact (1291 blind) is gone (S4).
    assert signature.segments_rendered == 1149
    assert signature.metadata.mandrel_length_mm == 500.0
    assert signature.metadata.tow_width_mm == 7.0

    result = render_plot(program, PlotConfig(scale=0.5))
    assert result.image.size == (250, 180)
    assert result.segments_rendered == signature.segments_rendered


def test_plot_cli_writes_output(tmp_path: Path) -> None:
    commands = _plan_simple_cylinder_commands()
    gcode_path = tmp_path / "program.gcode"
    gcode_path.write_text("\n".join(commands) + "\n", encoding="utf-8")
    runner = CliRunner()
    destination = tmp_path / "preview.png"
    result = runner.invoke(
        app,
        ["plot", str(gcode_path), "--output", str(destination), "--scale", "0.5"],
    )
    assert result.exit_code == 0, result.output
    assert destination.exists()
    assert destination.stat().st_size > 0


def test_render_plot_handles_simple_cylinder_example() -> None:
    program = _plan_simple_cylinder_program()
    signature = compute_plot_signature(program)
    assert signature.digest == SIMPLE_CYLINDER_SIGNATURE_DIGEST
    assert signature.segments_rendered > 0
    result = render_plot(program, PlotConfig(scale=0.5))
    assert result.segments_rendered == signature.segments_rendered


def test_plot_cli_renders_simple_cylinder_example(tmp_path: Path) -> None:
    commands = _plan_simple_cylinder_commands()
    gcode_path = tmp_path / "simple-cylinder.gcode"
    gcode_path.write_text("\n".join(commands) + "\n", encoding="utf-8")
    destination = tmp_path / "simple-cylinder.png"
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plot", str(gcode_path), "--output", str(destination), "--scale", "0.5"],
    )
    assert result.exit_code == 0, result.output
    assert destination.exists()
    assert destination.stat().st_size > 0
