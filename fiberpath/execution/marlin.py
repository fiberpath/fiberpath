"""Utilities for streaming G-code to Marlin-based controllers."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

DEFAULT_BAUD_RATE = 250_000
DEFAULT_RESPONSE_TIMEOUT = 10.0  # Allow time for slow moves (e.g., large rotations)

LOGGER = logging.getLogger(__name__)


class StreamError(RuntimeError):
    """Raised when streaming cannot proceed."""


class SerialTransport(Protocol):
    """Minimal interface expected by :class:`MarlinStreamer`."""

    def write_line(self, data: str) -> None:
        """Write a G-code line to the transport."""

    def readline(self, timeout: float | None = None) -> str | None:
        """Return a single response line or ``None`` on timeout."""

    def close(self) -> None:
        """Close the transport."""


class PySerialTransport:
    """Serial transport backed by :mod:`pyserial`."""

    def __init__(self, port: str, baud_rate: int, timeout: float) -> None:
        try:
            import serial
        except ImportError as exc:  # pragma: no cover - dependency error surfaced to caller
            raise StreamError(
                "pyserial is required for live streaming; install fiberpath with the CLI extras"
            ) from exc

        self._serial = serial.serial_for_url(
            port,
            baudrate=baud_rate,
            timeout=timeout,
            write_timeout=timeout,
        )

    def write_line(self, data: str) -> None:
        payload = (data + "\n").encode("utf-8")
        self._serial.write(payload)
        self._serial.flush()

    def readline(self, timeout: float | None = None) -> str | None:
        previous_timeout: float | None = None
        if timeout is not None:
            previous_timeout = self._serial.timeout
            self._serial.timeout = timeout
        raw = self._serial.readline()
        if timeout is not None and previous_timeout is not None:
            self._serial.timeout = previous_timeout
        if not raw:
            return None
        return raw.decode("utf-8", errors="ignore").strip()

    def close(self) -> None:
        self._serial.close()


@dataclass(frozen=True)
class StreamProgress:
    """Per-command streaming progress."""

    commands_sent: int
    commands_total: int
    command: str
    dry_run: bool


class MarlinStreamer:
    """Queue and stream G-code to a Marlin controller."""

    def __init__(
        self,
        *,
        port: str | None = None,
        baud_rate: int = DEFAULT_BAUD_RATE,
        response_timeout_s: float = DEFAULT_RESPONSE_TIMEOUT,
        log: Callable[[str], None] | None = None,
        transport: SerialTransport | None = None,
    ) -> None:
        self._port = port
        self._baud_rate = baud_rate
        self._response_timeout = response_timeout_s
        self._log = log
        self._transport = transport
        self._connected = False
        self._startup_handled = transport is not None  # Mock transports skip startup

        self._program: list[str] = []
        self._cursor = 0
        self._commands_sent = 0
        self._total_commands = 0
        self._paused = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def connect(self) -> None:
        """Explicitly connect to Marlin without streaming.

        This establishes the serial connection and waits for Marlin
        to complete its startup sequence. After calling this, you can
        send individual commands or stream programs.
        """
        if self._connected and self._startup_handled:
            return  # Already connected
        self._ensure_connection()

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to Marlin."""
        return self._connected and self._startup_handled

    def load_program(self, commands: Sequence[str]) -> None:
        """Load and sanitize a G-code program for streaming."""

        sanitized: list[str] = []
        total = 0
        for raw in commands:
            line = raw.strip()
            if not line:
                continue
            sanitized.append(line)
            if not line.startswith(";"):
                total += 1
        if not sanitized:
            raise StreamError("G-code program contained no commands")
        self._program = sanitized
        self._cursor = 0
        self._commands_sent = 0
        self._total_commands = total

    def iter_stream(
        self, commands: Sequence[str], *, dry_run: bool = False
    ) -> Iterator[StreamProgress]:
        """Yield progress as commands are streamed.

        Args:
            commands: G-code command sequence to stream.
            dry_run: If True, skip serial I/O and just report progress.
        """
        # Load and sanitize commands
        self.load_program(commands)

        if not self._program:
            raise StreamError("No valid commands to stream")

        while self._cursor < len(self._program):
            # Check if paused - block until resumed
            while self._paused:
                LOGGER.debug("iter_stream - paused, waiting...")
                time.sleep(0.1)  # Check every 100ms

            line = self._program[self._cursor]
            self._cursor += 1

            if not line:
                continue
            if line.startswith(";"):
                if self._log is not None:
                    self._log(line[1:].strip())
                continue

            if not dry_run:
                self.send_command(line)

            self._commands_sent += 1
            yield StreamProgress(
                commands_sent=self._commands_sent,
                commands_total=self._total_commands,
                command=line,
                dry_run=dry_run,
            )

    def pause(self) -> None:
        """Pause streaming by setting the paused flag.

        This causes iter_stream() to block before sending the next command.
        Also sends M0 to Marlin to pause any buffered commands.

        Order of operations:
        1. Set _paused flag to stop Python from sending more commands
        2. Send M0 to Marlin to pause execution of buffered commands

        Note: M0 causes Marlin to pause and NOT send 'ok' until resumed.
        We send the command without waiting for ok to avoid timeout.
        """
        if self._paused:
            raise StreamError("Stream is already paused")

        LOGGER.debug("MarlinStreamer.pause() - setting paused flag")
        # Set paused flag FIRST to stop Python from sending more commands
        self._paused = True

        self._ensure_connection()
        if self._transport is None:
            raise StreamError("Serial transport is not connected")

        # Then send M0 to pause Marlin's execution of buffered commands
        LOGGER.debug("MarlinStreamer.pause() - sending M0")
        self._transport.write_line("M0")
        LOGGER.debug("MarlinStreamer.pause() - M0 sent, streaming blocked")

    def resume(self) -> None:
        """Resume streaming by clearing the paused flag.

        This allows iter_stream() to continue sending commands.
        Also sends M108 to Marlin to resume processing buffered commands.

        Order of operations:
        1. Send M108 to Marlin to resume execution
        2. Clear _paused flag to allow Python to continue sending

        When M108 is sent, Marlin will:
        1. Send 'ok' for the pending M0 command
        2. Resume execution of buffered commands
        3. Eventually send another 'ok' for the M108
        """
        if not self._paused:
            raise StreamError("Stream is not paused")

        LOGGER.debug("MarlinStreamer.resume() - sending M108")
        self._ensure_connection()
        if self._transport is None:
            raise StreamError("Serial transport is not connected")

        # Send M108 to break out of M0 pause
        self._transport.write_line("M108")

        # Wait for the pending 'ok' from M0
        try:
            LOGGER.debug("MarlinStreamer.resume() - waiting for M0's ok")
            self._await_ok()  # This gets the 'ok' from M0
            LOGGER.debug("MarlinStreamer.resume() - got M0's ok")
        except StreamError as e:
            LOGGER.debug("MarlinStreamer.resume() - error waiting for ok: %s", e)
            # Continue anyway - the resume might have worked

        # Clear paused flag to allow iter_stream to continue
        LOGGER.debug("MarlinStreamer.resume() - clearing paused flag")
        self._paused = False
        LOGGER.debug("MarlinStreamer.resume() - streaming unblocked")

    def emergency_stop(self) -> None:
        """Send M112 emergency stop and close connection.

        M112 causes Marlin to halt immediately and not send 'ok'.
        After M112, the connection is unusable and must be closed.
        """
        LOGGER.debug("MarlinStreamer.emergency_stop() - sending M112")
        self._ensure_connection()
        if self._transport is None:
            raise StreamError("Serial transport is not connected")

        # Send M112 but don't wait for 'ok' - Marlin halts immediately
        self._transport.write_line("M112")

        # Close connection - Marlin is halted and won't respond
        LOGGER.debug("MarlinStreamer.emergency_stop() - M112 sent, closing connection")
        self.close()

    def reset_progress(self) -> None:
        """Restart streaming from the first command."""

        self._cursor = 0
        self._commands_sent = 0
        self._paused = False

    def close(self) -> None:
        """Close the underlying transport."""

        if self._transport is not None:
            self._transport.close()
        self._connected = False
        self._startup_handled = False

    def __enter__(self) -> MarlinStreamer:
        return self

    def __exit__(self, *_exc: object) -> None:  # pragma: no cover - trivial
        self.close()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def commands_total(self) -> int:
        return self._total_commands

    @property
    def commands_sent(self) -> int:
        return self._commands_sent

    @property
    def commands_remaining(self) -> int:
        return max(self._total_commands - self._commands_sent, 0)

    @property
    def paused(self) -> bool:
        return self._paused

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_connection(self) -> None:
        if self._connected and self._startup_handled:
            return

        if self._transport is None:
            if self._port is None:
                raise StreamError("Serial port is required for live streaming")
            self._transport = PySerialTransport(self._port, self._baud_rate, self._response_timeout)

        if not self._startup_handled:
            self._wait_for_marlin_ready()
            self._startup_handled = True

        self._connected = True

    def _wait_for_marlin_ready(self) -> None:
        """Wait for Marlin to complete its startup sequence and become ready."""
        if self._transport is None:
            raise StreamError("Serial transport is not connected")

        if self._log is not None:
            self._log("Waiting for Marlin to initialize...")

        # Marlin sends a startup banner on connection. Wait for it to finish.
        # The startup typically ends with configuration dump (M206, M200, etc.)
        # We'll wait up to 5 seconds for the startup to complete, consuming all lines.
        start_time = time.monotonic()
        startup_timeout = 5.0
        last_line_time = start_time
        quiet_period = 0.5  # Wait for 0.5s of silence to confirm startup is done

        startup_lines: list[str] = []
        seen_first_line = False

        while time.monotonic() - start_time < startup_timeout:
            remaining = startup_timeout - (time.monotonic() - start_time)
            # Use a shorter timeout for responsive checking
            line = self._transport.readline(min(remaining, 0.05))

            if line is not None and line.strip():
                startup_lines.append(line.strip())
                last_line_time = time.monotonic()
                seen_first_line = True
                if self._log is not None:
                    self._log(f"[marlin startup] {line.strip()}")

            # Only check for quiet period after we've seen the first line
            # and enough time has passed since the last line
            if seen_first_line:
                time_since_last_line = time.monotonic() - last_line_time
                if time_since_last_line >= quiet_period:
                    if self._log is not None:
                        self._log(f"Marlin ready (received {len(startup_lines)} startup lines)")
                    return

        # If we got here, we either saw no startup or timed out
        if not startup_lines:
            # No startup lines seen - might be already initialized, wrong port, or wrong baud rate
            if self._log is not None:
                self._log("No Marlin startup detected. Controller may already be initialized.")
        else:
            # We timed out while receiving startup - this could be problematic
            if self._log is not None:
                self._log(
                    f"Warning: Startup timeout after {len(startup_lines)} lines. "
                    "Proceeding, but stream may fail if controller is not ready."
                )

    def send_command(self, command: str) -> list[str]:
        """Send a single G-code command and return response lines.

        This is the public API for sending individual commands to Marlin.
        Useful for interactive control (e.g., G28, M114).

        Returns:
            List of response lines received before 'ok'.
        """
        self._ensure_connection()
        if self._transport is None:
            raise StreamError("Serial transport is not connected")

        self._transport.write_line(command)
        responses = self._await_ok()

        return responses

    def _await_ok(self) -> list[str]:
        """Wait for 'ok' response and return all intermediate lines."""
        if self._transport is None:
            raise StreamError("Serial transport is not connected")
        deadline = time.monotonic() + self._response_timeout
        responses: list[str] = []

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                LOGGER.error(
                    "Timeout waiting for Marlin response after %ss", self._response_timeout
                )
                raise StreamError("Timed out waiting for Marlin response")
            line = self._transport.readline(remaining)
            if line is None:
                continue
            line = line.strip()
            if not line:
                continue

            if line == "ok":
                return responses
            if line.startswith("echo:busy"):
                deadline = time.monotonic() + self._response_timeout
                continue
            if line.startswith("Error") or "kill()" in line.lower() or "halted" in line.lower():
                # Fatal error detected - mark connection as broken
                LOGGER.error("Marlin fatal error: %s", line)
                self._connected = False
                self._startup_handled = False
                raise StreamError(f"Marlin reported: {line}")
            # Collect all non-ok responses
            responses.append(line)
            if self._log is not None:
                self._log(f"[marlin] {line}")
