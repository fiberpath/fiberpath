import { describe, expect, it, vi, beforeEach } from "vitest";
import { createStreamFeedback } from "./streamFeedback";

function makeMocks() {
  const addLogEntry = vi.fn();
  const addToast = vi.fn();
  const feedback = createStreamFeedback({ addLogEntry, addToast });
  return { addLogEntry, addToast, feedback };
}

describe("createStreamFeedback", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("connection", () => {
    it("noPortSelected logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.connection.noPortSelected();
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("connecting logs info message with port and baud rate", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.connection.connecting("/dev/ttyUSB0", 250000);
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "info",
          content: expect.stringContaining("250000"),
        }),
      );
      expect(addToast).not.toHaveBeenCalled();
    });

    it("connected logs info and shows success toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.connection.connected("/dev/ttyUSB0", 250000);
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "success" }),
      );
    });

    it("failed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.connection.failed("timeout");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("disconnected logs info and shows info toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.connection.disconnected();
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
    });

    it("disconnectFailed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.connection.disconnectFailed("serial error");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("noPortsFound shows warning toast without logging", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.connection.noPortsFound();
      expect(addLogEntry).not.toHaveBeenCalled();
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "warning" }),
      );
    });

    it("listPortsFailed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.connection.listPortsFailed("access denied");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });
  });

  describe("file", () => {
    it("selected logs info and shows info toast with filename", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.file.selected("part.wind");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
    });

    it("selectionFailed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.file.selectionFailed("permission denied");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("cleared logs info and shows info toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.file.cleared();
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
    });
  });

  describe("streaming", () => {
    it("startedToast shows an info toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.startedToast();
      expect(addLogEntry).not.toHaveBeenCalled();
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
    });

    it("startFailed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.startFailed("device busy");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("paused logs info and shows warning toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.paused();
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "warning" }),
      );
    });

    it("pauseFailed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.pauseFailed("no response");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("resumed logs info and shows success toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.resumed();
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "success" }),
      );
    });

    it("resumeFailed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.resumeFailed("timeout");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("cancelled logs info and shows info toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.cancelled();
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
    });

    it("cancelFailed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.cancelFailed("port closed");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("stopped logs error and shows warning toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.stopped();
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "warning" }),
      );
    });

    it("stopFailed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.stopFailed("timeout");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("startedEvent logs info with file and command count", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.startedEvent("part.gcode", 150);
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({
          type: "info",
          content: expect.stringContaining("150"),
        }),
      );
      expect(addToast).not.toHaveBeenCalled();
    });

    it("progressLog adds a stream log entry", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.progressLog(10, 100, "G1 X10");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "stream" }),
      );
      expect(addToast).not.toHaveBeenCalled();
    });

    it("progressMilestone shows an info toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.progressMilestone(50);
      expect(addLogEntry).not.toHaveBeenCalled();
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
    });

    it("complete logs info and shows success toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.complete(100, 100);
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "info" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "success" }),
      );
    });

    it("error logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.streaming.error("checksum mismatch");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });
  });

  describe("command", () => {
    it("issued adds a command log entry", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.command.issued("G28");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "command", content: "G28" }),
      );
      expect(addToast).not.toHaveBeenCalled();
    });

    it("response adds a response log entry", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.command.response("ok");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "response", content: "ok" }),
      );
      expect(addToast).not.toHaveBeenCalled();
    });

    it("failed logs error and shows error toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.command.failed("unknown command");
      expect(addLogEntry).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "error" }),
      );
    });

    it("homingComplete shows success toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.command.homingComplete();
      expect(addLogEntry).not.toHaveBeenCalled();
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "success" }),
      );
    });

    it("emergencyStop shows warning toast", () => {
      const { addLogEntry, addToast, feedback } = makeMocks();
      feedback.command.emergencyStop();
      expect(addLogEntry).not.toHaveBeenCalled();
      expect(addToast).toHaveBeenCalledWith(
        expect.objectContaining({ type: "warning" }),
      );
    });
  });
});
