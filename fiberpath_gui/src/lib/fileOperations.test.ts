import { beforeEach, describe, expect, it, vi } from "vitest";
import { open, save, ask } from "@tauri-apps/plugin-dialog";
import * as commands from "./commands";
import * as recentFilesModule from "./recentFiles";
import { createFileOperations } from "./fileOperations";
import { createEmptyProject } from "../types/project";
import type { FiberPathProject } from "../types/project";

vi.mock("@tauri-apps/plugin-dialog", () => ({
  open: vi.fn(),
  save: vi.fn(),
  ask: vi.fn(),
}));

vi.mock("./commands", () => ({
  saveWindFile: vi.fn(),
  loadWindFile: vi.fn(),
  planWind: vi.fn(),
  validateWindDefinition: vi.fn(),
}));

vi.mock("./recentFiles", () => ({
  addRecentFile: vi.fn(),
  getRecentFiles: vi.fn().mockReturnValue([]),
}));

const mockOpen = vi.mocked(open);
const mockSave = vi.mocked(save);
const mockAsk = vi.mocked(ask);
const mockSaveWindFile = vi.mocked(commands.saveWindFile);
const mockLoadWindFile = vi.mocked(commands.loadWindFile);
const mockPlanWind = vi.mocked(commands.planWind);
const mockValidateWindDefinition = vi.mocked(commands.validateWindDefinition);
const mockAddRecentFile = vi.mocked(recentFilesModule.addRecentFile);

