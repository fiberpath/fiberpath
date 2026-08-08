"""CLI plan command."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import typer
from fiberpath.config import (
    MachineProfileError,
    WindFileError,
    default_machine_profile,
    load_machine_profile,
    load_wind_definition,
)
from fiberpath.gcode import write_gcode
from fiberpath.planning import PlanOptions, plan_wind
from rich.console import Console
from rich.table import Table

from .output import echo_json

console = Console()

WIND_FILE_ARGUMENT = typer.Argument(..., exists=True, readable=True, help="Input .wind file")
OUTPUT_OPTION = typer.Option(
    Path("output.gcode"), "--output", "-o", help="Destination for generated G-code"
)
VERBOSE_OPTION = typer.Option(False, "--verbose", "-v", help="Emit verbose planner output")
PROFILE_OPTION = typer.Option(
    None,
    "--profile",
    help=(
        "Machine profile JSON (controller/dialect + slip limit μ). Defaults to the bundled "
        "marlin-xab profile. Supply a calibrated profile to set the slipLimit that bounds a "
        "layer's non-geodesic frictionLambda."
    ),
)
JSON_OPTION = typer.Option(
    False,
    "--json",
    help="Emit machine-readable JSON instead of human-readable text.",
)


def plan_command(
    wind_file: Path = WIND_FILE_ARGUMENT,
    output: Path = OUTPUT_OPTION,
    verbose: bool = VERBOSE_OPTION,
    json_output: bool = JSON_OPTION,
    profile: Path | None = PROFILE_OPTION,
) -> None:
    try:
        wind_definition = load_wind_definition(wind_file)
    except WindFileError as exc:  # pragma: no cover - CLI glue
        raise typer.BadParameter(str(exc)) from exc

    # The machine profile carries the controller/dialect and the slip limit μ that bounds a
    # layer's frictionLambda. load_machine_profile validates existence + schema, surfaced as a
    # BadParameter (a bad --profile is user input, not a planner failure).
    if profile is not None:
        try:
            machine_profile = load_machine_profile(profile)
        except MachineProfileError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        machine_profile = default_machine_profile()

    try:
        result = plan_wind(wind_definition, PlanOptions(verbose=verbose, profile=machine_profile))
    except Exception as exc:  # pragma: no cover - defensive guard
        typer.echo(f"Planning failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    destination = write_gcode(result.commands, output)

    summary = {
        "output": str(destination),
        "commands": len(result.commands),
        "timeSeconds": result.total_time_s,
        "towMeters": result.total_tow_m,
        "layers": [asdict(metric) for metric in result.layers],
    }

    if json_output:
        echo_json(summary)
        return

    console.print(f"[green]Wrote[/green] {summary['commands']} commands to {destination}")
    if verbose:
        table = Table(title="Layer metrics", expand=False)
        table.add_column("#", justify="right")
        table.add_column("Type")
        table.add_column("Cmds", justify="right")
        table.add_column("Δt (s)", justify="right")
        table.add_column("Tow (m)", justify="right")
        for metric in result.layers:
            table.add_row(
                str(metric.index),
                metric.wind_type,
                str(metric.commands),
                f"{metric.time_s:.2f}",
                f"{metric.tow_m:.3f}",
            )
        console.print(table)
        console.print(
            f"[cyan]Totals[/cyan] time={result.total_time_s:.2f}s tow={result.total_tow_m:.3f}m"
        )
        console.print(wind_definition.model_dump(mode="json"))
