from __future__ import annotations

from collections import deque

import pytest
from fiberpath.execution import MarlinStreamer, StreamError


class DummyTransport:
    def __init__(self) -> None:
        self.written: list[str] = []
        self._responses: deque[str] = deque()

    def queue_front(self, *lines: str) -> None:
        for line in reversed(lines):
            self._responses.appendleft(line)

    def write_line(self, data: str) -> None:
        self.written.append(data)
        self._responses.append("ok")

    def readline(self, timeout: float | None = None) -> str | None:  # noqa: ARG002
        if not self._responses:
            return None
        return self._responses.popleft()

    def close(self) -> None:  # pragma: no cover - nothing to close
        return None


def test_iter_stream_sends_commands_and_skips_comments() -> None:
    transport = DummyTransport()
    streamer = MarlinStreamer(transport=transport)

    progress = list(streamer.iter_stream(["; header", "G0 X1", "", "G1 Y2 F1000"]))

    assert [p.command for p in progress] == ["G0 X1", "G1 Y2 F1000"]
    assert transport.written == ["G0 X1", "G1 Y2 F1000"]
    assert streamer.commands_total == 2
    assert streamer.commands_sent == 2


def test_pause_and_resume_issue_m_codes() -> None:
    transport = DummyTransport()
    streamer = MarlinStreamer(transport=transport)

    list(streamer.iter_stream(["G0 X1"]))

    streamer.pause()
    streamer.resume()

    assert transport.written[-2:] == ["M0", "M108"]


def test_stream_raises_on_marlin_error() -> None:
    transport = DummyTransport()
    streamer = MarlinStreamer(transport=transport)
    transport.queue_front("Error: printer halted")

    with pytest.raises(StreamError):
        next(streamer.iter_stream(["G1 X5"]))


def test_marlin_startup_sequence_consumed() -> None:
    """Verify that Marlin's startup banner is properly consumed before streaming."""

    class StartupTransport:
        """Realistic transport that simulates Marlin's startup behavior."""

        def __init__(self) -> None:
            self.written: list[str] = []
            self._startup_index = 0
            self._responses: deque[str] = deque()
            # Simulate Marlin's startup banner
            self._startup_lines = [
                "start",
                "Marlin bugfix-2.1.x",
                "echo: Last Updated: 2025-11-13",
                "echo: Compiled: Dec  9 2025",
                "echo:; Linear Units:",
                "echo:  G21 ; (mm)",
                "echo:; Steps per unit:",
                "echo:  M92 X81.00 Y1.00 Z1.00 A15.00 B15.00",
                "echo:; Max feedrates (units/s):",
                "echo:  M203 X80.00 Y1.00 Z1.00 A5.00 B5.00",
            ]

        def write_line(self, data: str) -> None:
            """Write command and queue 'ok' response."""
            self.written.append(data)
            self._responses.append("ok")

        def readline(self, timeout: float | None = None) -> str | None:
            """Return startup lines first, then queued responses."""
            # First, drain startup banner
            if self._startup_index < len(self._startup_lines):
                line = self._startup_lines[self._startup_index]
                self._startup_index += 1
                return line

            # Then return any queued responses (from write_line)
            if self._responses:
                return self._responses.popleft()

            # Otherwise timeout (return None)
            return None

        def close(self) -> None:
            pass

    transport = StartupTransport()
    # Create streamer that will use this transport when it connects
    streamer = MarlinStreamer(port="test_port")
    # Inject transport to avoid actual serial connection
    streamer._transport = transport
    # Don't set _startup_handled - let the code handle it naturally

    # Stream should automatically handle startup
    progress = list(streamer.iter_stream(["G0 X1", "G1 Y2"]))

    # Verify all startup lines were consumed
    assert transport._startup_index == len(transport._startup_lines)
    # Verify commands were sent after startup
    assert len(progress) == 2
    assert transport.written == ["G0 X1", "G1 Y2"]