function makeCallbacks(overrides: Partial<Parameters<typeof createFileOperations>[0]> = {}) {
  const project = createEmptyProject();
  return {
    getProject: vi.fn<() => FiberPathProject>().mockReturnValue(project),
    newProject: vi.fn(),
    loadProject: vi.fn(),
    setFilePath: vi.fn(),
    clearDirty: vi.fn(),
    getActiveLayerId: vi.fn<() => string | null>().mockReturnValue(null),
    duplicateLayer: vi.fn(),
    removeLayer: vi.fn(),
    updateRecentFiles: vi.fn(),
    showError: vi.fn(),
    showInfo: vi.fn(),
    setValidationErrors: vi.fn(),
    clearValidationErrors: vi.fn(),
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("fileOperations", () => {
  describe("handleNewProject()", () => {
    it("creates a new project when not dirty", async () => {
      const callbacks = makeCallbacks();
      const ops = createFileOperations(callbacks);
      const result = await ops.handleNewProject();
      expect(result).toBe(true);
      expect(callbacks.newProject).toHaveBeenCalled();
    });

    it("asks for confirmation when dirty and proceeds on confirm", async () => {
      const dirtyProject = { ...createEmptyProject(), isDirty: true };
      const callbacks = makeCallbacks({
        getProject: vi.fn().mockReturnValue(dirtyProject),
      });
      mockAsk.mockResolvedValue(true);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleNewProject();
      expect(mockAsk).toHaveBeenCalled();
      expect(result).toBe(true);
      expect(callbacks.newProject).toHaveBeenCalled();
    });

    it("aborts when dirty and user declines", async () => {
      const dirtyProject = { ...createEmptyProject(), isDirty: true };
      const callbacks = makeCallbacks({
        getProject: vi.fn().mockReturnValue(dirtyProject),
      });
      mockAsk.mockResolvedValue(false);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleNewProject();
      expect(result).toBe(false);
      expect(callbacks.newProject).not.toHaveBeenCalled();
    });
  });

  describe("handleSave()", () => {
    it("saves to existing filePath without dialog", async () => {
      const projectWithPath = {
        ...createEmptyProject(),
        filePath: "/existing.wind",
      };
      const callbacks = makeCallbacks({
        getProject: vi.fn().mockReturnValue(projectWithPath),
      });
      mockSaveWindFile.mockResolvedValue(undefined);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleSave();
      expect(result).toBe(true);
      expect(mockSave).not.toHaveBeenCalled();
      expect(callbacks.setFilePath).toHaveBeenCalledWith("/existing.wind");
    });

    it("opens save dialog when no filePath is set", async () => {
      const callbacks = makeCallbacks();
      mockSave.mockResolvedValue("/new.wind");
      mockSaveWindFile.mockResolvedValue(undefined);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleSave();
      expect(result).toBe(true);
      expect(mockSave).toHaveBeenCalled();
    });

    it("returns false when save dialog is cancelled", async () => {
      const callbacks = makeCallbacks();
      mockSave.mockResolvedValue(null);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleSave();
      expect(result).toBe(false);
    });
  });

  describe("handleOpen()", () => {
    const validWindContent = JSON.stringify({
      mandrelParameters: { diameter: 100, windLength: 500 },
      towParameters: { width: 12.7, thickness: 0.25 },
      defaultFeedRate: 400,
      layers: [],
    });

    it("returns false when file dialog is cancelled", async () => {
      const callbacks = makeCallbacks();
      mockOpen.mockResolvedValue(null);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleOpen();
      expect(result).toBe(false);
    });

    it("loads project on successful open", async () => {
      const callbacks = makeCallbacks();
      mockOpen.mockResolvedValue("/file.wind");
      mockLoadWindFile.mockResolvedValue(validWindContent);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleOpen();
      expect(result).toBe(true);
      expect(callbacks.loadProject).toHaveBeenCalled();
      expect(mockAddRecentFile).toHaveBeenCalledWith("/file.wind");
    });

    it("calls showError and throws FileError on load failure", async () => {
      const callbacks = makeCallbacks();
      mockOpen.mockResolvedValue("/bad.wind");
      mockLoadWindFile.mockRejectedValue(new Error("read error"));
      const ops = createFileOperations(callbacks);
      await expect(ops.handleOpen()).rejects.toThrow();
      expect(callbacks.showError).toHaveBeenCalled();
    });

    it("asks confirmation when dirty and aborts on decline", async () => {
      const dirtyProject = { ...createEmptyProject(), isDirty: true };
      const callbacks = makeCallbacks({
        getProject: vi.fn().mockReturnValue(dirtyProject),
      });
      mockAsk.mockResolvedValue(false);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleOpen();
      expect(result).toBe(false);
      expect(callbacks.loadProject).not.toHaveBeenCalled();
    });
  });

  describe("handleOpenRecent()", () => {
    const validWindContent = JSON.stringify({
      mandrelParameters: { diameter: 100, windLength: 500 },
      towParameters: { width: 12.7, thickness: 0.25 },
      defaultFeedRate: 400,
      layers: [],
    });

    it("loads a recent file successfully", async () => {
      const callbacks = makeCallbacks();
      mockLoadWindFile.mockResolvedValue(validWindContent);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleOpenRecent("/recent.wind");
      expect(result).toBe(true);
      expect(callbacks.loadProject).toHaveBeenCalled();
    });

    it("asks confirmation when dirty and aborts on decline", async () => {
      const dirtyProject = { ...createEmptyProject(), isDirty: true };
      const callbacks = makeCallbacks({
        getProject: vi.fn().mockReturnValue(dirtyProject),
      });
      mockAsk.mockResolvedValue(false);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleOpenRecent("/recent.wind");
      expect(result).toBe(false);
    });

    it("calls showError and throws on load failure", async () => {
      const callbacks = makeCallbacks();
      mockLoadWindFile.mockRejectedValue(new Error("not found"));
      const ops = createFileOperations(callbacks);
      await expect(ops.handleOpenRecent("/missing.wind")).rejects.toThrow();
      expect(callbacks.showError).toHaveBeenCalled();
    });
  });

  describe("handleExportGcode()", () => {
    it("returns false when gcode save dialog is cancelled", async () => {
      const callbacks = makeCallbacks();
      mockSave.mockResolvedValue(null);
      const ops = createFileOperations(callbacks);
      const result = await ops.handleExportGcode();
      expect(result).toBe(false);
    });

    it("exports gcode and shows info on success", async () => {
      const callbacks = makeCallbacks();
      mockSave.mockResolvedValue("/output.gcode");
      mockSaveWindFile.mockResolvedValue(undefined);
      mockPlanWind.mockResolvedValue({
        output: "/output.gcode",
        commands: 10,
      });
      const ops = createFileOperations(callbacks);
      const result = await ops.handleExportGcode();
      expect(result).toBe(true);
      expect(callbacks.showInfo).toHaveBeenCalled();
    });

    it("calls showError and throws on planWind failure", async () => {
      const callbacks = makeCallbacks();
      mockSave.mockResolvedValue("/output.gcode");
      mockSaveWindFile.mockResolvedValue(undefined);
      mockPlanWind.mockRejectedValue(new Error("plan failed"));
      const ops = createFileOperations(callbacks);
      await expect(ops.handleExportGcode()).rejects.toThrow();
      expect(callbacks.showError).toHaveBeenCalled();
    });
  });

  describe("handleDuplicateLayer()", () => {
    it("duplicates the active layer and returns true", () => {
      const callbacks = makeCallbacks({
        getActiveLayerId: vi.fn().mockReturnValue("layer-1"),
      });
      const ops = createFileOperations(callbacks);
      const result = ops.handleDuplicateLayer();
      expect(result).toBe(true);
      expect(callbacks.duplicateLayer).toHaveBeenCalledWith("layer-1");
    });

    it("returns false when no active layer", () => {
      const callbacks = makeCallbacks({
        getActiveLayerId: vi.fn().mockReturnValue(null),
      });
      const ops = createFileOperations(callbacks);
      const result = ops.handleDuplicateLayer();
      expect(result).toBe(false);
      expect(callbacks.duplicateLayer).not.toHaveBeenCalled();
    });
  });

  describe("handleDeleteLayer()", () => {
    it("removes the active layer and returns true", () => {
      const callbacks = makeCallbacks({
        getActiveLayerId: vi.fn().mockReturnValue("layer-1"),
      });
      const ops = createFileOperations(callbacks);
      const result = ops.handleDeleteLayer();
      expect(result).toBe(true);
      expect(callbacks.removeLayer).toHaveBeenCalledWith("layer-1");
    });

    it("returns false when no active layer", () => {
      const callbacks = makeCallbacks();
      const ops = createFileOperations(callbacks);
      const result = ops.handleDeleteLayer();
      expect(result).toBe(false);
    });
  });

  describe("handleValidate()", () => {
    it("clears errors and shows info on valid definition", async () => {
      const callbacks = makeCallbacks();
      mockValidateWindDefinition.mockResolvedValue({
        valid: true,
        errors: [],
      });
      const ops = createFileOperations(callbacks);
      const result = await ops.handleValidate();
      expect(result).toBe(true);
      expect(callbacks.clearValidationErrors).toHaveBeenCalled();
      expect(callbacks.showInfo).toHaveBeenCalled();
    });

    it("sets validation errors and throws when backend returns errors", async () => {
      const callbacks = makeCallbacks();
      mockValidateWindDefinition.mockResolvedValue({
        valid: false,
        errors: [{ field: "mandrel.diameter", message: "Must be positive" }],
      });
      const ops = createFileOperations(callbacks);
      await expect(ops.handleValidate()).rejects.toThrow();
      expect(callbacks.setValidationErrors).toHaveBeenCalled();
      expect(callbacks.showError).toHaveBeenCalled();
    });

    it("catches and rethrows unexpected errors", async () => {
      const callbacks = makeCallbacks();
      mockValidateWindDefinition.mockRejectedValue(new Error("network error"));
      const ops = createFileOperations(callbacks);
      await expect(ops.handleValidate()).rejects.toThrow("network error");
      expect(callbacks.showError).toHaveBeenCalled();
    });
  });
});
