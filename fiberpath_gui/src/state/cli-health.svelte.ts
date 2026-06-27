import { invoke } from "@tauri-apps/api/core";
import { CliHealthResponseSchema } from "../lib/schemas";
import { isTauri } from "../lib/tauri";

export type CliStatus = "ready" | "checking" | "unavailable" | "unknown";

/** Shown when there is no Tauri backend to detect (browser dev preview). */
const BROWSER_PREVIEW_MESSAGE =
  "Browser preview — no backend. Run `npm run tauri dev` for the full app.";

/**
 * CLI/sidecar backend health (replaces useCliHealth + CliHealthContext).
 * Invokes the `check_cli_health` Tauri command and validates the response.
 */
export class CliHealth {
  status = $state<CliStatus>("unknown");
  version = $state<string | null>(null);
  errorMessage = $state<string | null>(null);
  lastChecked = $state<Date | null>(null);
  isBrowserPreview = $state(false);

  readonly isHealthy = $derived(this.status === "ready");
  readonly isUnavailable = $derived(this.status === "unavailable");

  #timer: ReturnType<typeof setInterval> | null = null;

  async refresh() {
    // No Tauri bridge (plain-browser dev preview): the backend can't be reached,
    // so surface it as an expected preview state instead of polling + failing.
    if (!isTauri()) {
      this.isBrowserPreview = true;
      this.status = "unavailable";
      this.version = null;
      this.errorMessage = BROWSER_PREVIEW_MESSAGE;
      this.lastChecked = new Date();
      return;
    }
    this.isBrowserPreview = false;
    this.status = "checking";
    try {
      const response = await invoke<unknown>("check_cli_health");
      const parsed = CliHealthResponseSchema.safeParse(response);
      if (!parsed.success) {
        throw new Error(`Invalid response schema: ${parsed.error.message}`);
      }
      this.status = parsed.data.healthy ? "ready" : "unavailable";
      this.version = parsed.data.version;
      this.errorMessage = parsed.data.errorMessage;
    } catch (e) {
      this.status = "unavailable";
      this.version = null;
      this.errorMessage =
        e instanceof Error ? e.message : typeof e === "string" ? e : "Unknown error occurred";
    } finally {
      this.lastChecked = new Date();
    }
  }

  /** Refresh now and then every `intervalMs`; returns an unsubscribe. */
  startPolling(intervalMs = 30000): () => void {
    void this.refresh();
    // Nothing to poll in a browser preview — the backend can't appear later.
    if (!isTauri()) return () => this.stopPolling();
    if (this.#timer === null) {
      this.#timer = setInterval(() => void this.refresh(), intervalMs);
    }
    return () => this.stopPolling();
  }

  stopPolling() {
    if (this.#timer !== null) {
      clearInterval(this.#timer);
      this.#timer = null;
    }
  }
}

export const cliHealth = new CliHealth();
