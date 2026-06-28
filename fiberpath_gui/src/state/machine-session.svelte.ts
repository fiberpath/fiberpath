import { open } from "@tauri-apps/plugin-dialog";
import * as marlin from "../lib/marlin-api";
import type { SerialPort, JobStatus } from "../lib/marlin-api";
import { loadWindFile } from "../lib/commands";
import { createStreamFeedback } from "../lib/streamFeedback";
import { notifications } from "./notifications.svelte";
import {
  MAX_LOG_ENTRIES,
  DEFAULT_BAUD_RATE,
  PROGRESS_MILESTONE_PERCENTAGES,
  LOG_PROGRESS_EVERY_N_COMMANDS,
} from "../lib/constants";

export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "paused";

export interface LogEntry {
  id: string;
  type: "info" | "command" | "response" | "stream" | "progress" | "error";
  content: string;
  timestamp: number;
}

export interface StreamProgress {
  sent: number;
  total: number;
  currentCommand: string;
}

/** How often the streaming poll loop fetches job status. */
const POLL_INTERVAL_MS = 250;

/** Job states that end the poll loop (terminal). */
function isTerminalJobState(state: string): boolean {
  return (
    state === "completed" ||
    state === "cancelled" ||
    state === "error" ||
    state === "disconnected"
  );
}

/**
 * Reactive Marlin machine control. Talks to the local HTTP API sidecar through
 * `marlin-api` (typed client) and reuses `streamFeedback` for log/toast copy.
 * Streaming progress is polled from `getJob()` rather than pushed over Tauri
 * events.
 */
export class MachineSession {
  // Connection
  status = $state<ConnectionStatus>("disconnected");
  ports = $state<SerialPort[]>([]);
  selectedPort = $state<string | null>(null);
  baudRate = $state<number>(DEFAULT_BAUD_RATE);
  refreshing = $state(false);

  // Connected controller info (#146 connection panel)
  firmware = $state<string | null>(null);
  capabilities = $state<Record<string, boolean>>({});

  // Streaming
  isStreaming = $state(false);
  filePath = $state<string | null>(null); // full path for streaming
  selectedFile = $state<string | null>(null); // basename for display
  progress = $state<StreamProgress | null>(null);
  streamControlLoading = $state(false);

  // Manual control
  commandInput = $state("");
  commandLoading = $state(false);

  // Log
  log = $state<LogEntry[]>([]);
  autoScroll = $state(true);

