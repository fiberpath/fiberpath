import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("../lib/commands", () => ({ plotDefinition: vi.fn() }));
vi.mock("../lib/validation", () => ({
  validateWindDefinition: vi.fn(() => ({ valid: true, errors: [] })),
}));

import { plotDefinition } from "../lib/commands";
import { validateWindDefinition } from "../lib/validation";
import { PreviewSession } from "./preview-session.svelte";
import { projectSession } from "./project-session.svelte";
import { notifications } from "./notifications.svelte";

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(validateWindDefinition).mockReturnValue({ valid: true, errors: [] });
  projectSession.newDocument();
  notifications.clear();
});

describe("PreviewSession", () => {
  it("refuses to generate with no layers", async () => {
    const ps = new PreviewSession();
    await ps.generate();
    expect(ps.error).toBe("No layers to visualize");
    expect(plotDefinition).not.toHaveBeenCalled();
  });

  it("reports invalid mandrel parameters", async () => {
    projectSession.addLayer("helical");
    projectSession.updateMandrel({ diameter: 0 });
    const ps = new PreviewSession();
    await ps.generate();
    expect(ps.error).toBe("Invalid mandrel parameters");
  });

  it("generates a preview image on success", async () => {
    projectSession.addLayer("helical");
    vi.mocked(plotDefinition).mockResolvedValue({
      imageBase64: "QUJD",
      warnings: ["heads up"],
      path: "",
    });

    const ps = new PreviewSession();
    await ps.generate();

    expect(plotDefinition).toHaveBeenCalledOnce();
    expect(ps.image).toBe("data:image/png;base64,QUJD");
    expect(ps.warnings).toEqual(["heads up"]);
    expect(ps.isGenerating).toBe(false);
    expect(ps.error).toBeNull();
  });

  it("surfaces a plot failure as error state + toast", async () => {
    projectSession.addLayer("helical");
    vi.mocked(plotDefinition).mockRejectedValue(new Error("backend down"));

    const ps = new PreviewSession();
    await ps.generate();

    expect(ps.error).toBe("backend down");
    expect(ps.image).toBeNull();
    expect(notifications.toasts.some((t) => t.type === "error")).toBe(true);
  });

  it("rejects empty image data", async () => {
    projectSession.addLayer("helical");
    vi.mocked(plotDefinition).mockResolvedValue({ imageBase64: "", warnings: [], path: "" });

    const ps = new PreviewSession();
    await ps.generate();
    expect(ps.error).toBe("Empty image data returned from plot command");
  });

  it("drops a superseded (stale) response", async () => {
    projectSession.addLayer("helical");
    const ps = new PreviewSession();

    // First request stays pending; we resolve it AFTER a newer one finishes.
    let resolveStale!: (v: { imageBase64: string; warnings: string[]; path: string }) => void;
    vi.mocked(plotDefinition).mockImplementationOnce(
      () => new Promise((r) => (resolveStale = r)),
    );
    const stale = ps.generate(); // request 1 (pending)

    // Newer request supersedes and completes immediately.
    vi.mocked(plotDefinition).mockResolvedValueOnce({ imageBase64: "TkVX", warnings: [], path: "" });
    await ps.generate(); // request 2 wins
    expect(ps.image).toBe("data:image/png;base64,TkVX");

    // The stale request now resolves with old data — it must NOT overwrite.
    resolveStale({ imageBase64: "T0xE", warnings: ["stale"], path: "" });
    await stale;

    expect(ps.image).toBe("data:image/png;base64,TkVX");
    expect(ps.warnings).toEqual([]);
    expect(ps.isGenerating).toBe(false);
  });

  it("fails on schema validation errors before calling the API", async () => {
    projectSession.addLayer("helical");
    vi.mocked(validateWindDefinition).mockReturnValue({
      valid: false,
      errors: [{ field: "windAngle", message: "out of range" }],
    });

    const ps = new PreviewSession();
    await ps.generate();
    expect(ps.error).toContain("Schema validation failed");
    expect(plotDefinition).not.toHaveBeenCalled();
  });
});
