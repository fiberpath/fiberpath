/**
 * Runtime detection for the Tauri webview.
 *
 * The GUI bootstraps its backend through Tauri: the Rust shell spawns the API
 * sidecar and reports its URL via `invoke("api_base_url")`. In a plain browser
 * (`npm run dev` at :5173) that bridge is absent, so backend features cannot
 * work. Use this to treat the backend-less browser state as an expected dev
 * preview rather than a failure. The full backed dev loop is `npm run tauri dev`.
 */
export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}
