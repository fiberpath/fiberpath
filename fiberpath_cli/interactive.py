"""Interactive mode for GUI integration via JSON stdin/stdout protocol.

This module provides a JSON-based protocol for controlling MarlinStreamer
from GUI applications. Commands are sent via stdin, responses via stdout.

Architecture:
    - Streaming runs in background thread (non-blocking)
    - Main loop remains responsive to all commands during streaming
    - No race conditions: each thread owns its own resources
    - Clean separation: streaming logic separate from command dispatch

Protocol:
    Input (stdin): JSON objects, one per line
    Output (stdout): JSON responses, one per line

    Request-Response Correlation (Phase 2):
        - Commands may include optional "requestId" field
        - Responses include matching "requestId" if present in request
        - Progress events have no requestId (broadcast events)
        - Enables single-reader routing in Rust bridge

Actions:
    - list_ports: List available serial ports
    - connect: Establish connection to Marlin
    - disconnect: Close connection
    - send: Send single G-code command
    - stream: Stream G-code file (non-blocking, runs in background)
    - pause: Pause streaming (works during active stream)
    - resume: Resume streaming (works during active stream)
    - stop: Stop streaming (works during active stream)

Example:
    {"action": "list_ports", "requestId": 1}
    {"action": "connect", "port": "COM3", "baudRate": 250000, "requestId": 2}
    {"action": "send", "gcode": "G28", "requestId": 3}
    {"action": "stream", "file": "path/to/file.gcode", "requestId": 4}
    {"action": "pause", "requestId": 5}
    {"action": "resume", "requestId": 6}
    {"action": "stop", "requestId": 7}
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
from pathlib import Path
from typing import Any

import serial.tools.list_ports
from fiberpath.execution import MarlinStreamer, StreamError, StreamProgress

LOGGER = logging.getLogger(__name__)


class StreamingSession:
    """Manages a background streaming session.

    This class runs streaming in a separate thread, allowing the main
    command loop to remain responsive to pause/resume/stop commands.
    Progress is tracked via shared state instead of queuing to avoid lag.
    """

    def __init__(self, streamer: MarlinStreamer, commands: list[str], file_path: str):
        self.streamer = streamer
        self.commands = commands
        self.file_path = file_path
        self.thread: threading.Thread | None = None
        self._stop_requested = False
        self._error: tuple[str, str] | None = None  # (message, code)
        self._completed = False
        self._last_command = ""
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start streaming in background thread."""
        self.thread = threading.Thread(
            target=self._stream_worker,
            daemon=False,
            name="streaming-worker",
        )
        self.thread.start()

    def request_stop(self) -> None:
        """Request the streaming thread to stop gracefully."""
        with self._lock:
            self._stop_requested = True

    def is_stop_requested(self) -> bool:
        """Check if stop has been requested."""
        with self._lock:
            return self._stop_requested

    def _stream_worker(self) -> None:
        """Background thread that performs the actual streaming."""
        try:
            for progress in self.streamer.iter_stream(self.commands):
                if self.is_stop_requested():
                    return
                # Track last command for display
                with self._lock:
                    self._last_command = progress.command
            # Completed successfully
            with self._lock:
                self._completed = True
        except StreamError as e:
            with self._lock:
                self._error = (str(e), "STREAM_FAILED")
        except Exception as e:
            with self._lock:
                self._error = (f"Unexpected error: {e}", "INTERNAL_ERROR")

    def is_alive(self) -> bool:
        """Check if streaming thread is still running."""
        return self.thread is not None and self.thread.is_alive()

    def is_completed(self) -> bool:
        """Check if streaming completed successfully."""
        with self._lock:
            return self._completed

    def get_error(self) -> tuple[str, str] | None:
        """Get error if one occurred, returns (message, code) or None."""
        with self._lock:
            return self._error

    def get_progress(self) -> tuple[int, int, bool, str]:
        """Get current progress: (commands_sent, commands_total, paused, last_command)."""
        with self._lock:
            last_cmd = self._last_command
        return (
            self.streamer.commands_sent,
            self.streamer.commands_total,
            self.streamer.paused,
            last_cmd,
        )


def send_response(data: dict[str, Any], request_id: int | None = None) -> None:
    """Send JSON response to stdout and flush.

    Args:
        data: Response data dictionary
        request_id: Optional request ID for correlation
    """
    if request_id is not None:
        data = {"requestId": request_id, **data}
    print(json.dumps(data), flush=True)


def send_error(message: str, code: str = "ERROR", request_id: int | None = None) -> None:
    """Send error response."""
    send_response({"status": "error", "code": code, "message": message}, request_id)


def send_progress(progress: StreamProgress) -> None:
    """Send streaming progress event (no requestId)."""
    send_response(
        {
            "status": "progress",
            "commandsSent": progress.commands_sent,
            "commandsTotal": progress.commands_total,
            "command": progress.command,
            "dryRun": progress.dry_run,
        }
    )


