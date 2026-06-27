import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

import { invoke } from "@tauri-apps/api/core";
import { CliHealth } from "./cli-health.svelte";

// Simulate the Tauri webview so refresh() takes the real backend path.
beforeEach(() => {
  vi.clearAllMocks();
  (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
});
afterEach(() => {
  delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
});

describe("CliHealth", () => {
  it("reports ready on a healthy response", async () => {
    vi.mocked(invoke).mockResolvedValue({ healthy: true, version: "0.7.4", errorMessage: null });
    const h = new CliHealth();
    await h.refresh();
    expect(h.status).toBe("ready");
    expect(h.isHealthy).toBe(true);
    expect(h.version).toBe("0.7.4");
    expect(h.lastChecked).toBeInstanceOf(Date);
  });

  it("reports unavailable on a healthy:false response", async () => {
    vi.mocked(invoke).mockResolvedValue({ healthy: false, version: null, errorMessage: "no cli" });
    const h = new CliHealth();
    await h.refresh();
    expect(h.status).toBe("unavailable");
    expect(h.isUnavailable).toBe(true);
    expect(h.errorMessage).toBe("no cli");
  });

  it("reports unavailable when the command throws", async () => {
    vi.mocked(invoke).mockRejectedValue(new Error("not found"));
    const h = new CliHealth();
    await h.refresh();
    expect(h.status).toBe("unavailable");
    expect(h.errorMessage).toBe("not found");
    expect(h.version).toBeNull();
  });

  it("reports unavailable when the response fails schema validation", async () => {
    vi.mocked(invoke).mockResolvedValue({ unexpected: true });
    const h = new CliHealth();
    await h.refresh();
    expect(h.status).toBe("unavailable");
    expect(h.errorMessage).toContain("Invalid response schema");
  });

  it("reports a browser preview (no invoke) when there is no Tauri runtime", async () => {
    delete (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__;
    const h = new CliHealth();
    await h.refresh();
    expect(h.isBrowserPreview).toBe(true);
    expect(h.status).toBe("unavailable");
    expect(h.errorMessage).toContain("tauri dev");
    expect(invoke).not.toHaveBeenCalled();
  });
});
