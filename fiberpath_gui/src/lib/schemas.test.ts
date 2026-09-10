import { describe, it, expect } from "vitest";
import {
  FiberPathError,
  FileError,
  ValidationError,
  CommandError,
  ConnectionError,
  parseError,
  isRetryableError,
} from "./schemas";

describe("schemas", () => {
  describe("Custom Error Classes", () => {
    describe("FiberPathError", () => {
      it("should create error with message", () => {
        const error = new FiberPathError("Test error");

        expect(error.message).toBe("Test error");
        expect(error.name).toBe("FiberPathError");
        expect(error).toBeInstanceOf(Error);
      });

      it("should store context", () => {
        const context = { key: "value", count: 42 };
        const error = new FiberPathError("Test error", context);

        expect(error.context).toEqual(context);
      });
    });

    describe("FileError", () => {
      it("should create file error with all properties", () => {
        const error = new FileError(
          "Failed to save",
          "/path/file.wind",
          "save",
        );

        expect(error.message).toBe("Failed to save");
        expect(error.path).toBe("/path/file.wind");
        expect(error.operation).toBe("save");
        expect(error.name).toBe("FileError");
        expect(error).toBeInstanceOf(FiberPathError);
      });
    });

    describe("ValidationError", () => {
      it("should create validation error with errors array", () => {
        const errors = [
          { field: "mandrel.diameter", message: "Must be positive" },
          { field: "tow.width", message: "Required" },
        ];
        const error = new ValidationError("Validation failed", errors);

        expect(error.message).toBe("Validation failed");
        expect(error.errors).toEqual(errors);
        expect(error.name).toBe("ValidationError");
      });
    });

    describe("CommandError", () => {
      it("should create command error with command name", () => {
        const originalError = new Error("Underlying error");
        const error = new CommandError(
          "Command failed",
          "plan_wind",
          originalError,
        );

        expect(error.message).toBe("Command failed");
        expect(error.command).toBe("plan_wind");
        expect(error.originalError).toBe(originalError);
        expect(error.name).toBe("CommandError");
      });
    });

    describe("ConnectionError", () => {
      it("should create connection error with endpoint", () => {
        const error = new ConnectionError(
          "Connection lost",
          "http://localhost:8000",
        );

        expect(error.message).toBe("Connection lost");
        expect(error.endpoint).toBe("http://localhost:8000");
        expect(error.name).toBe("ConnectionError");
      });
    });
  });

  describe("Error Parsing Utilities", () => {
    describe("parseError", () => {
      it("should extract message from FiberPathError", () => {
        const error = new FileError(
          "File not found",
          "/path/file.wind",
          "load",
        );
        expect(parseError(error)).toBe("File not found");
      });

      it("should extract message from standard Error", () => {
        const error = new Error("Standard error");
        expect(parseError(error)).toBe("Standard error");
      });

      it("should handle string errors", () => {
        expect(parseError("Error string")).toBe("Error string");
      });

      it("should handle objects with message property", () => {
        const error = { message: "Object error" };
        expect(parseError(error)).toBe("Object error");
      });

      it("should handle unknown error types", () => {
        expect(parseError(null)).toBe("An unknown error occurred");
        expect(parseError(undefined)).toBe("An unknown error occurred");
        expect(parseError(42)).toBe("An unknown error occurred");
      });
    });

    describe("isRetryableError", () => {
      it("should not retry ValidationError", () => {
        const error = new ValidationError("Validation failed");
        expect(isRetryableError(error)).toBe(false);
      });

      it("should retry FileError", () => {
        const error = new FileError("File locked", "/path/file.wind", "save");
        expect(isRetryableError(error)).toBe(true);
      });

      it("should retry ConnectionError", () => {
        const error = new ConnectionError("Network timeout");
        expect(isRetryableError(error)).toBe(true);
      });

      it("should not retry CommandError with validation message", () => {
        const error = new CommandError("Validation failed", "plan_wind");
        expect(isRetryableError(error)).toBe(false);
      });

      it("should retry CommandError with IO message", () => {
        const error = new CommandError("Failed to read file", "load_wind_file");
        expect(isRetryableError(error)).toBe(true);
      });

      it("should retry unknown errors by default", () => {
        const error = new Error("Unknown error");
        expect(isRetryableError(error)).toBe(true);
      });
    });
  });
});
