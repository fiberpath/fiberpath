// Project state interfaces matching fiberpath/config/schemas.py

// Von Kármán (LD-Haack) nose profile (schemaVersion 1.2+). Carries only its
// discriminator; base radius comes from `diameter` and length from `wind_length`
// (no duplicated dimensions), mirroring the engine's VonKarmanProfile.
export interface MandrelProfile {
  type: "vonKarman";
}

export interface Mandrel {
  diameter: number; // mm
  wind_length: number; // mm
  // Small-end diameter of a reducing cone/frustum (schemaVersion 1.1+). Absent
  // means a plain cylinder. Preserved on load/save so cone files round-trip
  // without silent data loss (#344).
  end_diameter?: number | null; // mm
  // Mandrel surface profile (a non-cylindrical surface of revolution, e.g. a Von
  // Kármán nose; schemaVersion 1.2+). Absent means a plain cylinder. Preserved on
  // load/save so profile files round-trip without silent data loss (#345).
  profile?: MandrelProfile | null;
}

export interface Tow {
  width: number; // mm
  thickness: number; // mm
}

export interface HoopLayer {
  terminal: boolean;
}

export interface HelicalLayer {
  wind_angle: number; // degrees (0-90)
  pattern_number: number;
  skip_index: number;
  lock_degrees: number;
  lead_in_mm: number;
  lead_out_degrees: number;
  skip_initial_near_lock: boolean;
  // Non-geodesic friction ratio for a helical layer on a mandrel profile
  // (schemaVersion 1.3+). Absent means geodesic; an explicit 0 is preserved
  // verbatim (not normalized to absent) so the file round-trips byte-faithfully
  // without silent data loss (#345).
  friction_lambda?: number;
}

export interface SkipLayer {
  mandrel_rotation: number; // degrees
}

export type LayerType = "hoop" | "helical" | "skip";

export interface Layer {
  id: string; // UUID for React keys
  type: LayerType;
  hoop?: HoopLayer;
  helical?: HelicalLayer;
  skip?: SkipLayer;
}

/**
 * Canonical default values for a helical layer. Single source of truth shared by
 * createLayer and the GUI<->wind-schema converters so the two never drift.
 */
export const HELICAL_DEFAULTS = {
  wind_angle: 45,
  pattern_number: 3,
  skip_index: 2,
  lock_degrees: 540,
  lead_in_mm: 25,
  lead_out_degrees: 60,
  skip_initial_near_lock: false,
} as const;

// Helper to create layer with defaults
export function createLayer(type: LayerType): Layer {
  const id = crypto.randomUUID();

  switch (type) {
    case "hoop":
      return {
        id,
        type: "hoop",
        hoop: { terminal: false },
      };
    case "helical":
      return {
        id,
        type: "helical",
        helical: { ...HELICAL_DEFAULTS },
      };
    case "skip":
      return {
        id,
        type: "skip",
        skip: { mandrel_rotation: 90 },
      };
  }
}
