/**
 * Lazily start the local API sidecar and hand back a typed client.
 *
 * The Rust shell spawns/supervises the sidecar and reports its base URL via the
 * `api_base_url` command; we poll `GET /health` until it is ready, then build an
 * `openapi-fetch` client (generated types in `../api`). The client is memoised;
 * a failed start resets the memo so the next call retries.
 */

import { createApiClient, type ApiClient } from "../api/client";
import { invokeBackend } from "./tauri";

let clientPromise: Promise<ApiClient> | null = null;

async function waitForHealth(baseUrl: string, timeoutMs = 30_000): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) return;
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error(`API sidecar did not become healthy: ${String(lastError)}`);
}

async function start(): Promise<ApiClient> {
  const baseUrl = await invokeBackend<string>("api_base_url");
  await waitForHealth(baseUrl);
  return createApiClient(baseUrl);
}

/** Get the typed API client, starting + health-checking the sidecar on first use. */
export function getApiClient(): Promise<ApiClient> {
  if (!clientPromise) {
    clientPromise = start().catch((error) => {
      clientPromise = null; // allow a later retry after a failed start
      throw error;
    });
  }
  return clientPromise;
}
