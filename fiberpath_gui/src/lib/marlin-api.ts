/**
 * Marlin machine control via the local HTTP API sidecar.
 *
 * These wrappers mirror `commands.ts`: they grab the typed `getApiClient()`,
 * call a `/machine/*` endpoint, and map an error body / missing payload to a
 * `CommandError`. The old Tauri stdio-subprocess bridge (interactive process,
 * `stream-*` events) is gone — streaming progress now comes from polling
 * `getJob()`.
 */

import { getApiClient } from "./apiClient";
import { CommandError } from "./schemas";
import { DEFAULT_BAUD_RATE } from "./constants";
import type { components } from "../api/schema";

export type SerialPort = components["schemas"]["PortInfoOut"];
export type ConnectionInfo = components["schemas"]["ConnectionInfoOut"];
export type JobStatus = components["schemas"]["JobStatusOut"];
export type JobEvent = components["schemas"]["JobEventOut"];
export type StartJobResult = components["schemas"]["StartJobResponse"];

/** Enumerate the serial ports available on the host. */
export async function listSerialPorts(): Promise<SerialPort[]> {
  const client = await getApiClient();
  const { data, error } = await client.GET("/machine/ports", {});
  if (error || !data) {
    throw new CommandError("Failed to list serial ports", "machine/ports", error);
  }
  return data;
}

/**
 * Open a serial connection to a Marlin controller. Returns the connection info
 * (state, firmware, capabilities) for the connection-info panel (#146).
 */
export async function connectMarlin(
  port: string,
  baudRate: number = DEFAULT_BAUD_RATE,
): Promise<ConnectionInfo> {
  const client = await getApiClient();
  const response = await client.POST("/machine/connection", {
    body: { port, baud_rate: baudRate, timeout: 10 },
  });
  if (response.error || !response.data) {
    throw new CommandError("Failed to connect to controller", "machine/connection", response.error);
  }
  return response.data;
}

/** Close the active serial connection (204 on success). */
export async function disconnectMarlin(): Promise<void> {
  const client = await getApiClient();
  const { error } = await client.DELETE("/machine/connection", {});
  if (error) {
    throw new CommandError("Failed to disconnect", "machine/connection", error);
  }
}

/** Run a single G-code command synchronously and return the controller replies. */
export async function sendCommand(gcode: string): Promise<string[]> {
  const client = await getApiClient();
  const response = await client.POST("/machine/commands", { body: { gcode } });
  if (response.error || !response.data) {
    throw new CommandError("Failed to send command", "machine/commands", response.error);
  }
  return response.data.responses;
}

/** Start streaming a G-code program; returns the job id and total command count. */
export async function startJob(gcode: string): Promise<StartJobResult> {
  const client = await getApiClient();
  const response = await client.POST("/machine/jobs", { body: { gcode } });
  if (response.error || !response.data) {
    throw new CommandError("Failed to start job", "machine/jobs", response.error);
  }
  return response.data;
}

/**
 * Fetch a job's status plus the events logged since `since` (its event cursor).
 * Advance `since` to the returned `cursor` between polls so each event is seen
 * exactly once.
 */
export async function getJob(jobId: string, since: number = 0): Promise<JobStatus> {
  const client = await getApiClient();
  const response = await client.GET("/machine/jobs/{job_id}", {
    params: { path: { job_id: jobId }, query: { since } },
  });
  if (response.error || !response.data) {
    throw new CommandError("Failed to fetch job status", "machine/jobs/get", response.error);
  }
  return response.data;
}

/** Pause a running job. Returns the updated status. */
export async function pauseJob(jobId: string): Promise<JobStatus> {
  const client = await getApiClient();
  const response = await client.POST("/machine/jobs/{job_id}/pause", {
    params: { path: { job_id: jobId } },
  });
  if (response.error || !response.data) {
    throw new CommandError("Failed to pause job", "machine/jobs/pause", response.error);
  }
  return response.data;
}

/** Resume a paused job. Returns the updated status. */
export async function resumeJob(jobId: string): Promise<JobStatus> {
  const client = await getApiClient();
  const response = await client.POST("/machine/jobs/{job_id}/resume", {
    params: { path: { job_id: jobId } },
  });
  if (response.error || !response.data) {
    throw new CommandError("Failed to resume job", "machine/jobs/resume", response.error);
  }
  return response.data;
}

/** Cancel a running/paused job (stays connected). Returns the updated status. */
export async function cancelJob(jobId: string): Promise<JobStatus> {
  const client = await getApiClient();
  const response = await client.POST("/machine/jobs/{job_id}/cancel", {
    params: { path: { job_id: jobId } },
  });
  if (response.error || !response.data) {
    throw new CommandError("Failed to cancel job", "machine/jobs/cancel", response.error);
  }
  return response.data;
}

/** Emergency stop (M112) — halts the controller; the connection is dropped (204). */
export async function emergencyStop(): Promise<void> {
  const client = await getApiClient();
  const { error } = await client.POST("/machine/estop", {});
  if (error) {
    throw new CommandError("Failed to emergency stop", "machine/estop", error);
  }
}