def test_reconnection_handles_startup_again() -> None:
    """Verify that reconnecting after close() properly handles startup again."""
    transport = DummyTransport()
    streamer = MarlinStreamer(transport=transport)

    # First stream
    list(streamer.iter_stream(["G0 X1"]))
    assert transport.written == ["G0 X1"]

    # Close and verify state reset
    streamer.close()
    assert not streamer._connected
    assert not streamer._startup_handled

    # Reconnect with new transport (simulating new serial connection)
    new_transport = DummyTransport()
    streamer._transport = new_transport
    streamer.reset_progress()

    # Should handle startup again (even though it's a mock)
    list(streamer.iter_stream(["G1 Y2"]))
    assert new_transport.written == ["G1 Y2"]


def test_startup_timeout_proceeds_with_warning() -> None:
    """Verify that startup timeout doesn't crash but logs a warning."""

    class SlowStartupTransport:
        """Transport that never finishes sending startup (simulates hung controller)."""

        def __init__(self) -> None:
            self.written: list[str] = []
            self._responses: deque[str] = deque()
            self.log_messages: list[str] = []

        def write_line(self, data: str) -> None:
            self.written.append(data)
            self._responses.append("ok")

        def readline(self, timeout: float | None = None) -> str | None:
            if self._responses:
                return self._responses.popleft()
            # Always return None (simulating slow/hung startup)
            return None

        def close(self) -> None:
            pass

    transport = SlowStartupTransport()

    def capture_log(msg: str) -> None:
        transport.log_messages.append(msg)

    streamer = MarlinStreamer(port="test_port", log=capture_log, response_timeout_s=0.2)
    streamer._transport = transport

    # Should timeout during startup but proceed
    list(streamer.iter_stream(["G0 X1"]))

    # Verify warning was logged
    assert any("No Marlin startup detected" in msg for msg in transport.log_messages)
    # Verify command was still sent (streamer proceeded despite no startup)
    assert transport.written == ["G0 X1"]


def _force_unconnected(streamer: MarlinStreamer) -> None:
    """Make _ensure_connection a no-op so _transport stays None at the guard."""
    streamer._ensure_connection = lambda: None  # type: ignore[method-assign]


@pytest.mark.parametrize("operation", ["send_command", "pause", "resume", "emergency_stop"])
def test_transport_guard_raises_streamerror(operation: str) -> None:
    """A None transport at a guard site raises StreamError, not AttributeError.

    Under the previous ``assert self._transport is not None`` guards this same
    setup raised ``AttributeError`` (or, under ``python -O``, dereferenced None),
    so this is a true regression guard for issue #103.
    """
    streamer = MarlinStreamer(port="dummy")
    _force_unconnected(streamer)
    if operation == "resume":
        streamer._paused = True

    method = getattr(streamer, operation)
    args = ("G0 X1",) if operation == "send_command" else ()
    with pytest.raises(StreamError):
        method(*args)


def test_transport_guard_raises_under_optimized_python() -> None:
    """The guard still raises StreamError when assertions are stripped (python -O)."""
    import subprocess
    import sys

    code = (
        "from fiberpath.execution import MarlinStreamer, StreamError\n"
        "s = MarlinStreamer(port='dummy')\n"
        "s._ensure_connection = lambda: None\n"
        "try:\n"
        "    s.send_command('G0 X1')\n"
        "except StreamError:\n"
        "    print('OK')\n"
    )
    result = subprocess.run(
        [sys.executable, "-O", "-c", code],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_pause_resume_emit_no_debug_noise_on_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A normal stream/pause/resume cycle produces no debug output by default.

    The streaming code logs via `logging.debug`; with no handler configured the
    messages stay silent. Before #102 these were `print(..., file=sys.stderr)`
    calls, so this is a regression guard for the logging migration.
    """
    transport = DummyTransport()
    streamer = MarlinStreamer(transport=transport)

    list(streamer.iter_stream(["G0 X1"]))
    streamer.pause()
    streamer.resume()

    captured = capsys.readouterr()
    assert "[DEBUG]" not in captured.err
    assert "[DEBUG]" not in captured.out
    assert captured.err == ""
