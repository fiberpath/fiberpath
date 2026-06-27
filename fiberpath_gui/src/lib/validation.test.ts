import { describe, it, expect, beforeEach } from "vitest";
import { validateWindDefinition } from "./validation";
import type { WindDefinition } from "../types/wind-schema";

describe("Wind Definition Validation", () => {
  describe("Valid definitions", () => {
    it("should validate a minimal valid hoop layer definition", () => {
      const validDef: WindDefinition = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "hoop",
            terminal: false,
          },
        ],
      };

      const result = validateWindDefinition(validDef);
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("should validate a helical layer with all required fields", () => {
      const validDef: WindDefinition = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "helical",
            windAngle: 45,
            patternNumber: 3,
            skipIndex: 1,
            lockDegrees: 10,
            leadInMM: 5,
            leadOutDegrees: 10,
            skipInitialNearLock: false,
          },
        ],
      };

      const result = validateWindDefinition(validDef);
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("should validate a skip layer", () => {
      const validDef: WindDefinition = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "skip",
            mandrelRotation: 180,
          },
        ],
      };

      const result = validateWindDefinition(validDef);
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it("should validate a definition with multiple layer types", () => {
      const validDef: WindDefinition = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "hoop",
            terminal: false,
          },
          {
            windType: "helical",
            windAngle: 35,
            patternNumber: 4,
            skipIndex: 1,
            lockDegrees: 10,
            leadInMM: 5,
            leadOutDegrees: 10,
          },
          {
            windType: "skip",
            mandrelRotation: 90,
          },
          {
            windType: "hoop",
            terminal: true,
          },
        ],
      };

      const result = validateWindDefinition(validDef);
      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
  });

  describe("Invalid definitions", () => {
    it("should reject missing required top-level fields", () => {
      const invalidDef = {
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        // Missing towParameters, defaultFeedRate, layers
      };

      const result = validateWindDefinition(invalidDef);
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it("should reject negative mandrel diameter", () => {
      const invalidDef = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: -150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [],
      };

      const result = validateWindDefinition(invalidDef);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.field.includes("diameter"))).toBe(
        true,
      );
    });

    it("should reject zero tow width", () => {
      const invalidDef = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 0,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [],
      };

      const result = validateWindDefinition(invalidDef);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.field.includes("width"))).toBe(true);
    });

    it("should reject helical layer with missing required fields", () => {
      const invalidDef = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "helical",
            windAngle: 45,
            // Missing patternNumber, skipIndex, lockDegrees, leadInMM, leadOutDegrees
          },
        ],
      };

      const result = validateWindDefinition(invalidDef);
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it("should reject helical layer with zero wind angle", () => {
      const invalidDef = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "helical",
            windAngle: 0,
            patternNumber: 3,
            skipIndex: 1,
            lockDegrees: 10,
            leadInMM: 5,
            leadOutDegrees: 10,
          },
        ],
      };

      const result = validateWindDefinition(invalidDef);
      expect(result.valid).toBe(false);
      expect(result.errors.some((e) => e.field.includes("windAngle"))).toBe(
        true,
      );
    });

    it("should reject skip layer without mandrelRotation", () => {
      const invalidDef = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "skip",
            // Missing mandrelRotation
          },
        ],
      };

      const result = validateWindDefinition(invalidDef);
      expect(result.valid).toBe(false);
      if (!result.valid) {
        expect(
          result.errors.some(
            (e) =>
              e.field.includes("mandrelRotation") ||
              e.message.includes("mandrelRotation"),
          ),
        ).toBe(true);
      }
    });

    it("should reject invalid layer type", () => {
      const invalidDef = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "invalid_type",
          },
        ],
      };

      const result = validateWindDefinition(invalidDef);
      expect(result.valid).toBe(false);
    });

    it("should reject non-object input", () => {
      const result = validateWindDefinition("not an object");
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it("should reject null input", () => {
      const result = validateWindDefinition(null);
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });

    it("should reject empty object", () => {
      const result = validateWindDefinition({});
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
    });
  });

  describe("Error messages", () => {
    it("should provide meaningful error messages", () => {
      const invalidDef = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 150,
          windLength: 800,
        },
        towParameters: {
          width: 12,
          thickness: 0.25,
        },
        defaultFeedRate: 1000,
        layers: [
          {
            windType: "helical",
            windAngle: 45,
            // Missing required fields
          },
        ],
      };

      const result = validateWindDefinition(invalidDef);
      expect(result.valid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(0);
      result.errors.forEach((error) => {
        expect(error.field).toBeDefined();
        expect(error.message).toBeDefined();
        expect(typeof error.field).toBe("string");
        expect(typeof error.message).toBe("string");
      });
    });
  });
});
