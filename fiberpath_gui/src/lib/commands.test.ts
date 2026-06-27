import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import {
  planWind,
  plotDefinition,
  saveWindFile,
  loadWindFile,
  validateWindDefinition,
} from "./commands";
import { getApiClient } from "./apiClient";
import { CommandError } from "./schemas";

// Remove retry wrapping so each test controls the mock directly.
vi.mock("./retry", () => ({
  withRetry:
    (fn: (...args: unknown[]) => unknown, _opts?: unknown) =>
    (...args: unknown[]) =>
      fn(...args),
  retry: (fn: () => unknown) => fn(),
}));

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("./apiClient", () => ({ getApiClient: vi.fn() }));

const mockInvoke = vi.mocked(invoke);
const mockPost = vi.fn();

beforeEach(() => {
  mockInvoke.mockReset();
  mockPost.mockReset();
  vi.mocked(getApiClient).mockResolvedValue({ POST: mockPost } as never);
});

describe("commands", () => {
  describe("planWind()", () => {
    it("POSTs /plan and writes the returned gcode to the output path", async () => {
      mockPost.mockResolvedValue({
        data: { gcode: "G1 X0", commandCount: 10 },
        error: undefined,
        response: { status: 200 },
      });
      mockInvoke.mockResolvedValue(undefined); // save_wind_file

      const result = await planWind('{"layers":[]}', "/out.gcode");

      expect(result).toEqual({ output: "/out.gcode", commands: 10 });
      expect(mockPost).toHaveBeenCalledWith("/plan", { body: { layers: [] } });
      expect(mockInvoke).toHaveBeenCalledWith(
        "save_wind_file",
        expect.objectContaining({ path: "/out.gcode", content: "G1 X0" }),
      );
    });

    it("throws CommandError when the plan request errors", async () => {
      mockPost.mockResolvedValue({
        data: undefined,
        error: { detail: "bad" },
        response: { status: 400 },
      });
      await expect(planWind("{}", "/out.gcode")).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("plotDefinition()", () => {
    it("plans then plots and returns base64 image bytes", async () => {
      mockPost
        .mockResolvedValueOnce({
          data: { gcode: "G1", commandCount: 1 },
          error: undefined,
          response: { status: 200 },
        })
        .mockResolvedValueOnce({
          data: new Uint8Array([1, 2, 3]).buffer,
          error: undefined,
          response: { status: 200 },
        });

      const result = await plotDefinition('{"layers":[]}', 3);

      expect(result.imageBase64).toBe(btoa("\x01\x02\x03"));
      expect(result.warnings).toEqual([]);
    });

    it("throws CommandError when planning fails", async () => {
      mockPost.mockResolvedValue({
        data: undefined,
        error: { detail: "nope" },
        response: { status: 400 },
      });
      await expect(plotDefinition("{}", 3)).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("validateWindDefinition()", () => {
    it("returns valid:true on 200", async () => {
      mockPost.mockResolvedValue({
        data: { valid: true },
        error: undefined,
        response: { status: 200 },
      });
      const result = await validateWindDefinition("{}");
      expect(result.valid).toBe(true);
    });

    it("maps a 400 detail string to a field error (not a throw)", async () => {
      mockPost.mockResolvedValue({
        data: undefined,
        error: { detail: "wind angle must be 1-89" },
        response: { status: 400 },
      });
      const result = await validateWindDefinition("{}");
      expect(result.valid).toBe(false);
      expect(result.errors).toEqual([{ field: "", message: "wind angle must be 1-89" }]);
    });

    it("throws CommandError when the request itself fails", async () => {
      mockPost.mockRejectedValue(new Error("network down"));
      await expect(validateWindDefinition("{}")).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("saveWindFile()", () => {
    it("resolves without error on success", async () => {
      mockInvoke.mockResolvedValue(undefined);
      await expect(saveWindFile("/path.wind", "{}")).resolves.toBeUndefined();
    });

    it("throws CommandError on failure", async () => {
      mockInvoke.mockRejectedValue(new Error("write error"));
      await expect(saveWindFile("/path.wind", "{}")).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("loadWindFile()", () => {
    it("returns string content on success", async () => {
      mockInvoke.mockResolvedValue('{"key":"value"}');
      const result = await loadWindFile("/path.wind");
      expect(result).toBe('{"key":"value"}');
    });

    it("throws CommandError when result is not a string", async () => {
      mockInvoke.mockResolvedValue(42);
      await expect(loadWindFile("/path.wind")).rejects.toBeInstanceOf(CommandError);
    });
  });
});
