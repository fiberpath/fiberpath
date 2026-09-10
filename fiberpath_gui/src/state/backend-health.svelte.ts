import { invoke } from "@tauri-apps/api/core";
import { BROWSER_PREVIEW_MESSAGE, isTauri } from "../lib/tauri";

/**
 * Shape of the `check_backend_health` Tauri command response. Served over the
 * Tauri bridge rather than the OpenAPI surface, so it has no generated type.
 */
interface BackendHealthResponse {
  healthy: boolean;
  version: string | null;
  errorMessage: string | null;
}

function isBackendHealthResponse(v: unknown): v is BackendHealthResponse {
  if (typeof v !== "object" || v === null) return false;
  const r = v as Record<string, unknown>;
  return (
    typeof r.healthy === "boolean" &&
    (typeof r.version === "string" || r.version === null) &&
    (typeof r.errorMessage === "string" || r.errorMessage === null)
  );
}

export type BackendStatus = "ready" | "checking" | "unavailable" | "unknown";

/**
 * Backend health: probes the bundled CLI/sidecar via the `check_backend_health`
 * Tauri command and validates the response.
 */
export class BackendHealth {
  status = $state<BackendStatus>("unknown");
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
      const response = await invoke<unknown>("check_backend_health");
      if (!isBackendHealthResponse(response)) {
        throw new Error(
          `Invalid response schema: ${JSON.stringify(response)?.slice(0, 200)}`,
        );
      }
      this.status = response.healthy ? "ready" : "unavailable";
      this.version = response.version;
      this.errorMessage = response.errorMessage;
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

export const backendHealth = new BackendHealth();
