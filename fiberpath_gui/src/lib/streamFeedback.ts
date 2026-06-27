import { TOAST_DURATION_ERROR_MS } from "./constants";
import { toastMessages } from "./toastMessages";

// Structural types so this module stays framework-agnostic (no dependency on the
// state modules that consume it).
type LogType = "info" | "command" | "response" | "stream" | "progress" | "error";
type ToastType = "success" | "error" | "warning" | "info";
type AddLogEntry = (entry: { type: LogType; content: string }) => void;
type AddToast = (toast: { type: ToastType; message: string; duration?: number }) => void;

interface StreamFeedbackHandlers {
  addLogEntry: AddLogEntry;
  addToast: AddToast;
}

const logInfo = (addLogEntry: AddLogEntry, content: string) => {
  addLogEntry({ type: "info", content });
};

const logError = (addLogEntry: AddLogEntry, content: string) => {
  addLogEntry({ type: "error", content });
};

export function createStreamFeedback({
  addLogEntry,
  addToast,
}: StreamFeedbackHandlers) {
  return {
    connection: {
      noPortSelected() {
        logError(addLogEntry, "Please select a port");
        addToast({
          type: "error",
          message: toastMessages.connection.noPortSelected(),
        });
      },

      connecting(port: string, baudRate: number) {
        logInfo(addLogEntry, `Connecting to ${port} at ${baudRate} baud...`);
      },

      connected(port: string, baudRate: number) {
        logInfo(addLogEntry, `Connected to ${port} at ${baudRate} baud`);
        addToast({
          type: "success",
          message: toastMessages.connection.success(port),
        });
      },

      failed(errorMsg: string) {
        logError(addLogEntry, `Connection failed: ${errorMsg}`);
        addToast({
          type: "error",
          message: toastMessages.connection.failed(errorMsg),
          duration: TOAST_DURATION_ERROR_MS,
        });
      },

      disconnected() {
        logInfo(addLogEntry, "Disconnected");
        addToast({
          type: "info",
          message: toastMessages.connection.disconnected(),
        });
      },

      disconnectFailed(errorMsg: string) {
        logError(addLogEntry, `Disconnect failed: ${errorMsg}`);
        addToast({
          type: "error",
          message: `Disconnect failed: ${errorMsg}`,
        });
      },

      noPortsFound() {
        addToast({
          type: "warning",
          message: toastMessages.connection.noPortsFound(),
        });
      },

      listPortsFailed(errorMsg: string) {
        logError(addLogEntry, `Failed to list ports: ${errorMsg}`);
        addToast({
          type: "error",
          message: toastMessages.connection.listPortsFailed(errorMsg),
        });
      },
    },

    file: {
      selected(filename: string) {
        logInfo(addLogEntry, `File selected: ${filename}`);
        addToast({
          type: "info",
          message: toastMessages.file.selected(filename),
        });
      },

      selectionFailed(errorMsg: string) {
        logError(addLogEntry, `File selection failed: ${errorMsg}`);
        addToast({
          type: "error",
          message: toastMessages.file.selectionFailed(errorMsg),
          duration: TOAST_DURATION_ERROR_MS,
        });
      },

      cleared() {
        logInfo(addLogEntry, "File selection cleared");
        addToast({
          type: "info",
          message: "File selection cleared",
        });
      },
    },

    streaming: {
      startedToast() {
        addToast({
          type: "info",
          message: toastMessages.streaming.started(),
        });
      },

      startFailed(errorMsg: string) {
        logError(addLogEntry, `Failed to start streaming: ${errorMsg}`);
        addToast({
          type: "error",
          message: toastMessages.streaming.failed(errorMsg),
          duration: TOAST_DURATION_ERROR_MS,
        });
      },

      paused() {
        logInfo(addLogEntry, "Streaming paused (M0 sent)");
        addToast({
          type: "warning",
          message: toastMessages.streaming.paused(),
        });
      },

      pauseFailed(errorMsg: string) {
        logError(addLogEntry, `Pause failed: ${errorMsg}`);
        addToast({
          type: "error",
          message: toastMessages.streaming.pauseFailed(errorMsg),
        });
      },

      resumed() {
        logInfo(addLogEntry, "Streaming resumed (M108 sent)");
        addToast({
          type: "success",
          message: toastMessages.streaming.resumed(),
        });
      },

      resumeFailed(errorMsg: string) {
        logError(addLogEntry, `Resume failed: ${errorMsg}`);
        addToast({
          type: "error",
          message: toastMessages.streaming.resumeFailed(errorMsg),
        });
      },

      cancelled() {
        logInfo(addLogEntry, "Job cancelled - ready for new file");
        addToast({
          type: "info",
          message: "Job cancelled successfully. Connection maintained.",
        });
      },

      cancelFailed(errorMsg: string) {
        logError(addLogEntry, `Cancel failed: ${errorMsg}`);
        addToast({
          type: "error",
          message: `Failed to cancel: ${errorMsg}`,
          duration: TOAST_DURATION_ERROR_MS,
        });
      },

      stopped() {
        logError(
          addLogEntry,
          "Emergency stop (M112) sent - controller will disconnect",
        );
        addToast({
          type: "warning",
          message:
            "Emergency stop executed. Controller disconnected - reconnect to continue.",
          duration: TOAST_DURATION_ERROR_MS,
        });
      },

      stopFailed(errorMsg: string) {
        logError(addLogEntry, `Stop failed: ${errorMsg}`);
        addToast({
          type: "error",
          message: `Failed to stop: ${errorMsg}`,
          duration: TOAST_DURATION_ERROR_MS,
        });
      },

      startedEvent(file: string, totalCommands: number) {
        logInfo(
          addLogEntry,
          `Streaming started: ${file} (${totalCommands} commands)`,
        );
      },

      progressLog(sent: number, total: number, command: string) {
        addLogEntry({
          type: "stream",
          content: `[${sent}/${total}] ${command}`,
        });
      },

      progressMilestone(percentage: number) {
        addToast({
          type: "info",
          message: toastMessages.streaming.progress(percentage),
        });
      },

      complete(sent: number, total: number) {
        logInfo(
          addLogEntry,
          `Streaming complete: ${sent}/${total} commands sent`,
        );
        addToast({
          type: "success",
          message: toastMessages.streaming.complete(sent),
        });
      },

      error(message: string) {
        logError(addLogEntry, `Streaming error: ${message}`);
        addToast({
          type: "error",
          message: toastMessages.streaming.error(message),
          duration: TOAST_DURATION_ERROR_MS,
        });
      },
    },

    command: {
      issued(gcode: string) {
        addLogEntry({
          type: "command",
          content: gcode,
        });
      },

      response(response: string) {
        addLogEntry({
          type: "response",
          content: response,
        });
      },

      failed(errorMsg: string) {
        logError(addLogEntry, `Command failed: ${errorMsg}`);
        addToast({
          type: "error",
          message: toastMessages.command.failed(errorMsg),
        });
      },

      homingComplete() {
        addToast({
          type: "success",
          message: toastMessages.command.homingComplete(),
        });
      },

      emergencyStop() {
        addToast({
          type: "warning",
          message: toastMessages.command.emergencyStop(),
          duration: TOAST_DURATION_ERROR_MS,
        });
      },
    },
  };
}
