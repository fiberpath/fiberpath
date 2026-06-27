import { invoke } from "@tauri-apps/api/core";

import { getApiClient } from "./apiClient";
import { withRetry } from "./retry";
import { CommandError, ValidationError } from "./schemas";

/** Result of an export plan: the file written and how many commands it holds. */
export interface PlanSummary {
  output: string;
  commands: number;
}

/** Rendered preview payload returned to the canvas. */
export interface PlotPreviewPayload {
  imageBase64: string;
  warnings: string[];
  path: string;
}

/** Outcome of validating a wind definition. */
export interface ValidationResult {
  valid: boolean;
  errors?: { field: string; message: string }[];
}

/** Map an API error body (400 `{detail}` string, or 422 pydantic list) to UI errors. */
function mapApiErrors(body: unknown): { field: string; message: string }[] {
  const detail = (body as { detail?: unknown } | undefined)?.detail;
  if (typeof detail === "string") {
    return [{ field: "", message: detail }];
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      const loc = Array.isArray(item?.loc) ? item.loc.slice(1) : [];
      return { field: loc.join("."), message: String(item?.msg ?? "Invalid value") };
    });
  }
  return [{ field: "validation", message: "Unknown validation error" }];
}

function bytesToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

/**
 * Plan a wind definition into G-code and write it to `outputPath`.
 * The backend no longer writes files, so the gcode comes back in the response
 * and we persist it through the file-system bridge.
 */
export const planWind = withRetry(
  async (definitionJson: string, outputPath: string): Promise<PlanSummary> => {
    const client = await getApiClient();
    let response;
    try {
      response = await client.POST("/plan", { body: JSON.parse(definitionJson) });
    } catch (error) {
      throw new CommandError("Failed to plan wind definition", "plan", error);
    }
    if (response.error || !response.data) {
      throw new CommandError("Failed to plan wind definition", "plan", response.error);
    }
    await saveWindFile(outputPath, response.data.gcode);
    return { output: outputPath, commands: response.data.commandCount };
  },
  { maxAttempts: 2 },
);

/**
 * Plot an in-memory wind definition: plan it to G-code, then render a preview.
 * `visibleLayerCount` is already applied by the caller (it slices layers before
 * stringifying), so it is not sent separately.
 */
export const plotDefinition = withRetry(
  async (
    definitionJson: string,
    _visibleLayerCount: number,
    _outputPath?: string,
  ): Promise<PlotPreviewPayload> => {
    const client = await getApiClient();
    try {
      const plan = await client.POST("/plan", { body: JSON.parse(definitionJson) });
      if (plan.error || !plan.data) {
        throw new CommandError("Failed to plan definition", "plan", plan.error);
      }
      const plot = await client.POST("/plot", {
        body: { gcode: plan.data.gcode },
        parseAs: "arrayBuffer",
      });
      if (plot.error || !plot.data) {
        throw new CommandError("Failed to render preview", "plot", plot.error);
      }
      return {
        imageBase64: bytesToBase64(plot.data as ArrayBuffer),
        // The API exposes no structured planner warnings yet; the preview shows none.
        warnings: [],
        path: "",
      };
    } catch (error) {
      if (error instanceof CommandError) throw error;
      throw new CommandError("Failed to plot definition", "plot", error);
    }
  },
);

/**
 * Validate an in-memory wind definition. A semantic/schema failure is a normal
 * outcome (returned as `{valid: false, errors}`), not a thrown command error.
 */
export const validateWindDefinition = withRetry(
  async (definitionJson: string): Promise<ValidationResult> => {
    const client = await getApiClient();
    let response;
    try {
      response = await client.POST("/validate", { body: JSON.parse(definitionJson) });
    } catch (error) {
      throw new CommandError("Failed to validate wind definition", "validate", error);
    }
    if (response.data) {
      // 200: the API returns {valid: true}; honour the field defensively in case
      // it ever reports an invalid-but-200 result rather than only via 4xx.
      return { valid: response.data.valid };
    }
    if (response.response.status === 400 || response.response.status === 422) {
      return { valid: false, errors: mapApiErrors(response.error) };
    }
    throw new CommandError(
      "Failed to validate wind definition",
      "validate",
      response.error ?? response.response.statusText,
    );
  },
  { maxAttempts: 2 },
);

/**
 * Saves file content to disk through the Tauri file-system bridge (native).
 */
export const saveWindFile = withRetry(
  async (path: string, content: string): Promise<void> => {
    try {
      await invoke("save_wind_file", { path, content });
    } catch (error) {
      throw new CommandError("Failed to save wind file", "save_wind_file", error);
    }
  },
);

/**
 * Loads file content from disk through the Tauri file-system bridge (native).
 */
export const loadWindFile = withRetry(async (path: string): Promise<string> => {
  try {
    const result = await invoke<string>("load_wind_file", { path });
    if (typeof result !== "string") {
      throw new ValidationError("Expected string content from load_wind_file");
    }
    return result;
  } catch (error) {
    throw new CommandError("Failed to load wind file", "load_wind_file", error);
  }
});
