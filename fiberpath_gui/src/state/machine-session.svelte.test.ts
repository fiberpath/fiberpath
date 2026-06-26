import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("../lib/marlin-api", () => ({
  listSerialPorts: vi.fn(() => Promise.resolve([])),
  startInteractive: vi.fn(() => Promise.resolve()),
  connectMarlin: vi.fn(() => Promise.resolve()),
  disconnectMarlin: vi.fn(() => Promise.resolve()),
  sendCommand: vi.fn(() => Promise.resolve([])),
  streamFile: vi.fn(() => Promise.resolve()),
  pauseStream: vi.fn(() => Promise.resolve()),
  resumeStream: vi.fn(() => Promise.resolve()),
  cancelStream: vi.fn(() => Promise.resolve()),
  stopStream: vi.fn(() => Promise.resolve()),
  onStreamStarted: vi.fn(() => Promise.resolve(() => {})),
  onStreamProgress: vi.fn(() => Promise.resolve(() => {})),
  onStreamComplete: vi.fn(() => Promise.resolve(() => {})),
  onStreamError: vi.fn(() => Promise.resolve(() => {})),
}));
vi.mock("@tauri-apps/plugin-dialog", () => ({ open: vi.fn() }));

import * as marlin from "../lib/marlin-api";
import { open } from "@tauri-apps/plugin-dialog";
import { MachineSession } from "./machine-session.svelte";
import { notifications } from "./notifications.svelte";
import { MAX_LOG_ENTRIES } from "../lib/constants";

let m: MachineSession;
beforeEach(() => {
  vi.clearAllMocks();
  notifications.clear();
  m = new MachineSession();
});

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

  it("connect transitions to connected on success", async () => {
    m.selectedPort = "/dev/ttyUSB0";
    await m.connect();
    expect(marlin.startInteractive).toHaveBeenCalled();
    expect(marlin.connectMarlin).toHaveBeenCalledWith("/dev/ttyUSB0", 250000);
    expect(m.status).toBe("connected");
  });

  it("connect falls back to disconnected on failure", async () => {
    m.selectedPort = "/dev/ttyUSB0";
    vi.mocked(marlin.connectMarlin).mockRejectedValueOnce(new Error("no device"));
    await m.connect();
    expect(m.status).toBe("disconnected");
  });

  it("disconnect returns to disconnected and clears streaming", async () => {
    m.status = "connected";
    m.selectedFile = "a.gcode";
    await m.disconnect();
    expect(m.status).toBe("disconnected");
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
  beforeEach(() => {
    m.status = "connected";
    m.isStreaming = true;
  });

  it("pause moves to paused", async () => {
    await m.pause();
    expect(marlin.pauseStream).toHaveBeenCalled();
    expect(m.status).toBe("paused");
  });

  it("resume moves back to connected", async () => {
    m.status = "paused";
    await m.resume();
    expect(m.status).toBe("connected");
  });

  it("cancel keeps the connection and clears the job", async () => {
    await m.cancel();
    expect(marlin.cancelStream).toHaveBeenCalled();
    expect(m.status).toBe("connected");
    expect(m.isStreaming).toBe(false);
    expect(m.progress).toBeNull();
  });

  it("stop (emergency) disconnects and ends the job — distinct from cancel", async () => {
    await m.stop();
    expect(marlin.stopStream).toHaveBeenCalled();
    expect(m.status).toBe("disconnected");
    expect(m.isStreaming).toBe(false);
    expect(m.progress).toBeNull();
  });

  it("all control actions are ignored while one is in flight", async () => {
    m.streamControlLoading = true;
    await m.pause();
    await m.resume();
    await m.cancel();
    await m.stop();
    expect(marlin.pauseStream).not.toHaveBeenCalled();
    expect(marlin.resumeStream).not.toHaveBeenCalled();
    expect(marlin.cancelStream).not.toHaveBeenCalled();
    expect(marlin.stopStream).not.toHaveBeenCalled();
  });

  it("a failed cancel still resets to connected; a failed stop still disconnects", async () => {
    vi.mocked(marlin.cancelStream).mockRejectedValueOnce(new Error("x"));
    await m.cancel();
    expect(m.status).toBe("connected");
    expect(m.isStreaming).toBe(false);

    m.status = "connected";
    m.isStreaming = true;
    vi.mocked(marlin.stopStream).mockRejectedValueOnce(new Error("x"));
    await m.stop();
    expect(m.status).toBe("disconnected");
    expect(m.isStreaming).toBe(false);
  });
});

