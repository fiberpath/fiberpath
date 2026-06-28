import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

vi.mock("../lib/marlin-api", () => ({
  listSerialPorts: vi.fn(() => Promise.resolve([])),
  connectMarlin: vi.fn(() =>
    Promise.resolve({
      state: "connected",
      port: "/dev/ttyUSB0",
      baud_rate: 250000,
      firmware: "Marlin 2.1.2",
      capabilities: { EEPROM: true, AUTOLEVEL: false },
    }),
  ),
  disconnectMarlin: vi.fn(() => Promise.resolve()),
  sendCommand: vi.fn(() => Promise.resolve([])),
  startJob: vi.fn(() => Promise.resolve({ job_id: "job-1", total: 100 })),
  getJob: vi.fn(() =>
    Promise.resolve({ id: "job-1", state: "streaming", sent: 0, total: 100, cursor: 0, events: [] }),
  ),
  pauseJob: vi.fn(() => Promise.resolve({ id: "job-1", state: "paused", cursor: 0, events: [] })),
  resumeJob: vi.fn(() => Promise.resolve({ id: "job-1", state: "streaming", cursor: 0, events: [] })),
  cancelJob: vi.fn(() => Promise.resolve({ id: "job-1", state: "cancelled", cursor: 0, events: [] })),
  emergencyStop: vi.fn(() => Promise.resolve()),
}));
vi.mock("../lib/commands", () => ({
  loadWindFile: vi.fn(() => Promise.resolve("G1 X0\nG1 X1")),
}));
vi.mock("@tauri-apps/plugin-dialog", () => ({ open: vi.fn() }));

import * as marlin from "../lib/marlin-api";
import { loadWindFile } from "../lib/commands";
import { open } from "@tauri-apps/plugin-dialog";
import { MachineSession } from "./machine-session.svelte";
import { notifications } from "./notifications.svelte";
import { MAX_LOG_ENTRIES } from "../lib/constants";

// Matches POLL_INTERVAL_MS in machine-session; advance a bit past it.
const POLL_TICK = 300;

let m: MachineSession;
beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  notifications.clear();
  m = new MachineSession();
});
afterEach(() => {
  vi.clearAllTimers();
  vi.useRealTimers();
});

/** Put the session into a live streaming job (poll loop scheduled but not yet fired). */
async function startStreaming() {
  m.status = "connected";
  m.filePath = "/x.gcode";
  m.selectedFile = "x.gcode";
  await m.startStream();
}

describe("MachineSession — connection", () => {
  it("refreshPorts loads ports and auto-selects the first", async () => {
    vi.mocked(marlin.listSerialPorts).mockResolvedValue([
      { port: "/dev/ttyUSB0", description: "Arduino", hwid: "x" },
      { port: "/dev/ttyUSB1", description: "Other", hwid: "y" },
    ]);
    await m.refreshPorts();
    expect(m.ports).toHaveLength(2);
    expect(m.selectedPort).toBe("/dev/ttyUSB0");
    expect(m.refreshing).toBe(false);
  });

  it("connect requires a selected port", async () => {
    await m.connect();
    expect(marlin.connectMarlin).not.toHaveBeenCalled();
    expect(m.status).toBe("disconnected");
  });

  it("connect transitions to connected and stores firmware/capabilities", async () => {
    m.selectedPort = "/dev/ttyUSB0";
    await m.connect();
    expect(marlin.connectMarlin).toHaveBeenCalledWith("/dev/ttyUSB0", 250000);
    expect(m.status).toBe("connected");
    expect(m.firmware).toBe("Marlin 2.1.2");
    expect(m.capabilities).toEqual({ EEPROM: true, AUTOLEVEL: false });
  });

  it("connect falls back to disconnected on failure", async () => {
    m.selectedPort = "/dev/ttyUSB0";
    vi.mocked(marlin.connectMarlin).mockRejectedValueOnce(new Error("no device"));
    await m.connect();
    expect(m.status).toBe("disconnected");
    expect(m.firmware).toBeNull();
  });

  it("disconnect returns to disconnected and clears firmware + streaming", async () => {
    m.status = "connected";
    m.firmware = "Marlin";
    m.selectedFile = "a.gcode";
    await m.disconnect();
    expect(m.status).toBe("disconnected");
    expect(m.firmware).toBeNull();
    expect(m.selectedFile).toBeNull();
  });
});

