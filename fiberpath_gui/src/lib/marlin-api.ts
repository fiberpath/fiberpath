/**
 * Tauri commands for Marlin integration
 *
 * This module provides typed wrappers around the Tauri commands
 * for interacting with Marlin controllers via serial connection.
 */

import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { invokeBackend } from "./tauri";
import type {
  SerialPort,
  StreamProgress,
  StreamComplete,
  StreamError,
  StreamStarted,
} from "./tauri-types";

/**
 * List available serial ports
 */
export async function listSerialPorts(): Promise<SerialPort[]> {
  return await invokeBackend<SerialPort[]>("marlin_list_ports");
}

/**
 * Start the interactive Python subprocess
 */
export async function startInteractive(): Promise<void> {
  await invokeBackend("marlin_start_interactive");
}

/**
 * Connect to a Marlin controller
 */
export async function connectMarlin(
  port: string,
  baudRate: number = 250000,
): Promise<void> {
  await invokeBackend("marlin_connect", { port, baudRate });
}

/**
 * Disconnect from the Marlin controller
 */
export async function disconnectMarlin(): Promise<void> {
  await invokeBackend("marlin_disconnect");
}

/**
 * Send a single G-code command to the Marlin controller
 */
export async function sendCommand(gcode: string): Promise<string[]> {
  try {
    const result = await invokeBackend<string[]>("marlin_send_command", { gcode });
    return result;
  } catch (error) {
    console.error("Command failed:", error);
    throw error;
  }
}

/**
 * Stream a G-code file to the Marlin controller
 */
export async function streamFile(filePath: string): Promise<void> {
  await invokeBackend("marlin_stream_file", { filePath });
}

/**
 * Pause streaming (sends M0)
 */
export async function pauseStream(): Promise<void> {
  await invokeBackend("marlin_pause");
}

/**
 * Resume streaming (sends M108)
 */
export async function resumeStream(): Promise<void> {
  await invokeBackend("marlin_resume");
}

/**
 * Cancel streaming (clean exit, stays connected)
 */
export async function cancelStream(): Promise<void> {
  await invokeBackend("marlin_cancel");
}

/**
 * Stop streaming (sends M112 emergency stop)
 */
export async function stopStream(): Promise<void> {
  await invokeBackend("marlin_stop");
}

/**
 * Listen for streaming started events
 */
export async function onStreamStarted(
  callback: (started: StreamStarted) => void,
): Promise<UnlistenFn> {
  return await listen<StreamStarted>("stream-started", (event) => {
    callback(event.payload);
  });
}

/**
 * Listen for streaming progress events
 */
export async function onStreamProgress(
  callback: (progress: StreamProgress) => void,
): Promise<UnlistenFn> {
  return await listen<StreamProgress>("stream-progress", (event) => {
    callback(event.payload);
  });
}

/**
 * Listen for streaming complete events
 */
export async function onStreamComplete(
  callback: (complete: StreamComplete) => void,
): Promise<UnlistenFn> {
  return await listen<StreamComplete>("stream-complete", (event) => {
    callback(event.payload);
  });
}

/**
 * Listen for streaming error events
 */
export async function onStreamError(
  callback: (error: StreamError) => void,
): Promise<UnlistenFn> {
  return await listen<StreamError>("stream-error", (event) => {
    callback(event.payload);
  });
}