describe("MachineSession — feedback, events & robustness (epic scenarios)", () => {
  function wireEvents() {
    const cbs: Record<string, (arg: never) => void> = {};
    const unlisten = { started: vi.fn(), progress: vi.fn(), complete: vi.fn(), error: vi.fn() };
    vi.mocked(marlin.onStreamStarted).mockImplementation((cb) => {
      cbs.started = cb as never;
      return Promise.resolve(unlisten.started);
    });
    vi.mocked(marlin.onStreamProgress).mockImplementation((cb) => {
      cbs.progress = cb as never;
      return Promise.resolve(unlisten.progress);
    });
    vi.mocked(marlin.onStreamComplete).mockImplementation((cb) => {
      cbs.complete = cb as never;
      return Promise.resolve(unlisten.complete);
    });
    vi.mocked(marlin.onStreamError).mockImplementation((cb) => {
      cbs.error = cb as never;
      return Promise.resolve(unlisten.error);
    });
    return { cbs, unlisten };
  }

  it("pushes a toast on a successful connect (feedback adapter wired)", async () => {
    m.selectedPort = "/dev/ttyUSB0";
    await m.connect();
    expect(notifications.toasts.some((t) => t.type === "success")).toBe(true);
  });

  it("fires a milestone toast at 25/50/75% and throttles the stream log", async () => {
    const { cbs } = wireEvents();
    await m.subscribe();
    cbs.started({ file: "j", totalCommands: 100 } as never);

    notifications.clear();
    // 25% is a milestone; 25 % 10 != 0 so it is NOT stream-logged
    cbs.progress({ commandsSent: 25, commandsTotal: 100, command: "g", dryRun: false } as never);
    expect(notifications.toasts.some((t) => t.type === "info")).toBe(true);
    expect(m.log.some((e) => e.type === "stream")).toBe(false);

    // 30 % 10 == 0 -> stream-logged
    cbs.progress({ commandsSent: 30, commandsTotal: 100, command: "g", dryRun: false } as never);
    expect(m.log.some((e) => e.type === "stream")).toBe(true);
  });

  it("the error event resets state and logs an error", async () => {
    const { cbs } = wireEvents();
    await m.subscribe();
    cbs.started({ file: "j", totalCommands: 100 } as never);
    expect(m.isStreaming).toBe(true);

    cbs.error({ code: "E", message: "board exploded" } as never);
    expect(m.isStreaming).toBe(false);
    expect(m.status).toBe("connected");
    expect(m.progress).toBeNull();
    expect(notifications.toasts.some((t) => t.type === "error")).toBe(true);
  });

  it("drops stale progress from a finished job", async () => {
    const { cbs } = wireEvents();
    await m.subscribe();
    cbs.started({ file: "j", totalCommands: 100 } as never);
    cbs.complete({ commandsSent: 100, commandsTotal: 100 } as never);
    expect(m.progress).toBeNull();

    // a late progress event from the finished job must NOT revive the bar
    cbs.progress({ commandsSent: 50, commandsTotal: 100, command: "g", dryRun: false } as never);
    expect(m.progress).toBeNull();
  });

  it("cleanup unlistens every stream event", async () => {
    const { unlisten } = wireEvents();
    const cleanup = await m.subscribe();
    cleanup();
    expect(unlisten.started).toHaveBeenCalled();
    expect(unlisten.progress).toHaveBeenCalled();
    expect(unlisten.complete).toHaveBeenCalled();
    expect(unlisten.error).toHaveBeenCalled();
  });

  it("caps the log at MAX_LOG_ENTRIES", async () => {
    m.status = "connected";
    const many = Array.from({ length: MAX_LOG_ENTRIES + 50 }, (_, i) => `ok ${i}`);
    vi.mocked(marlin.sendCommand).mockResolvedValue(many);
    await m.sendCommand("M114");
    expect(m.log.length).toBe(MAX_LOG_ENTRIES);
  });
});

describe("MachineSession — files & events", () => {
  it("selectFile records the path and basename", async () => {
    vi.mocked(open).mockResolvedValue("/home/cam/job.gcode");
    await m.selectFile();
    expect(m.filePath).toBe("/home/cam/job.gcode");
    expect(m.selectedFile).toBe("job.gcode");
  });

  it("startStream requires a file and a connection", async () => {
    await m.startStream();
    expect(marlin.streamFile).not.toHaveBeenCalled();
    m.status = "connected";
    m.filePath = "/x.gcode";
    await m.startStream();
    expect(marlin.streamFile).toHaveBeenCalledWith("/x.gcode");
  });

  it("subscribe wires stream events into state", async () => {
    let started!: (s: { file: string; totalCommands: number }) => void;
    let progress!: (p: { commandsSent: number; commandsTotal: number; command: string; dryRun: boolean }) => void;
    let complete!: (c: { commandsSent: number; commandsTotal: number }) => void;
    vi.mocked(marlin.onStreamStarted).mockImplementation((cb) => {
      started = cb;
      return Promise.resolve(() => {});
    });
    vi.mocked(marlin.onStreamProgress).mockImplementation((cb) => {
      progress = cb;
      return Promise.resolve(() => {});
    });
    vi.mocked(marlin.onStreamComplete).mockImplementation((cb) => {
      complete = cb;
      return Promise.resolve(() => {});
    });

    const cleanup = await m.subscribe();

    started({ file: "j.gcode", totalCommands: 100 });
    expect(m.isStreaming).toBe(true);

    progress({ commandsSent: 50, commandsTotal: 100, command: "G1 X1", dryRun: false });
    expect(m.progress).toEqual({ sent: 50, total: 100, currentCommand: "G1 X1" });

    complete({ commandsSent: 100, commandsTotal: 100 });
    expect(m.isStreaming).toBe(false);
    expect(m.progress).toBeNull();

    expect(typeof cleanup).toBe("function");
  });
});
