import { describe, it, expect } from "vitest";
import {
  convertLayerToWindSchema,
  convertWindSchemaToLayer,
  projectToWindDefinition,
  windDefinitionToProject,
} from "./converters";
import { createLayer, type Layer, type FiberPathProject } from "./project";
import type { WindDefinition } from "./wind-schema";

describe("converters", () => {
  describe("convertLayerToWindSchema", () => {
    it("should convert hoop layer to wind schema", () => {
      const layer: Layer = {
        id: "test-id",
        type: "hoop",
        hoop: { terminal: true },
      };

      const result = convertLayerToWindSchema(layer);

      expect(result).toEqual({
        windType: "hoop",
        terminal: true,
      });
    });

    it("should convert helical layer to wind schema", () => {
      const layer: Layer = {
        id: "test-id",
        type: "helical",
        helical: {
          wind_angle: 60,
          pattern_number: 5,
          skip_index: 3,
          lock_degrees: 10,
          lead_in_mm: 15,
          lead_out_degrees: 8,
          skip_initial_near_lock: true,
        },
      };

      const result = convertLayerToWindSchema(layer);

      expect(result).toEqual({
        windType: "helical",
        windAngle: 60,
        patternNumber: 5,
        skipIndex: 3,
        lockDegrees: 10,
        leadInMM: 15,
        leadOutDegrees: 8,
        skipInitialNearLock: true,
      });
    });

    it("should convert skip layer to wind schema", () => {
      const layer: Layer = {
        id: "test-id",
        type: "skip",
        skip: { mandrel_rotation: 180 },
      };

      const result = convertLayerToWindSchema(layer);

      expect(result).toEqual({
        windType: "skip",
        mandrelRotation: 180,
      });
    });

    it("should use default values for missing hoop properties", () => {
      const layer: Layer = {
        id: "test-id",
        type: "hoop",
        hoop: undefined,
      };

      const result = convertLayerToWindSchema(layer);

      expect(result).toEqual({
        windType: "hoop",
        terminal: false,
      });
    });

    it("should use default values for missing helical properties", () => {
      const layer: Layer = {
        id: "test-id",
        type: "helical",
        helical: undefined,
      };

      const result = convertLayerToWindSchema(layer);

      expect(result).toEqual({
        windType: "helical",
        windAngle: 45,
        patternNumber: 3,
        skipIndex: 2,
        lockDegrees: 540,
        leadInMM: 25,
        leadOutDegrees: 60,
        skipInitialNearLock: false,
      });
    });
  });

  describe("convertWindSchemaToLayer", () => {
    it("should convert wind schema hoop to layer", () => {
      const windLayer = {
        windType: "hoop" as const,
        terminal: true,
      };

      const result = convertWindSchemaToLayer(windLayer);

      expect(result.type).toBe("hoop");
      expect(result.hoop).toEqual({ terminal: true });
      expect(result.id).toBeTruthy();
    });

    it("should convert wind schema helical to layer", () => {
      const windLayer = {
        windType: "helical" as const,
        windAngle: 55,
        patternNumber: 7,
        skipIndex: 4,
        lockDegrees: 12,
        leadInMM: 20,
        leadOutDegrees: 10,
        skipInitialNearLock: false,
      };

      const result = convertWindSchemaToLayer(windLayer);

      expect(result.type).toBe("helical");
      expect(result.helical).toEqual({
        wind_angle: 55,
        pattern_number: 7,
        skip_index: 4,
        lock_degrees: 12,
        lead_in_mm: 20,
        lead_out_degrees: 10,
        skip_initial_near_lock: false,
      });
    });

    it("should convert wind schema skip to layer", () => {
      const windLayer = {
        windType: "skip" as const,
        mandrelRotation: 270,
      };

      const result = convertWindSchemaToLayer(windLayer);

      expect(result.type).toBe("skip");
      expect(result.skip).toEqual({ mandrel_rotation: 270 });
    });

    it("should use defaults for missing optional helical properties", () => {
      const windLayer = {
        windType: "helical" as const,
        windAngle: 50,
        patternNumber: 5,
        skipIndex: 3,
        lockDegrees: 8,
        leadInMM: 12,
        leadOutDegrees: 6,
        skipInitialNearLock: false,
      };

      const result = convertWindSchemaToLayer(windLayer);

      expect(result.helical?.skip_initial_near_lock).toBe(false);
    });
  });

  describe("helical default round-trip", () => {
    it("preserves a freshly created helical layer through GUI->schema->GUI", () => {
      const original = createLayer("helical");
      const roundTripped = convertWindSchemaToLayer(
        convertLayerToWindSchema(original),
      );
      // ids are regenerated; the helical payload must survive unchanged
      // (regression guard: defaults must not collapse to lock_degrees=5).
      expect(roundTripped.helical).toEqual(original.helical);
      expect(roundTripped.helical?.lock_degrees).toBe(540);
    });
  });

  describe("projectToWindDefinition", () => {
    it("should convert full project to wind definition", () => {
      const project: FiberPathProject = {
        filePath: "/test/file.wind",
        isDirty: false,
        mandrel: { diameter: 120, wind_length: 250 },
        tow: { width: 4, thickness: 0.3 },
        layers: [
          {
            id: "layer-1",
            type: "hoop",
            hoop: { terminal: false },
          },
          {
            id: "layer-2",
            type: "helical",
            helical: {
              wind_angle: 50,
              pattern_number: 4,
              skip_index: 2,
              lock_degrees: 7,
              lead_in_mm: 12,
              lead_out_degrees: 6,
              skip_initial_near_lock: true,
            },
          },
        ],
        defaultFeedRate: 2500,
        activeLayerId: "layer-2",
      };

      const result = projectToWindDefinition(project);

      expect(result).toEqual({
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 120,
          windLength: 250,
        },
        towParameters: {
          width: 4,
          thickness: 0.3,
        },
        defaultFeedRate: 2500,
        layers: [
          {
            windType: "hoop",
            terminal: false,
          },
          {
            windType: "helical",
            windAngle: 50,
            patternNumber: 4,
            skipIndex: 2,
            lockDegrees: 7,
            leadInMM: 12,
            leadOutDegrees: 6,
            skipInitialNearLock: true,
          },
        ],
      });
    });

    it("should respect visibleLayerCount parameter", () => {
      const project: FiberPathProject = {
        filePath: null,
        isDirty: false,
        mandrel: { diameter: 100, wind_length: 200 },
        tow: { width: 3, thickness: 0.25 },
        layers: [
          { id: "1", type: "hoop", hoop: { terminal: false } },
          {
            id: "2",
            type: "helical",
            helical: {
              wind_angle: 45,
              pattern_number: 3,
              skip_index: 2,
              lock_degrees: 5,
              lead_in_mm: 10,
              lead_out_degrees: 5,
              skip_initial_near_lock: false,
            },
          },
          { id: "3", type: "skip", skip: { mandrel_rotation: 90 } },
        ],
        defaultFeedRate: 2000,
        activeLayerId: null,
      };

      const result = projectToWindDefinition(project, 2);

      expect(result.layers).toHaveLength(2);
      expect(result.layers[0]).toHaveProperty("windType", "hoop");
      expect(result.layers[1]).toHaveProperty("windType", "helical");
    });

    it("should include all layers when visibleLayerCount is not provided", () => {
      const project: FiberPathProject = {
        filePath: null,
        isDirty: false,
        mandrel: { diameter: 100, wind_length: 200 },
        tow: { width: 3, thickness: 0.25 },
        layers: [
          { id: "1", type: "hoop", hoop: { terminal: false } },
          {
            id: "2",
            type: "helical",
            helical: {
              wind_angle: 45,
              pattern_number: 3,
              skip_index: 2,
              lock_degrees: 5,
              lead_in_mm: 10,
              lead_out_degrees: 5,
              skip_initial_near_lock: false,
            },
          },
          { id: "3", type: "skip", skip: { mandrel_rotation: 90 } },
        ],
        defaultFeedRate: 2000,
        activeLayerId: null,
      };

      const result = projectToWindDefinition(project);

      expect(result.layers).toHaveLength(3);
    });
  });

  describe("windDefinitionToProject", () => {
    it("should convert wind definition to project", () => {
      const windDef: WindDefinition = {
        schemaVersion: "1.0",
        mandrelParameters: {
          diameter: 130,
          windLength: 280,
        },
        towParameters: {
          width: 5,
          thickness: 0.4,
        },
        defaultFeedRate: 3000,
        layers: [
          {
            windType: "hoop",
            terminal: true,
          },
          {
            windType: "helical",
            windAngle: 65,
            patternNumber: 6,
            skipIndex: 3,
            lockDegrees: 9,
            leadInMM: 18,
            leadOutDegrees: 9,
            skipInitialNearLock: true,
          },
          {
            windType: "skip",
            mandrelRotation: 120,
          },
        ],
      };

      const result = windDefinitionToProject(windDef, "/path/to/file.wind");

      expect(result.filePath).toBe("/path/to/file.wind");
      expect(result.isDirty).toBe(false);
      expect(result.mandrel).toEqual({ diameter: 130, wind_length: 280 });
      expect(result.tow).toEqual({ width: 5, thickness: 0.4 });
      expect(result.defaultFeedRate).toBe(3000);
      expect(result.layers).toHaveLength(3);
      expect(result.layers[0].type).toBe("hoop");
      expect(result.layers[1].type).toBe("helical");
      expect(result.layers[2].type).toBe("skip");
      expect(result.activeLayerId).toBeNull();
    });

    it("should default filePath to null when not provided", () => {
      const windDef: WindDefinition = {
        schemaVersion: "1.0",
        mandrelParameters: { diameter: 100, windLength: 200 },
        towParameters: { width: 3, thickness: 0.25 },
        defaultFeedRate: 2000,
        layers: [],
      };

      const result = windDefinitionToProject(windDef);

      expect(result.filePath).toBeNull();
    });

    it("should handle empty layers array", () => {
      const windDef: WindDefinition = {
        schemaVersion: "1.0",
        mandrelParameters: { diameter: 100, windLength: 200 },
        towParameters: { width: 3, thickness: 0.25 },
        defaultFeedRate: 2000,
        layers: [],
      };

      const result = windDefinitionToProject(windDef);

      expect(result.layers).toHaveLength(0);
      expect(result.activeLayerId).toBeNull();
    });

    it("should preserve layer order", () => {
      const windDef: WindDefinition = {
        schemaVersion: "1.0",
        mandrelParameters: { diameter: 100, windLength: 200 },
        towParameters: { width: 3, thickness: 0.25 },
        defaultFeedRate: 2000,
        layers: [
          { windType: "skip", mandrelRotation: 45 },
          {
            windType: "helical",
            windAngle: 30,
            patternNumber: 2,
            skipIndex: 1,
            lockDegrees: 3,
            leadInMM: 5,
            leadOutDegrees: 3,
            skipInitialNearLock: false,
          },
          { windType: "hoop", terminal: false },
        ],
      };

      const result = windDefinitionToProject(windDef);

      expect(result.layers[0].type).toBe("skip");
      expect(result.layers[1].type).toBe("helical");
      expect(result.layers[2].type).toBe("hoop");
    });
  });

  describe("round-trip conversion", () => {
    it("should preserve data through project -> wind -> project conversion", () => {
      const originalProject: FiberPathProject = {
        filePath: "/test.wind",
        isDirty: false,
        mandrel: { diameter: 150, wind_length: 300 },
        tow: { width: 6, thickness: 0.5 },
        layers: [
          {
            id: "layer-1",
            type: "hoop",
            hoop: { terminal: true },
          },
          {
            id: "layer-2",
            type: "helical",
            helical: {
              wind_angle: 70,
              pattern_number: 8,
              skip_index: 5,
              lock_degrees: 15,
              lead_in_mm: 25,
              lead_out_degrees: 12,
              skip_initial_near_lock: true,
            },
          },
          {
            id: "layer-3",
            type: "skip",
            skip: { mandrel_rotation: 135 },
          },
        ],
        defaultFeedRate: 3500,
        activeLayerId: "layer-2",
      };

      // Convert to wind definition and back
      const windDef = projectToWindDefinition(originalProject);
      const roundTripProject = windDefinitionToProject(
        windDef,
        originalProject.filePath!,
      );

      // Check that critical data is preserved (IDs will be different)
      expect(roundTripProject.mandrel).toEqual(originalProject.mandrel);
      expect(roundTripProject.tow).toEqual(originalProject.tow);
      expect(roundTripProject.defaultFeedRate).toEqual(
        originalProject.defaultFeedRate,
      );
      expect(roundTripProject.layers).toHaveLength(
        originalProject.layers.length,
      );

      // Check layer types and data
      expect(roundTripProject.layers[0].type).toBe("hoop");
      expect(roundTripProject.layers[0].hoop?.terminal).toBe(true);

      expect(roundTripProject.layers[1].type).toBe("helical");
      expect(roundTripProject.layers[1].helical?.wind_angle).toBe(70);
      expect(roundTripProject.layers[1].helical?.pattern_number).toBe(8);

      expect(roundTripProject.layers[2].type).toBe("skip");
      expect(roundTripProject.layers[2].skip?.mandrel_rotation).toBe(135);
    });
  });
});
