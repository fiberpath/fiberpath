/**
 * Typed client for the FiberPath local API sidecar.
 *
 * Types in `./schema` are generated from `fiberpath_gui/openapi.json` (itself
 * exported from the FastAPI app) — do not edit them by hand. A CI drift gate
 * regenerates both and fails if they diverge from the live API.
 */

import createClient, { type Client } from "openapi-fetch";

import type { paths } from "./schema";

export type ApiClient = Client<paths>;

/** Create a typed client bound to the given sidecar base URL. */
export function createApiClient(baseUrl: string): ApiClient {
  return createClient<paths>({ baseUrl });
}

export type { paths };
