"""FiberPath command line interface."""

from __future__ import annotations

import typer

from .plan import plan_command
from .plot import plot_command
from .simulate import simulate_command
from .stream import stream_command
from .validate import validate_command

app = typer.Typer(
    name="FiberPath",
    help="FiberPath utilities for planning and executing filament winding jobs.",
)


app.command("plan")(plan_command)
app.command("plot")(plot_command)
app.command("simulate")(simulate_command)
app.command("validate")(validate_command)
app.command("stream")(stream_command)


if __name__ == "__main__":  # pragma: no cover
    app()