  #logId = 0;
  #feedback = createStreamFeedback({
    addLogEntry: (e) => this.#addLog(e.type, e.content),
    addToast: (t) => notifications.push(t.type, t.message, t.duration),
  });

  // Active job + poll loop bookkeeping
  #jobId: string | null = null;
  #since = 0;
  #pollTimer: ReturnType<typeof setTimeout> | null = null;

  readonly isConnected = $derived(this.status === "connected" || this.status === "paused");
  readonly isPaused = $derived(this.status === "paused");
  readonly manualControlsEnabled = $derived(
    this.isConnected && (!this.isStreaming || this.status === "paused"),
  );
  readonly canStartStream = $derived(Boolean(this.filePath) && this.isConnected);

  #addLog(type: LogEntry["type"], content: string) {
    this.log.push({ id: `log-${this.#logId++}`, type, content, timestamp: Date.now() });
    if (this.log.length > MAX_LOG_ENTRIES) {
      this.log = this.log.slice(-MAX_LOG_ENTRIES);
    }
  }

  #clearStreamingState() {
    this.selectedFile = null;
    this.filePath = null;
    this.progress = null;
    this.isStreaming = false;
  }

  /** Tear down the active job + poll loop. `disconnected` is true after an e-stop. */
  #endJob(opts?: { disconnected?: boolean }) {
    if (this.#pollTimer) {
      clearTimeout(this.#pollTimer);
      this.#pollTimer = null;
    }
    this.#jobId = null;
    this.#since = 0;
    this.isStreaming = false;
    this.progress = null;
    this.status = opts?.disconnected ? "disconnected" : "connected";
  }

  clearLog() {
    this.log = [];
  }
  toggleAutoScroll() {
    this.autoScroll = !this.autoScroll;
  }

  // --- Connection -------------------------------------------------------
  async refreshPorts() {
    this.refreshing = true;
    try {
      const ports = await marlin.listSerialPorts();
      this.ports = ports;
      if (!this.selectedPort && ports.length > 0) this.selectedPort = ports[0].port;
      if (ports.length === 0) this.#feedback.connection.noPortsFound();
    } catch (e) {
      this.#feedback.connection.listPortsFailed(String(e));
    } finally {
      this.refreshing = false;
    }
  }

  async connect() {
    if (!this.selectedPort) {
      this.#feedback.connection.noPortSelected();
      return;
    }
    this.status = "connecting";
    this.#feedback.connection.connecting(this.selectedPort, this.baudRate);
    try {
      const info = await marlin.connectMarlin(this.selectedPort, this.baudRate);
      this.status = "connected";
      this.firmware = info.firmware || null;
      this.capabilities = info.capabilities ?? {};
      this.#feedback.connection.connected(this.selectedPort, this.baudRate);
      this.#clearStreamingState();
    } catch (e) {
      this.status = "disconnected";
      this.firmware = null;
      this.capabilities = {};
      this.#feedback.connection.failed(String(e));
    }
  }

  async disconnect() {
    try {
      await marlin.disconnectMarlin();
      this.status = "disconnected";
      this.firmware = null;
      this.capabilities = {};
      this.#endJob({ disconnected: true });
      this.#clearStreamingState();
      this.#feedback.connection.disconnected();
    } catch (e) {
      this.#feedback.connection.disconnectFailed(String(e));
    }
  }

  // --- Manual control ---------------------------------------------------
  async sendCommand(gcode: string) {
    if (!gcode.trim() || !this.isConnected || this.commandLoading) return;
    this.commandLoading = true;
    this.#feedback.command.issued(gcode);
    try {
      const responses = await marlin.sendCommand(gcode);
      responses.forEach((r) => this.#feedback.command.response(r));
      if (gcode === "G28") this.#feedback.command.homingComplete();
    } catch (e) {
      this.#feedback.command.failed(String(e));
    } finally {
      this.commandLoading = false;
    }
  }

  async manualSend() {
    const command = this.commandInput.trim();
    if (!command) return;
    await this.sendCommand(command);
    this.commandInput = "";
  }

  // --- File streaming ---------------------------------------------------
  async selectFile() {
    try {
      const selected = await open({
        multiple: false,
        filters: [{ name: "G-code", extensions: ["gcode", "nc", "ngc"] }],
      });
      if (typeof selected !== "string") return;
      this.filePath = selected;
      const filename = selected.split(/[\\/]/).pop() || selected;
      this.selectedFile = filename;
      this.#feedback.file.selected(filename);
    } catch (e) {
      this.#feedback.file.selectionFailed(String(e));
    }
  }

  clearFile() {
    this.filePath = null;
    this.selectedFile = null;
    this.progress = null;
    this.#feedback.file.cleared();
  }

  async startStream() {
    if (!this.filePath || !this.isConnected || this.isStreaming) return;
    let gcode: string;
    try {
      // Read the selected program off disk via the same fs bridge as wind files,
      // then hand the G-code text to the API (the sidecar owns no file access).
      gcode = await loadWindFile(this.filePath);
    } catch (e) {
      this.#feedback.streaming.startFailed(String(e));
      return;
    }
    try {
      const { job_id, total } = await marlin.startJob(gcode);
      this.#jobId = job_id;
      this.#since = 0;
      this.isStreaming = true;
      this.status = "connected";
      this.progress = { sent: 0, total, currentCommand: "" };
      this.#feedback.streaming.startedToast();
      this.#feedback.streaming.startedEvent(this.selectedFile ?? this.filePath, total);
      this.#schedulePoll();
    } catch (e) {
      this.#feedback.streaming.startFailed(String(e));
    }
  }

  // --- Poll loop --------------------------------------------------------
  #schedulePoll() {
    this.#pollTimer = setTimeout(() => void this.#poll(), POLL_INTERVAL_MS);
  }

  /**
   * One poll tick: fetch new job events since the cursor, fold them into UI
   * state, then either end the job (terminal state) or schedule the next tick.
   */
  async #poll() {
    const jobId = this.#jobId;
    if (!jobId) return;
    let status: JobStatus;
    try {
      status = await marlin.getJob(jobId, this.#since);
    } catch (e) {
      if (this.#jobId !== jobId) return; // job already ended elsewhere
      this.#feedback.streaming.error(String(e));
      this.#endJob();
      return;
    }
    if (this.#jobId !== jobId) return; // ended while the request was in flight
    this.#since = status.cursor;
    this.#applyJobEvents(status);

    if (isTerminalJobState(status.state)) {
      this.#endJob();
      return;
    }
    // Reflect remote pause/resume in the connection status display.
    this.status = status.state === "paused" ? "paused" : "connected";
    this.#schedulePoll();
  }

  /** Fold a status payload's new events into the log / progress / toasts. */
  #applyJobEvents(status: JobStatus) {
    for (const ev of status.events) {
      switch (ev.type) {
        case "progress": {
          const sent = ev.sent ?? 0;
          const total = ev.total ?? this.progress?.total ?? 0;
          this.progress = { sent, total, currentCommand: ev.command ?? "" };
          if (total > 0 && (sent % LOG_PROGRESS_EVERY_N_COMMANDS === 0 || sent === total)) {
            this.#feedback.streaming.progressLog(sent, total, ev.command ?? "");
          }
          if (total > 0) {
            const pct = Math.round((sent / total) * 100);
            if (PROGRESS_MILESTONE_PERCENTAGES.includes(pct)) {
              this.#feedback.streaming.progressMilestone(pct);
            }
          }
          break;
        }
        case "action":
          this.#addLog("info", ev.message ?? ev.action ?? "Action");
          break;
        case "complete":
          this.#feedback.streaming.complete(
            ev.sent ?? this.progress?.sent ?? 0,
            ev.total ?? this.progress?.total ?? 0,
          );
          break;
        case "error":
          this.#feedback.streaming.error(ev.message ?? "Streaming error");
          break;
      }
    }
  }

  // --- Stream controls --------------------------------------------------
  async pause() {
    if (this.streamControlLoading || !this.#jobId) return;
    this.streamControlLoading = true;
    try {
      await marlin.pauseJob(this.#jobId);
      this.status = "paused";
      this.#feedback.streaming.paused();
    } catch (e) {
      this.#feedback.streaming.pauseFailed(String(e));
    } finally {
      this.streamControlLoading = false;
    }
  }

  async resume() {
    if (this.streamControlLoading || !this.#jobId) return;
    this.streamControlLoading = true;
    try {
      await marlin.resumeJob(this.#jobId);
      this.status = "connected";
      this.#feedback.streaming.resumed();
    } catch (e) {
      this.#feedback.streaming.resumeFailed(String(e));
    } finally {
      this.streamControlLoading = false;
    }
  }

  async cancel() {
    if (this.streamControlLoading || !this.#jobId) return;
    this.streamControlLoading = true;
    try {
      await marlin.cancelJob(this.#jobId);
      this.#endJob();
      this.#feedback.streaming.cancelled();
    } catch (e) {
      this.#feedback.streaming.cancelFailed(String(e));
      this.#endJob();
    } finally {
      this.streamControlLoading = false;
    }
  }

  /** Emergency stop (M112) — halts the controller and drops the connection. */
  async emergencyStop() {
    if (this.streamControlLoading) return;
    this.streamControlLoading = true;
    try {
      await marlin.emergencyStop();
      // M112 halts the board (recovery needs a reset). Close the sidecar
      // connection too, so a later reconnect — which DTR-resets and recovers
      // the board — isn't refused as "already connected". Best-effort.
      try {
        await marlin.disconnectMarlin();
      } catch {
        /* the connection may already be gone; ignore */
      }
      this.#endJob({ disconnected: true });
      this.firmware = null;
      this.capabilities = {};
      this.#feedback.streaming.stopped();
    } catch (e) {
      this.#feedback.streaming.stopFailed(String(e));
      this.#endJob({ disconnected: true });
      this.firmware = null;
      this.capabilities = {};
    } finally {
      this.streamControlLoading = false;
    }
  }

  /** Alias kept for the streaming "Stop" control. */
  async stop() {
    await this.emergencyStop();
  }
}

export const machineSession = new MachineSession();
