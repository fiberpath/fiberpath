"""CLI command for streaming G-code to a Marlin controller."""

from __future__ import annotations

from pathlib import Path

import typer
from marlin_host import HostError, MarlinHost, SerialTransport

from .output import echo_json

GCODE_ARGUMENT = typer.Argument(..., exists=True, readable=True, file_okay=True, dir_okay=False)
PROGRESS_INTERVAL = 25


def stream_command(
    gcode_file: Path = GCODE_ARGUMENT,
    port: str | None = typer.Option(
        None,
        "--port",
        "-p",
        help="Serial port or pyserial URL (required unless --dry-run).",
    ),
    baud_rate: int = typer.Option(250_000, "--baud-rate", "-b", help="Marlin baud rate."),
    response_timeout: float = typer.Option(
        10.0,
        "--timeout",
        "-t",
        help="Per-response timeout in seconds for slow moves.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Skip serial I/O and just report what would be streamed.",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Print every streamed command."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Emit final summary as JSON (progress lines suppressed).",
    ),
) -> None:
    """Stream the provided G-code file to a Marlin device.

    Reliable framing (line numbers + checksum), bounded waits, and the connection
    handshake are handled by the marlin-host library. Press Ctrl+C to abort a live
    stream gracefully (it stops before the next line); for interactive pause/resume
    use the desktop GUI.
    """
    if not dry_run and port is None:
        raise typer.BadParameter("--port is required for live streaming", param_hint="--port")

    program = (line.strip() for line in gcode_file.read_text(encoding="utf-8").splitlines())
    commands = [line for line in program if line and not line.startswith(";")]
    total = len(commands)
    if total == 0:
        typer.echo("Streaming failed: G-code program contained no commands", err=True)
        raise typer.Exit(code=1)

    sent = 0
    aborted = False
    host: MarlinHost | None = None
    try:
        if dry_run:
            for sent, command in enumerate(commands, start=1):
                if not json_output:
                    typer.echo(f"[{sent}/{total}] (dry-run) {command}")
        else:
            assert port is not None  # guarded above
            host = MarlinHost(
                SerialTransport(port, baud_rate, timeout=response_timeout),
                reliable=True,
                idle_timeout=response_timeout,
            )
            host.connect()
            try:
                for progress in host.stream(commands):
                    sent = progress.commands_sent
                    if not json_output and _should_print(sent, total, verbose=verbose):
                        typer.echo(f"[{sent}/{total}] (live) {progress.command}")
            except KeyboardInterrupt:  # pragma: no cover - interactive abort
                host.stop()
                aborted = True
                if not json_output:
                    typer.echo(f"\nAborted at {sent}/{total} (Ctrl+C).")
    except HostError as exc:
        typer.echo(f"Streaming failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        if host is not None:
            host.close()

    summary = {
        "status": "dry-run" if dry_run else ("aborted" if aborted else "live"),
        "commands": sent,
        "total": total,
        "baudRate": baud_rate,
        "dryRun": dry_run,
    }
    if json_output:
        echo_json(summary)
        return

    status = "Dry-run" if dry_run else ("Aborted" if aborted else "Streamed")
    typer.echo(f"{status} {sent}/{total} commands at {baud_rate} baud.")


def _should_print(sent: int, total: int, *, verbose: bool) -> bool:
    if verbose:
        return True
    if sent in {1, total}:
        return True
    if total <= PROGRESS_INTERVAL:
        return False
    return sent % PROGRESS_INTERVAL == 0
