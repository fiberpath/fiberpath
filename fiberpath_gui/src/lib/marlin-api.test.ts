import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  listSerialPorts,
  connectMarlin,
  disconnectMarlin,
  sendCommand,
  startJob,
  getJob,
  pauseJob,
  resumeJob,
  cancelJob,
  emergencyStop,
} from "./marlin-api";
import { getApiClient } from "./apiClient";
import { CommandError } from "./schemas";

vi.mock("./apiClient", () => ({ getApiClient: vi.fn() }));

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockDelete = vi.fn();

beforeEach(() => {
  mockGet.mockReset();
  mockPost.mockReset();
  mockDelete.mockReset();
  vi.mocked(getApiClient).mockResolvedValue({
    GET: mockGet,
    POST: mockPost,
    DELETE: mockDelete,
  } as never);
});

const ok = (data: unknown) => ({ data, error: undefined, response: { status: 200 } });
const err = (status: number) => ({ data: undefined, error: { detail: "boom" }, response: { status } });

describe("marlin-api", () => {
  describe("listSerialPorts()", () => {
    it("GETs /machine/ports and returns the array", async () => {
      const ports = [{ port: "/dev/ttyUSB0", description: "USB Serial", hwid: "x" }];
      mockGet.mockResolvedValue(ok(ports));
      const result = await listSerialPorts();
      expect(result).toEqual(ports);
      expect(mockGet).toHaveBeenCalledWith("/machine/ports", {});
    });

    it("throws CommandError on error", async () => {
      mockGet.mockResolvedValue(err(500));
      await expect(listSerialPorts()).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("connectMarlin()", () => {
    it("POSTs /machine/connection with port/baud/timeout and returns connection info", async () => {
      const info = {
        state: "connected",
        port: "/dev/ttyUSB0",
        baud_rate: 250000,
        firmware: "Marlin 2.1.2",
        capabilities: { EEPROM: true },
      };
      mockPost.mockResolvedValue(ok(info));
      const result = await connectMarlin("/dev/ttyUSB0", 250000);
      expect(result).toEqual(info);
      expect(mockPost).toHaveBeenCalledWith("/machine/connection", {
        body: { port: "/dev/ttyUSB0", baud_rate: 250000, timeout: 10 },
      });
    });

    it("defaults the baud rate to 250000", async () => {
      mockPost.mockResolvedValue(ok({ state: "connected" }));
      await connectMarlin("/dev/ttyUSB0");
      expect(mockPost).toHaveBeenCalledWith(
        "/machine/connection",
        expect.objectContaining({ body: expect.objectContaining({ baud_rate: 250000 }) }),
      );
    });

    it("throws CommandError on error", async () => {
      mockPost.mockResolvedValue(err(400));
      await expect(connectMarlin("/dev/ttyUSB0")).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("disconnectMarlin()", () => {
    it("DELETEs /machine/connection (204, no data)", async () => {
      mockDelete.mockResolvedValue({ data: undefined, error: undefined, response: { status: 204 } });
      await expect(disconnectMarlin()).resolves.toBeUndefined();
      expect(mockDelete).toHaveBeenCalledWith("/machine/connection", {});
    });

    it("throws CommandError on error", async () => {
      mockDelete.mockResolvedValue(err(409));
      await expect(disconnectMarlin()).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("sendCommand()", () => {
    it("POSTs /machine/commands and returns the responses array", async () => {
      mockPost.mockResolvedValue(ok({ responses: ["ok"] }));
      const result = await sendCommand("G28");
      expect(result).toEqual(["ok"]);
      expect(mockPost).toHaveBeenCalledWith("/machine/commands", { body: { gcode: "G28" } });
    });

    it("throws CommandError on error", async () => {
      mockPost.mockResolvedValue(err(400));
      await expect(sendCommand("G28")).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("startJob()", () => {
    it("POSTs /machine/jobs and returns job id + total", async () => {
      mockPost.mockResolvedValue(ok({ job_id: "abc", total: 42 }));
      const result = await startJob("G1 X0\nG1 X1");
      expect(result).toEqual({ job_id: "abc", total: 42 });
      expect(mockPost).toHaveBeenCalledWith("/machine/jobs", { body: { gcode: "G1 X0\nG1 X1" } });
    });

    it("throws CommandError on error", async () => {
      mockPost.mockResolvedValue(err(400));
      await expect(startJob("G1")).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("getJob()", () => {
    it("GETs /machine/jobs/{job_id} with the since cursor", async () => {
      const status = { id: "abc", state: "streaming", sent: 5, total: 10, cursor: 3, events: [] };
      mockGet.mockResolvedValue(ok(status));
      const result = await getJob("abc", 3);
      expect(result).toEqual(status);
      expect(mockGet).toHaveBeenCalledWith("/machine/jobs/{job_id}", {
        params: { path: { job_id: "abc" }, query: { since: 3 } },
      });
    });

    it("defaults since to 0", async () => {
      mockGet.mockResolvedValue(ok({ id: "abc", state: "streaming", cursor: 0, events: [] }));
      await getJob("abc");
      expect(mockGet).toHaveBeenCalledWith(
        "/machine/jobs/{job_id}",
        expect.objectContaining({ params: expect.objectContaining({ query: { since: 0 } }) }),
      );
    });

    it("throws CommandError on error", async () => {
      mockGet.mockResolvedValue(err(404));
      await expect(getJob("abc")).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("pauseJob() / resumeJob() / cancelJob()", () => {
    it.each([
      ["pause", pauseJob, "/machine/jobs/{job_id}/pause"],
      ["resume", resumeJob, "/machine/jobs/{job_id}/resume"],
      ["cancel", cancelJob, "/machine/jobs/{job_id}/cancel"],
    ] as const)("%s POSTs the right path with the job id", async (_name, fn, path) => {
      const status = { id: "abc", state: "paused", cursor: 0, events: [] };
      mockPost.mockResolvedValue(ok(status));
      const result = await fn("abc");
      expect(result).toEqual(status);
      expect(mockPost).toHaveBeenCalledWith(path, { params: { path: { job_id: "abc" } } });
    });

    it("throws CommandError on error", async () => {
      mockPost.mockResolvedValue(err(409));
      await expect(pauseJob("abc")).rejects.toBeInstanceOf(CommandError);
    });
  });

  describe("emergencyStop()", () => {
    it("POSTs /machine/estop (204, no data)", async () => {
      mockPost.mockResolvedValue({ data: undefined, error: undefined, response: { status: 204 } });
      await expect(emergencyStop()).resolves.toBeUndefined();
      expect(mockPost).toHaveBeenCalledWith("/machine/estop", {});
    });

    it("throws CommandError on error", async () => {
      mockPost.mockResolvedValue(err(500));
      await expect(emergencyStop()).rejects.toBeInstanceOf(CommandError);
    });
  });
});
