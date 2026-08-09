import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
  save: vi.fn(),
  ask: vi.fn(),
}));
vi.mock("../lib/commands", () => ({
  saveWindFile: vi.fn(() => Promise.resolve()),
  loadWindFile: vi.fn(),
  planWind: vi.fn(() => Promise.resolve({ output: "x", commands: 1 })),
}));
vi.mock("../lib/recentFiles", () => ({ addRecentFile: vi.fn() }));

import { open, save, ask } from "@tauri-apps/plugin-dialog";
import { saveWindFile, loadWindFile, planWind } from "../lib/commands";
import * as fileOps from "./file-operations.svelte";
import { projectSession } from "../state/project-session.svelte";
import { notifications } from "../state/notifications.svelte";
import { projectToWindDefinition } from "../types/converters";

const validWindJson = JSON.stringify(
  projectToWindDefinition({
    mandrel: { diameter: 200, wind_length: 600 },
    tow: { width: 10, thickness: 0.3 },
    layers: [],
    defaultFeedRate: 500,
  }),
);

beforeEach(() => {
  vi.clearAllMocks();
  projectSession.newDocument();
  notifications.clear();
});

describe("file-operations service", () => {
  it("saveProjectAs writes the .wind, sets path, and clears dirty", async () => {
    projectSession.updateMandrel({ diameter: 222 });
    expect(projectSession.isDirty).toBe(true);
    vi.mocked(save).mockResolvedValue("/p/out.wind");

    const ok = await fileOps.saveProjectAs();

    expect(ok).toBe(true);
    expect(saveWindFile).toHaveBeenCalledWith("/p/out.wind", expect.stringContaining("schemaVersion"));
    expect(projectSession.filePath).toBe("/p/out.wind");
    expect(projectSession.isDirty).toBe(false);
  });

  it("saveProject uses the existing path without a dialog", async () => {
    projectSession.filePath = "/existing.wind";
    const ok = await fileOps.saveProject();
    expect(ok).toBe(true);
    expect(save).not.toHaveBeenCalled();
    expect(saveWindFile).toHaveBeenCalledWith("/existing.wind", expect.any(String));
  });

  it("saveProject falls back to Save As when there is no path", async () => {
    vi.mocked(save).mockResolvedValue("/p/new.wind");
    await fileOps.saveProject();
    expect(save).toHaveBeenCalled();
    expect(saveWindFile).toHaveBeenCalledWith("/p/new.wind", expect.any(String));
  });

  it("openProject loads, validates, and replaces the document", async () => {
    vi.mocked(open).mockResolvedValue("/p/in.wind");
    vi.mocked(loadWindFile).mockResolvedValue(validWindJson);

    const ok = await fileOps.openProject();

    expect(ok).toBe(true);
    expect(projectSession.document.mandrel.diameter).toBe(200);
    expect(projectSession.document.defaultFeedRate).toBe(500);
    expect(projectSession.filePath).toBe("/p/in.wind");
    expect(projectSession.isDirty).toBe(false);
  });

  it("openProject loads a .wind with a Von Kármán mandrel profile (#345)", async () => {
    // A VK profile (schemaVersion 1.2) is now representable and round-trips; opening
    // it must load the profile, not block or silently strip it to a cylinder.
    const vkWind = JSON.stringify({
      schemaVersion: "1.2",
      mandrelParameters: { diameter: 98, windLength: 300, profile: { type: "vonKarman" } },
      towParameters: { width: 7, thickness: 0.5 },
      defaultFeedRate: 9000,
      layers: [],
    });
    vi.mocked(open).mockResolvedValue("/p/vk.wind");
    vi.mocked(loadWindFile).mockResolvedValue(vkWind);

    const ok = await fileOps.openProject();

    expect(ok).toBe(true);
    expect(projectSession.document.mandrel.diameter).toBe(98);
    expect(projectSession.document.mandrel.profile).toEqual({ type: "vonKarman" });
    expect(projectSession.filePath).toBe("/p/vk.wind");
  });

  it("openProject aborts when the user declines the unsaved-changes prompt", async () => {
    projectSession.updateMandrel({ diameter: 999 });
    vi.mocked(ask).mockResolvedValue(false);

    const ok = await fileOps.openProject();

    expect(ok).toBe(false);
    expect(open).not.toHaveBeenCalled();
    expect(projectSession.document.mandrel.diameter).toBe(999);
  });

  it("newProject resets only after the prompt is accepted", async () => {
    projectSession.updateMandrel({ diameter: 999 });
    vi.mocked(ask).mockResolvedValueOnce(false);
    expect(await fileOps.newProject()).toBe(false);
    expect(projectSession.document.mandrel.diameter).toBe(999);

    vi.mocked(ask).mockResolvedValueOnce(true);
    expect(await fileOps.newProject()).toBe(true);
    expect(projectSession.document.mandrel.diameter).toBe(150);
  });

  it("exportGcode plans the gcode and notifies", async () => {
    vi.mocked(save).mockResolvedValue("/p/out.gcode");
    const ok = await fileOps.exportGcode();
    expect(ok).toBe(true);
    expect(planWind).toHaveBeenCalledWith(expect.stringContaining("schemaVersion"), "/p/out.gcode");
    expect(notifications.toasts.some((t) => t.type === "info")).toBe(true);
  });

  it("surfaces a save failure as an error toast and leaves the doc dirty", async () => {
    projectSession.updateMandrel({ diameter: 123 });
    expect(projectSession.isDirty).toBe(true);
    vi.mocked(save).mockResolvedValue("/p/out.wind");
    vi.mocked(saveWindFile).mockRejectedValueOnce(new Error("disk full"));

    const ok = await fileOps.saveProjectAs();

    expect(ok).toBe(false);
    expect(notifications.toasts.some((t) => t.type === "error")).toBe(true);
    expect(projectSession.isDirty).toBe(true); // failed save must not clear dirty
  });

  it("returns false without writing when a dialog is cancelled", async () => {
    vi.mocked(save).mockResolvedValue(null);
    expect(await fileOps.saveProjectAs()).toBe(false);
    expect(saveWindFile).not.toHaveBeenCalled();
  });
});
