/**
 * Runtime detection for the Tauri webview.
 *
 * The GUI bootstraps its backend through Tauri: the Rust shell spawns the API
 * sidecar and reports its URL via `invoke("api_base_url")`. In a plain browser
 * (`npm run dev` at :5173) that bridge is absent, so backend features cannot
 * work. Use this to treat the backend-less browser state as an expected dev
 * preview rather than a failure. The full backed dev loop is `npm run tauri dev`.
 */
import { invoke } from "@tauri-apps/api/core";

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

/** Shown when a backend feature is used in the backend-less browser preview. */
export const BROWSER_PREVIEW_MESSAGE =
  "Browser preview — no backend. Run `npm run tauri dev` for the full app.";

/**
 * Invoke a Tauri command, but in the browser preview reject with a clear,
 * actionable message instead of letting `invoke` throw a raw
 * "Cannot read properties of undefined (reading 'invoke')" TypeError. Every
 * backend call (compute sidecar, serial bridge, file bridge) routes through
 * here so the preview degrades gracefully rather than leaking internals.
 */
export function invokeBackend<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  if (!isTauri()) return Promise.reject(new Error(BROWSER_PREVIEW_MESSAGE));
  // Forward args only when present so the call signature matches a bare invoke(cmd).
  return args === undefined ? invoke<T>(cmd) : invoke<T>(cmd, args);
}