describe("MachineSession — manual control", () => {
  it("ignores commands when disconnected", async () => {
    await m.sendCommand("G28");
    expect(marlin.sendCommand).not.toHaveBeenCalled();
  });

  it("sends a command when connected and logs the response", async () => {
    m.status = "connected";
    vi.mocked(marlin.sendCommand).mockResolvedValue(["ok"]);
    await m.sendCommand("M114");
    expect(marlin.sendCommand).toHaveBeenCalledWith("M114");
    expect(m.log.some((e) => e.type === "command" && e.content === "M114")).toBe(true);
    expect(m.log.some((e) => e.type === "response" && e.content === "ok")).toBe(true);
  });

  it("manualSend clears the input after sending", async () => {
    m.status = "connected";
    m.commandInput = "G0 X10";
    await m.manualSend();
    expect(marlin.sendCommand).toHaveBeenCalledWith("G0 X10");
    expect(m.commandInput).toBe("");
  });

  it("gates manual controls while streaming unless paused", () => {
    m.status = "connected";
    m.isStreaming = true;
    expect(m.manualControlsEnabled).toBe(false);
    m.status = "paused";
    expect(m.manualControlsEnabled).toBe(true);
  });
});

describe("MachineSession — streaming lifecycle", () => {
  it("startStream requires a file and a connection", async () => {
    await m.startStream();
    expect(marlin.startJob).not.toHaveBeenCalled();
  });

  it("startStream reads the file off disk and starts a job", async () => {
    await startStreaming();
    expect(loadWindFile).toHaveBeenCalledWith("/x.gcode");
    expect(marlin.startJob).toHaveBeenCalledWith("G1 X0\nG1 X1");
    expect(m.isStreaming).toBe(true);
    expect(m.progress).toEqual({ sent: 0, total: 100, currentCommand: "" });
  });

  it("pause moves to paused", async () => {
    await startStreaming();
    await m.pause();
    expect(marlin.pauseJob).toHaveBeenCalledWith("job-1");
    expect(m.status).toBe("paused");
  });

  it("resume moves back to connected", async () => {
    await startStreaming();
    await m.pause();
    await m.resume();
    expect(marlin.resumeJob).toHaveBeenCalledWith("job-1");
    expect(m.status).toBe("connected");
  });

  it("cancel keeps the connection and clears the job", async () => {
    await startStreaming();
    await m.cancel();
    expect(marlin.cancelJob).toHaveBeenCalledWith("job-1");
    expect(m.status).toBe("connected");
    expect(m.isStreaming).toBe(false);
    expect(m.progress).toBeNull();
  });

  it("emergency stop disconnects and ends the job — distinct from cancel", async () => {
    await startStreaming();
    await m.emergencyStop();
    expect(marlin.emergencyStop).toHaveBeenCalled();
    expect(m.status).toBe("disconnected");
    expect(m.isStreaming).toBe(false);
    expect(m.progress).toBeNull();
    expect(m.firmware).toBeNull();
  });

  it("stop() is an alias for emergencyStop()", async () => {
    await startStreaming();
    await m.stop();
    expect(marlin.emergencyStop).toHaveBeenCalled();
    expect(m.status).toBe("disconnected");
  });

  it("all control actions are ignored while one is in flight", async () => {
    await startStreaming();
    m.streamControlLoading = true;
    await m.pause();
    await m.resume();
    await m.cancel();
    await m.emergencyStop();
    expect(marlin.pauseJob).not.toHaveBeenCalled();
    expect(marlin.resumeJob).not.toHaveBeenCalled();
    expect(marlin.cancelJob).not.toHaveBeenCalled();
    expect(marlin.emergencyStop).not.toHaveBeenCalled();
  });
});

