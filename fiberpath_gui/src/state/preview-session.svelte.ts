import { plotDefinition } from "../lib/commands";
import { projectToWindDefinition } from "../types/converters";
import { validateWindDefinition } from "../lib/validation";
import { projectSession } from "./project-session.svelte";
import { notifications } from "./notifications.svelte";
import type { ProjectDocument } from "../types/document";

function validateInputs(doc: ProjectDocument): string | null {
  if (doc.layers.length === 0) return "No layers to visualize";
  if (!(doc.mandrel.diameter > 0) || !(doc.mandrel.wind_length > 0)) {
    return "Invalid mandrel parameters";
  }
  if (!(doc.tow.width > 0) || !(doc.tow.thickness > 0)) {
    return "Invalid tow parameters";
  }
  return null;
}

/**
 * Reactive preview generation (replaces usePreviewGeneration): plans the visible
 * layers to G-code via the API, renders a PNG, and tracks loading/error/warnings.
 * Stale responses are dropped via a monotonic request id.
 */
export class PreviewSession {
  image = $state<string | null>(null);
  isGenerating = $state(false);
  error = $state<string | null>(null);
  warnings = $state<string[]>([]);
  /** How many layers (from the top) the preview includes; the scrubber drives it. */
  visibleLayerCount = $state(0);

  #requestId = 0;

  async generate() {
    const doc = projectSession.document;
    const inputError = validateInputs(doc);
    if (inputError) {
      this.error = inputError;
      return;
    }

    const requestId = ++this.#requestId;
    this.isGenerating = true;
    this.error = null;
    this.warnings = [];

    try {
      const windDef = projectToWindDefinition(doc, this.visibleLayerCount);
      const validation = validateWindDefinition(windDef);
      if (!validation.valid) {
        const detail = validation.errors
          .map((e) => `${e.field}: ${e.message}`)
          .join(", ");
        throw new Error(`Schema validation failed: ${detail}`);
      }

      const result = await plotDefinition(JSON.stringify(windDef), this.visibleLayerCount);
      if (requestId !== this.#requestId) return; // superseded

      if (result.warnings && result.warnings.length > 0) {
        this.warnings = result.warnings;
      }
      if (!result.imageBase64) {
        throw new Error("Empty image data returned from plot command");
      }
      this.image = `data:image/png;base64,${result.imageBase64}`;
    } catch (err) {
      if (requestId !== this.#requestId) return;
      const message = err instanceof Error ? err.message : String(err);
      this.error = message;
      notifications.error(`Failed to generate preview: ${message}`);
    } finally {
      if (requestId === this.#requestId) this.isGenerating = false;
    }
  }

  /** Drop the current preview and cancel any in-flight request (new project / tests). */
  reset() {
    this.#requestId++;
    this.image = null;
    this.error = null;
    this.warnings = [];
    this.isGenerating = false;
  }
}

export const previewSession = new PreviewSession();