def stdin_reader_thread(command_queue: queue.Queue[dict[str, Any] | None]) -> None:
    """Background thread that reads from stdin and puts commands in queue."""
    try:
        for line in sys.stdin:
            try:
                command = json.loads(line)
                command_queue.put(command)
            except json.JSONDecodeError as e:
                command_queue.put({"_parse_error": str(e)})
    except Exception:
        pass
    finally:
        command_queue.put(None)


def interactive_mode() -> None:
    """Run interactive JSON protocol loop."""
    streamer: MarlinStreamer | None = None
    streaming_session: StreamingSession | None = None
    command_queue: queue.Queue[dict[str, Any] | None] = queue.Queue()

    reader_thread = threading.Thread(
        target=stdin_reader_thread,
        args=(command_queue,),
        daemon=True,
        name="stdin-reader",
    )
    reader_thread.start()

    try:
        while True:
            # Check for streaming progress by polling shared state
            if streaming_session is not None:
                # Check if thread completed
                if not streaming_session.is_alive():
                    error = streaming_session.get_error()
                    if error:
                        message, code = error
                        send_error(message, code)
                        if streamer and not streamer.is_connected:
                            send_response({"status": "disconnected", "reason": "fatal_error"})
                    elif streaming_session.is_completed():
                        send_response(
                            {
                                "status": "complete",
                                "commandsSent": streaming_session.streamer.commands_sent,
                                "commandsTotal": streaming_session.streamer.commands_total,
                            }
                        )
                    streaming_session = None
                else:
                    # Thread is running - emit current progress
                    commands_sent, commands_total, _, last_cmd = streaming_session.get_progress()
                    send_progress(
                        StreamProgress(
                            commands_sent=commands_sent,
                            commands_total=commands_total,
                            command=last_cmd,
                            dry_run=False,
                        )
                    )

            # Get next command
            try:
                command = command_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if command is None:
                if streaming_session and streaming_session.is_alive():
                    streaming_session.request_stop()
                    send_response({"status": "stopped", "reason": "stdin_closed"})
                break

            if "_parse_error" in command:
                send_error(f"Invalid JSON: {command['_parse_error']}", "PARSE_ERROR")
                continue

            try:
                action = command.get("action")
                request_id = command.get("requestId")

                if action == "list_ports":
                    try:
                        ports = serial.tools.list_ports.comports()
                        ports_data = [
                            {
                                "port": p.device,
                                "description": p.description,
                                "hwid": p.hwid,
                            }
                            for p in ports
                        ]
                        send_response({"status": "ok", "ports": ports_data}, request_id)
                    except Exception as e:
                        send_error(
                            f"Failed to list ports: {e}",
                            "PORT_DISCOVERY_FAILED",
                            request_id,
                        )

                elif action == "connect":
                    port = command.get("port")
                    baud_rate = command.get("baudRate", 250_000)
                    timeout = command.get("timeout", 10.0)

                    if not port:
                        send_error("Port is required", "MISSING_PORT", request_id)
                        continue

                    try:
                        if streamer is not None:
                            streamer.close()

                        streamer = MarlinStreamer(
                            port=port,
                            baud_rate=baud_rate,
                            response_timeout_s=timeout,
                        )
                        streamer.connect()
                        send_response(
                            {
                                "status": "connected",
                                "port": port,
                                "baudRate": baud_rate,
                            },
                            request_id,
                        )
                    except StreamError as e:
                        send_error(f"Connection failed: {e}", "CONNECTION_FAILED", request_id)

                elif action == "disconnect":
                    if streaming_session and streaming_session.is_alive():
                        streaming_session.request_stop()
                        if streaming_session.thread:
                            streaming_session.thread.join(timeout=1.0)
                        streaming_session = None

                    if streamer is not None:
                        streamer.close()
                        streamer = None
                        send_response({"status": "disconnected"}, request_id)
                    else:
                        send_response(
                            {"status": "disconnected", "message": "Not connected"},
                            request_id,
                        )

                elif action == "send":
                    gcode = command.get("gcode")

                    if not gcode:
                        send_error("G-code is required", "MISSING_GCODE", request_id)
                        continue

                    if streamer is None or not streamer.is_connected:
                        send_error("Not connected to Marlin", "NOT_CONNECTED", request_id)
                        continue

                    try:
                        responses = streamer.send_command(gcode)
                        send_response(
                            {
                                "status": "ok",
                                "command": gcode,
                                "responses": responses,
                            },
                            request_id,
                        )
                    except StreamError as e:
                        send_error(f"Command failed: {e}", "COMMAND_FAILED", request_id)

                elif action == "stream":
                    file_path = command.get("file")

                    if not file_path:
                        send_error("File path is required", "MISSING_FILE", request_id)
                        continue

                    if streamer is None or not streamer.is_connected:
                        send_error("Not connected to Marlin", "NOT_CONNECTED", request_id)
                        continue

                    if streaming_session and streaming_session.is_alive():
                        send_error(
                            "Streaming already in progress",
                            "ALREADY_STREAMING",
                            request_id,
                        )
                        continue

                    try:
                        path = Path(file_path)
                        if not path.exists():
                            send_error(
                                f"File not found: {file_path}",
                                "FILE_NOT_FOUND",
                                request_id,
                            )
                            continue

                        commands = path.read_text(encoding="utf-8").splitlines()
                        non_comment_commands = [
                            c for c in commands if c.strip() and not c.strip().startswith(";")
                        ]

                        streaming_session = StreamingSession(
                            streamer=streamer, commands=commands, file_path=file_path
                        )
                        streaming_session.start()

                        send_response(
                            {
                                "status": "streaming",
                                "file": file_path,
                                "totalCommands": len(non_comment_commands),
                            },
                            request_id,
                        )
                    except StreamError as e:
                        send_error(f"Streaming failed: {e}", "STREAM_FAILED", request_id)
                        if streamer and not streamer.is_connected:
                            send_response({"status": "disconnected", "reason": "fatal_error"})

                elif action == "pause":
                    LOGGER.debug("Pause command received")
                    if streamer is None or not streamer.is_connected:
                        send_error("Not connected to Marlin", "NOT_CONNECTED", request_id)
                        continue

                    if not streaming_session or not streaming_session.is_alive():
                        send_error("Not currently streaming", "NOT_STREAMING", request_id)
                        continue

                    try:
                        LOGGER.debug("Calling streamer.pause()")
                        streamer.pause()
                        LOGGER.debug("Pause successful, sending response")
                        send_response({"status": "paused"}, request_id)
                    except StreamError as e:
                        LOGGER.debug("Pause failed with error: %s", e)
                        send_error(f"Pause failed: {e}", "PAUSE_FAILED", request_id)

                elif action == "resume":
                    LOGGER.debug("Resume command received")
                    if streamer is None or not streamer.is_connected:
                        send_error("Not connected to Marlin", "NOT_CONNECTED", request_id)
                        continue

                    if not streaming_session or not streaming_session.is_alive():
                        send_error("Not currently streaming", "NOT_STREAMING", request_id)
                        continue

                    try:
                        LOGGER.debug("Calling streamer.resume()")
                        streamer.resume()
                        LOGGER.debug("Resume successful, sending response")
                        send_response({"status": "resumed"}, request_id)
                    except StreamError as e:
                        LOGGER.debug("Resume failed with error: %s", e)
                        send_error(f"Resume failed: {e}", "RESUME_FAILED", request_id)

                elif action == "cancel":
                    LOGGER.debug("Cancel command received")
                    if not streaming_session or not streaming_session.is_alive():
                        send_error("Not currently streaming", "NOT_STREAMING", request_id)
                        continue

                    try:
                        LOGGER.debug("Requesting cancel (clean exit, stay connected)")
                        streaming_session.request_stop()

                        # Wait for worker thread to exit gracefully
                        if streaming_session.thread:
                            streaming_session.thread.join(timeout=2.0)

                        # CRITICAL: Reset pause flag so next stream can run
                        # Without this, streamer._paused stays True and blocks
                        if streamer:
                            LOGGER.debug("Resetting streamer pause flag")
                            streamer._paused = False

                        LOGGER.debug("Sending cancelled response")
                        send_response({"status": "cancelled"}, request_id)
                        streaming_session = None
                    except Exception as e:
                        LOGGER.debug("Cancel error: %s", e)
                        send_error(f"Cancel failed: {e}", "CANCEL_FAILED", request_id)
                        streaming_session = None

                elif action == "stop":
                    LOGGER.debug("Stop command received")
                    if streamer is None or not streamer.is_connected:
                        send_error("Not connected to Marlin", "NOT_CONNECTED", request_id)
                        continue

                    if not streaming_session or not streaming_session.is_alive():
                        send_error("Not currently streaming", "NOT_STREAMING", request_id)
                        continue

                    try:
                        LOGGER.debug("Requesting stop and sending M112")
                        streaming_session.request_stop()

                        # Send M112 emergency stop - it halts Marlin and closes connection
                        LOGGER.debug("Calling streamer.emergency_stop()")
                        streamer.emergency_stop()

                        LOGGER.debug("Sending stopped response")
                        send_response({"status": "stopped", "disconnected": True}, request_id)

                        if streaming_session.thread:
                            streaming_session.thread.join(timeout=1.0)
                        streaming_session = None
                    except Exception as e:
                        LOGGER.debug("Stop error: %s", e)
                        if streamer:
                            streamer.close()
                        send_response({"status": "stopped", "disconnected": True}, request_id)
                        streaming_session = None

                elif action == "exit":
                    if streaming_session and streaming_session.is_alive():
                        streaming_session.request_stop()
                        if streaming_session.thread:
                            streaming_session.thread.join(timeout=2.0)
                    if streamer is not None:
                        streamer.close()
                    send_response({"status": "exiting"}, request_id)
                    break

                else:
                    send_error(f"Unknown action: {action}", "UNKNOWN_ACTION", request_id)

            except Exception as e:
                req_id = command.get("requestId") if isinstance(command, dict) else None
                send_error(f"Unexpected error: {e}", "INTERNAL_ERROR", req_id)

    finally:
        if streaming_session and streaming_session.is_alive():
            streaming_session.request_stop()
            if streaming_session.thread:
                streaming_session.thread.join(timeout=2.0)
        if streamer is not None:
            streamer.close()


if __name__ == "__main__":
    interactive_mode()
