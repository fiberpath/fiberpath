import { open } from "@tauri-apps/plugin-dialog";
import * as marlin from "../lib/marlin-api";
import { createStreamFeedback } from "../lib/streamFeedback";
import { notifications } from "./notifications.svelte";
import {
  MAX_LOG_ENTRIES,
  DEFAULT_BAUD_RATE,
  PROGRESS_MILESTONE_PERCENTAGES,
  LOG_PROGRESS_EVERY_N_COMMANDS,
} from "../lib/constants";
import type { SerialPort } from "../lib/tauri-types";

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

/**
 * Reactive Marlin machine control — consolidates the Zustand streamStore + the
 * three React action hooks + useStreamEvents into one session. Reuses the
 * framework-agnostic `marlin-api` (Tauri bridge) and `streamFeedback` (log/toast
 * messages) unchanged.
 */
export class MachineSession {
  // Connection
  status = $state<ConnectionStatus>("disconnected");
  ports = $state<SerialPort[]>([]);
  selectedPort = $state<string | null>(null);
  baudRate = $state<number>(DEFAULT_BAUD_RATE);
  refreshing = $state(false);

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

  #resetAfterCancel() {
    this.isStreaming = false;
    this.status = "connected";
    this.progress = null;
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
      await marlin.startInteractive();
      await marlin.connectMarlin(this.selectedPort, this.baudRate);
      this.status = "connected";
      this.#feedback.connection.connected(this.selectedPort, this.baudRate);
      this.#clearStreamingState();
    } catch (e) {
      this.status = "disconnected";
      this.#feedback.connection.failed(String(e));
    }
  }

  async disconnect() {
    try {
      await marlin.disconnectMarlin();
      this.status = "disconnected";
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
      else if (gcode === "M112") this.#feedback.command.emergencyStop();
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
    if (!this.filePath || !this.isConnected) return;
    try {
      await marlin.streamFile(this.filePath);
      this.#feedback.streaming.startedToast();
    } catch (e) {
      this.#feedback.streaming.startFailed(String(e));
    }
  }

  async pause() {
    if (this.streamControlLoading) return;
    this.streamControlLoading = true;
    try {
      await marlin.pauseStream();
      this.status = "paused";
      this.#feedback.streaming.paused();
    } catch (e) {
      this.#feedback.streaming.pauseFailed(String(e));
    } finally {
      this.streamControlLoading = false;
    }
  }

  async resume() {
    if (this.streamControlLoading) return;
    this.streamControlLoading = true;
    try {
      await marlin.resumeStream();
      this.status = "connected";
      this.#feedback.streaming.resumed();
    } catch (e) {
      this.#feedback.streaming.resumeFailed(String(e));
    } finally {
      this.streamControlLoading = false;
    }
  }

  async cancel() {
    if (this.streamControlLoading) return;
    this.streamControlLoading = true;
    try {
      await marlin.cancelStream();
      this.#resetAfterCancel();
      this.#feedback.streaming.cancelled();
    } catch (e) {
      this.#feedback.streaming.cancelFailed(String(e));
      this.#resetAfterCancel();
    } finally {
      this.streamControlLoading = false;
    }
  }

  /** Emergency stop (M112) — disconnects the controller. Distinct from cancel. */
  async stop() {
    if (this.streamControlLoading) return;
    this.streamControlLoading = true;
    try {
      await marlin.stopStream();
      this.status = "disconnected";
      // The job is over and the controller is gone — clear streaming flags so the
      // UI can't keep offering Pause/Stop while disconnected (improves on React).
      this.isStreaming = false;
      this.progress = null;
      this.#feedback.streaming.stopped();
    } catch (e) {
      this.#feedback.streaming.stopFailed(String(e));
      this.status = "disconnected";
      this.isStreaming = false;
      this.progress = null;
    } finally {
      this.streamControlLoading = false;
    }
  }

  // --- Tauri stream-event subscription ----------------------------------
  /** Subscribe to stream lifecycle events; returns a cleanup that unlistens. */
  async subscribe(): Promise<() => void> {
    try {
      const unlisten = await Promise.all([
        marlin.onStreamStarted((s) => {
          this.isStreaming = true;
          this.#feedback.streaming.startedEvent(s.file, s.totalCommands);
        }),
        marlin.onStreamProgress((p) => {
          // Drop stale progress from a finished/cancelled job (#219 stale-event
          // guard — improves on React, which had no such guard).
          if (!this.isStreaming) return;
          this.progress = { sent: p.commandsSent, total: p.commandsTotal, currentCommand: p.command };
          if (
            p.commandsSent % LOG_PROGRESS_EVERY_N_COMMANDS === 0 ||
            p.commandsSent === p.commandsTotal
          ) {
            this.#feedback.streaming.progressLog(p.commandsSent, p.commandsTotal, p.command);
          }
          const pct = Math.round((p.commandsSent / p.commandsTotal) * 100);
          if (PROGRESS_MILESTONE_PERCENTAGES.includes(pct)) {
            this.#feedback.streaming.progressMilestone(pct);
          }
        }),
        marlin.onStreamComplete((c) => {
          this.#resetAfterCancel();
          this.#feedback.streaming.complete(c.commandsSent, c.commandsTotal);
        }),
        marlin.onStreamError((e) => {
          this.#resetAfterCancel();
          this.#feedback.streaming.error(e.message);
        }),
      ]);
      return () => unlisten.forEach((u) => u());
    } catch {
      // No Tauri runtime (e.g. browser preview) — nothing to clean up.
      return () => {};
    }
  }
}

export const machineSession = new MachineSession();
