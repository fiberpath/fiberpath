import { describe, it, expect } from "vitest";
import {
  StreamSummarySchema,
  MandrelParametersSchema,
  TowParametersSchema,
  WindHoopLayerSchema,
  WindHelicalLayerSchema,
  WindSkipLayerSchema,
  WindLayerSchema,
  WindDefinitionSchema,
  validateData,
  FiberPathError,
  FileError,
  ValidationError,
  CommandError,
  ConnectionError,
  parseError,
  isRetryableError,
} from "./schemas";

describe("schemas", () => {
  describe("Wind File Structure Schemas", () => {
    describe("MandrelParametersSchema", () => {
      it("should validate valid mandrel", () => {
        const data = { diameter: 100, windLength: 200 };
        const result = MandrelParametersSchema.safeParse(data);
        expect(result.success).toBe(true);
      });

      it("should reject zero diameter", () => {
        const data = { diameter: 0, windLength: 200 };
        const result = MandrelParametersSchema.safeParse(data);
        expect(result.success).toBe(false);
      });

      it("should reject negative windLength", () => {
        const data = { diameter: 100, windLength: -50 };
        const result = MandrelParametersSchema.safeParse(data);
        expect(result.success).toBe(false);
      });
    });

    describe("WindHelicalLayerSchema", () => {
      it("should validate valid helical layer", () => {
        const data = {
          windType: "helical" as const,
          windAngle: 45,
          patternNumber: 3,
          skipIndex: 2,
          lockDegrees: 5,
          leadInMM: 10,
          leadOutDegrees: 5,
          skipInitialNearLock: false,
        };

        const result = WindHelicalLayerSchema.safeParse(data);
        expect(result.success).toBe(true);
      });

      it("should reject windAngle > 90", () => {
        const data = {
          windType: "helical" as const,
          windAngle: 95,
          patternNumber: 3,
          skipIndex: 2,
          lockDegrees: 5,
          leadInMM: 10,
          leadOutDegrees: 5,
          skipInitialNearLock: false,
        };

        const result = WindHelicalLayerSchema.safeParse(data);
        expect(result.success).toBe(false);
      });

      it("should reject windAngle < 0", () => {
        const data = {
          windType: "helical" as const,
          windAngle: -5,
          patternNumber: 3,
          skipIndex: 2,
          lockDegrees: 5,
          leadInMM: 10,
          leadOutDegrees: 5,
          skipInitialNearLock: false,
        };

        const result = WindHelicalLayerSchema.safeParse(data);
        expect(result.success).toBe(false);
      });

      it("should reject zero patternNumber", () => {
        const data = {
          windType: "helical" as const,
          windAngle: 45,
          patternNumber: 0,
          skipIndex: 2,
          lockDegrees: 5,
          leadInMM: 10,
          leadOutDegrees: 5,
          skipInitialNearLock: false,
        };

        const result = WindHelicalLayerSchema.safeParse(data);
        expect(result.success).toBe(false);
      });
    });

    describe("WindLayerSchema", () => {
      it("should validate hoop layer", () => {
        const data = {
          windType: "hoop" as const,
          terminal: true,
        };

        const result = WindLayerSchema.safeParse(data);
        expect(result.success).toBe(true);
      });

      it("should validate helical layer", () => {
        const data = {
          windType: "helical" as const,
          windAngle: 60,
          patternNumber: 5,
          skipIndex: 3,
          lockDegrees: 8,
          leadInMM: 15,
          leadOutDegrees: 7,
          skipInitialNearLock: true,
        };

        const result = WindLayerSchema.safeParse(data);
        expect(result.success).toBe(true);
      });

      it("should validate skip layer", () => {
        const data = {
          windType: "skip" as const,
          mandrelRotation: 90,
        };

        const result = WindLayerSchema.safeParse(data);
        expect(result.success).toBe(true);
      });

      it("should reject layer with invalid windType", () => {
        const data = {
          windType: "invalid",
          terminal: false,
        };

        const result = WindLayerSchema.safeParse(data);
        expect(result.success).toBe(false);
      });
    });

    describe("WindDefinitionSchema", () => {
      it("should validate complete wind definition", () => {
        const data = {
          mandrelParameters: { diameter: 100, windLength: 200 },
          towParameters: { width: 3, thickness: 0.25 },
          defaultFeedRate: 1000,
          layers: [
            { windType: "hoop" as const, terminal: false },
            {
              windType: "helical" as const,
              windAngle: 45,
              patternNumber: 3,
              skipIndex: 2,
              lockDegrees: 5,
              leadInMM: 10,
              leadOutDegrees: 5,
              skipInitialNearLock: false,
            },
          ],
        };

        const result = WindDefinitionSchema.safeParse(data);
        expect(result.success).toBe(true);
      });

      it("should reject wind definition with invalid layer", () => {
        const data = {
          mandrelParameters: { diameter: 100, windLength: 200 },
          towParameters: { width: 3, thickness: 0.25 },
          defaultFeedRate: 1000,
          layers: [
            { windType: "helical" as const, windAngle: 120, patternNumber: 1, skipIndex: 0, lockDegrees: 0, leadInMM: 0, leadOutDegrees: 0 }, // Invalid: windAngle > 90
          ],
        };

        const result = WindDefinitionSchema.safeParse(data);
        expect(result.success).toBe(false);
      });

      it("should accept a future 1.x schemaVersion", () => {
        const data = {
          schemaVersion: "1.7",
          mandrelParameters: { diameter: 100, windLength: 200 },
          towParameters: { width: 3, thickness: 0.25 },
          defaultFeedRate: 1000,
          layers: [{ windType: "hoop" as const, terminal: false }],
        };

        const result = WindDefinitionSchema.safeParse(data);
        expect(result.success).toBe(true);
      });

      it("should reject an incompatible major schemaVersion", () => {
        const data = {
          schemaVersion: "2.0",
          mandrelParameters: { diameter: 100, windLength: 200 },
          towParameters: { width: 3, thickness: 0.25 },
          defaultFeedRate: 1000,
          layers: [{ windType: "hoop" as const, terminal: false }],
        };

        const result = WindDefinitionSchema.safeParse(data);
        expect(result.success).toBe(false);
      });
    });
  });

  describe("Validation Helper Functions", () => {
    describe("validateData", () => {
      it("should return data when validation succeeds", () => {
        const data = { diameter: 100, windLength: 200 };
        const result = validateData(MandrelParametersSchema, data, "test mandrel");

        expect(result).toEqual(data);
      });

      it("should throw ValidationError when validation fails", () => {
        const data = { diameter: -50, windLength: 200 };

        expect(() => {
          validateData(MandrelParametersSchema, data, "test mandrel");
        }).toThrow(ValidationError);
      });

      it("should include context in error message", () => {
        const data = { diameter: 0, windLength: -100 };

        try {
          validateData(MandrelParametersSchema, data, "test mandrel");
          expect.fail("Should have thrown");
        } catch (error) {
          expect(error).toBeInstanceOf(ValidationError);
          expect((error as ValidationError).message).toContain("test mandrel");
        }
      });
    });

  });

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
