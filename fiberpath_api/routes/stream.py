"""Serial streaming endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fiberpath.execution import MarlinStreamer, StreamError
from pydantic import BaseModel, Field

router = APIRouter()


class StreamRequest(BaseModel):
    gcode: str = Field(
        ...,
        max_length=10_000_000,
        description="Raw G-code to stream, newline separated.",
    )
    port: str | None = Field(
        default=None,
        description="Serial port or pyserial URL. Required when dry_run is false.",
    )
    baud_rate: int = Field(default=250_000, ge=1, description="Controller baud rate.")
    dry_run: bool = Field(default=True, description="Skip serial I/O and only count commands.")


class StreamResponse(BaseModel):
    commands_streamed: int
    total_commands: int
    dry_run: bool


@router.post("/", response_model=StreamResponse)
def start_stream(payload: StreamRequest) -> StreamResponse:
    if not payload.dry_run and payload.port is None:
        raise HTTPException(status_code=400, detail="port is required when dry_run is false")

    commands = payload.gcode.splitlines()
    streamer = MarlinStreamer(port=payload.port, baud_rate=payload.baud_rate)

    try:
        # Use new connection-centric API
        if not payload.dry_run:
            streamer.connect()

        for _update in streamer.iter_stream(commands, dry_run=payload.dry_run):
            pass
    except StreamError as exc:  # pragma: no cover - exercised via API test
        raise HTTPException(status_code=502, detail=f"Streaming failed: {exc}") from exc
    finally:
        streamer.close()

    return StreamResponse(
        commands_streamed=streamer.commands_sent,
        total_commands=streamer.commands_total,
        dry_run=payload.dry_run,
    )
