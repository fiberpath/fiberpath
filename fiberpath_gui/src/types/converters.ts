import {
  HELICAL_DEFAULTS,
  type Layer,
  type HoopLayer as GUIHoopLayer,
  type HelicalLayer as GUIHelicalLayer,
  type SkipLayer as GUISkipLayer,
} from "./project";
import type {
  WindDefinition,
  HoopLayer,
  HelicalLayer,
  SkipLayer,
} from "./wind-schema";
import type { ProjectDocument } from "./document";

/**
 * Convert internal GUI layer format to .wind schema format
 */
export function convertLayerToWindSchema(
  layer: Layer,
): HoopLayer | HelicalLayer | SkipLayer {
  if (layer.type === "hoop") {
    const hoopData = layer.hoop as GUIHoopLayer | undefined;
    return {
      windType: "hoop",
      terminal: hoopData?.terminal ?? false,
    };
  } else if (layer.type === "helical") {
    const helicalData = layer.helical as GUIHelicalLayer | undefined;
    return {
      windType: "helical",
      windAngle: helicalData?.wind_angle ?? HELICAL_DEFAULTS.wind_angle,
      patternNumber: helicalData?.pattern_number ?? HELICAL_DEFAULTS.pattern_number,
      skipIndex: helicalData?.skip_index ?? HELICAL_DEFAULTS.skip_index,
      lockDegrees: helicalData?.lock_degrees ?? HELICAL_DEFAULTS.lock_degrees,
      leadInMM: helicalData?.lead_in_mm ?? HELICAL_DEFAULTS.lead_in_mm,
      leadOutDegrees: helicalData?.lead_out_degrees ?? HELICAL_DEFAULTS.lead_out_degrees,
      skipInitialNearLock:
        helicalData?.skip_initial_near_lock ?? HELICAL_DEFAULTS.skip_initial_near_lock,
    };
  } else if (layer.type === "skip") {
    const skipData = layer.skip as GUISkipLayer | undefined;
    return {
      windType: "skip",
      mandrelRotation: skipData?.mandrel_rotation ?? 90,
    };
  }

  // Should never reach here - TypeScript ensures all layer types are handled
  throw new Error(`Unknown layer type: ${layer.type}`);
}

/**
 * Convert full project to .wind schema format
 */
export function projectToWindDefinition(
  project: {
    mandrel: { diameter: number; wind_length: number };
    tow: { width: number; thickness: number };
    layers: Layer[];
    defaultFeedRate: number;
  },
  visibleLayerCount?: number,
): WindDefinition {
  const layersToInclude = visibleLayerCount
    ? project.layers.slice(0, visibleLayerCount)
    : project.layers;

  return {
    schemaVersion: "1.0",
    mandrelParameters: {
      diameter: project.mandrel.diameter,
      windLength: project.mandrel.wind_length,
    },
    towParameters: {
      width: project.tow.width,
      thickness: project.tow.thickness,
    },
    defaultFeedRate: project.defaultFeedRate,
    layers: layersToInclude.map(convertLayerToWindSchema),
  };
}

/**
 * Convert .wind schema layer format back to internal GUI format
 */
export function convertWindSchemaToLayer(
  schemaLayer: HoopLayer | HelicalLayer | SkipLayer,
): Layer {
  if (schemaLayer.windType === "hoop") {
    return {
      id: crypto.randomUUID(),
      type: "hoop",
      hoop: {
        terminal: schemaLayer.terminal ?? false,
      },
    };
  } else if (schemaLayer.windType === "helical") {
    return {
      id: crypto.randomUUID(),
      type: "helical",
      helical: {
        wind_angle: schemaLayer.windAngle,
        pattern_number: schemaLayer.patternNumber,
        skip_index: schemaLayer.skipIndex,
        lock_degrees: schemaLayer.lockDegrees ?? HELICAL_DEFAULTS.lock_degrees,
        lead_in_mm: schemaLayer.leadInMM ?? HELICAL_DEFAULTS.lead_in_mm,
        lead_out_degrees: schemaLayer.leadOutDegrees ?? HELICAL_DEFAULTS.lead_out_degrees,
        skip_initial_near_lock:
          schemaLayer.skipInitialNearLock ?? HELICAL_DEFAULTS.skip_initial_near_lock,
      },
    };
  } else if (schemaLayer.windType === "skip") {
    return {
      id: crypto.randomUUID(),
      type: "skip",
      skip: {
        mandrel_rotation: schemaLayer.mandrelRotation,
      },
    };
  }

  // Should never reach here - TypeScript ensures all windTypes are handled
  throw new Error(`Unknown wind type: ${schemaLayer.windType}`);
}

/**
 * Convert a .wind definition to the persisted ProjectDocument (no transient
 * session fields). The Svelte session tracks filePath/selection separately.
 */
export function windDefinitionToDocument(windDef: WindDefinition): ProjectDocument {
  return {
    mandrel: {
      diameter: windDef.mandrelParameters.diameter,
      wind_length: windDef.mandrelParameters.windLength,
    },
    tow: {
      width: windDef.towParameters.width,
      thickness: windDef.towParameters.thickness,
    },
    layers: windDef.layers.map(convertWindSchemaToLayer),
    defaultFeedRate: windDef.defaultFeedRate,
  };
}