describe("MachineSession — poll loop", () => {
  it("folds progress events into the bar, throttles the stream log, fires milestones", async () => {
    await startStreaming();
    notifications.clear();
    // 25% is a milestone; 25 % 10 != 0 so it is NOT stream-logged.
    vi.mocked(marlin.getJob).mockResolvedValueOnce({
      id: "job-1",
      state: "streaming",
      sent: 25,
      total: 100,
      cursor: 4,
      events: [{ seq: 1, type: "progress", sent: 25, total: 100, command: "G1 X1" }],
    } as never);
    await vi.advanceTimersByTimeAsync(POLL_TICK);
    expect(m.progress).toEqual({ sent: 25, total: 100, currentCommand: "G1 X1" });
    expect(notifications.toasts.some((t) => t.type === "info")).toBe(true);
    expect(m.log.some((e) => e.type === "stream")).toBe(false);

    // 30 % 10 == 0 -> stream-logged.
    vi.mocked(marlin.getJob).mockResolvedValueOnce({
      id: "job-1",
      state: "streaming",
      sent: 30,
      total: 100,
      cursor: 6,
      events: [{ seq: 2, type: "progress", sent: 30, total: 100, command: "G1 X2" }],
    } as never);
    await vi.advanceTimersByTimeAsync(POLL_TICK);
    expect(m.log.some((e) => e.type === "stream")).toBe(true);
  });

  it("a terminal complete state ends the job with a success toast", async () => {
    await startStreaming();
    vi.mocked(marlin.getJob).mockResolvedValueOnce({
      id: "job-1",
      state: "completed",
      sent: 100,
      total: 100,
      cursor: 2,
      events: [{ seq: 1, type: "complete", sent: 100, total: 100 }],
    } as never);
    await vi.advanceTimersByTimeAsync(POLL_TICK);
    expect(m.isStreaming).toBe(false);
    expect(m.progress).toBeNull();
    expect(m.status).toBe("connected");
    expect(notifications.toasts.some((t) => t.type === "success")).toBe(true);
  });

  it("an error event/state ends the job and surfaces an error toast", async () => {
    await startStreaming();
    vi.mocked(marlin.getJob).mockResolvedValueOnce({
      id: "job-1",
      state: "error",
      sent: 5,
      total: 100,
      cursor: 2,
      error: "board exploded",
      events: [{ seq: 1, type: "error", message: "board exploded" }],
    } as never);
    await vi.advanceTimersByTimeAsync(POLL_TICK);
    expect(m.isStreaming).toBe(false);
    expect(m.status).toBe("connected");
    expect(m.progress).toBeNull();
    expect(notifications.toasts.some((t) => t.type === "error")).toBe(true);
  });

  it("stops polling once the job is terminal (no stale fetches)", async () => {
    await startStreaming();
    vi.mocked(marlin.getJob).mockResolvedValueOnce({
      id: "job-1",
      state: "completed",
      sent: 100,
      total: 100,
      cursor: 1,
      events: [{ seq: 1, type: "complete", sent: 100, total: 100 }],
    } as never);
    await vi.advanceTimersByTimeAsync(POLL_TICK);
    const callsAfterComplete = vi.mocked(marlin.getJob).mock.calls.length;
    await vi.advanceTimersByTimeAsync(POLL_TICK * 4);
    expect(vi.mocked(marlin.getJob).mock.calls.length).toBe(callsAfterComplete);
  });

  it("reflects a remote pause in the status display", async () => {
    await startStreaming();
    vi.mocked(marlin.getJob).mockResolvedValueOnce({
      id: "job-1",
      state: "paused",
      sent: 10,
      total: 100,
      cursor: 1,
      events: [{ seq: 1, type: "action", action: "pause", message: "paused at line 10" }],
    } as never);
    await vi.advanceTimersByTimeAsync(POLL_TICK);
    expect(m.status).toBe("paused");
    expect(m.log.some((e) => e.content === "paused at line 10")).toBe(true);
  });
});

describe("MachineSession — robustness", () => {
  it("pushes a toast on a successful connect (feedback adapter wired)", async () => {
    m.selectedPort = "/dev/ttyUSB0";
    await m.connect();
    expect(notifications.toasts.some((t) => t.type === "success")).toBe(true);
  });

  it("caps the log at MAX_LOG_ENTRIES", async () => {
    m.status = "connected";
    const many = Array.from({ length: MAX_LOG_ENTRIES + 50 }, (_, i) => `ok ${i}`);
    vi.mocked(marlin.sendCommand).mockResolvedValue(many);
    await m.sendCommand("M114");
    expect(m.log.length).toBe(MAX_LOG_ENTRIES);
  });

  it("selectFile records the path and basename", async () => {
    vi.mocked(open).mockResolvedValue("/home/cam/job.gcode");
    await m.selectFile();
    expect(m.filePath).toBe("/home/cam/job.gcode");
    expect(m.selectedFile).toBe("job.gcode");
  });
});
