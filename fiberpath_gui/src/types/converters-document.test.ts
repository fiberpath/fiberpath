import { describe, it, expect } from "vitest";
import {
  windDefinitionToDocument,
  projectToWindDefinition,
} from "./converters";
import type { WindDefinition } from "./wind-schema";

const sampleWind: WindDefinition = {
  schemaVersion: "1.0",
  mandrelParameters: { diameter: 200, windLength: 600 },
  towParameters: { width: 10, thickness: 0.3 },
  defaultFeedRate: 500,
  layers: [
    { windType: "hoop", terminal: true },
    {
      windType: "helical",
      windAngle: 55,
      patternNumber: 4,
      skipIndex: 3,
      lockDegrees: 540,
      leadInMM: 25,
      leadOutDegrees: 60,
      skipInitialNearLock: false,
    },
    { windType: "skip", mandrelRotation: 120 },
  ],
};

describe("windDefinitionToDocument", () => {
  it("maps mandrel/tow/feed and converts layers (no transient fields)", () => {
    const doc = windDefinitionToDocument(sampleWind);
    expect(doc).toEqual({
      mandrel: { diameter: 200, wind_length: 600 },
      tow: { width: 10, thickness: 0.3 },
      defaultFeedRate: 500,
      layers: expect.any(Array),
    });
    expect(doc.layers).toHaveLength(3);
    expect(doc.layers[0]).toMatchObject({ type: "hoop", hoop: { terminal: true } });
    expect(doc.layers[1]).toMatchObject({
      type: "helical",
      helical: { wind_angle: 55, pattern_number: 4, skip_index: 3 },
    });
    expect(doc.layers[2]).toMatchObject({ type: "skip", skip: { mandrel_rotation: 120 } });
  });

  it("round-trips through projectToWindDefinition", () => {
    const doc = windDefinitionToDocument(sampleWind);
    const back = projectToWindDefinition(doc);
    expect(back.mandrelParameters).toEqual(sampleWind.mandrelParameters);
    expect(back.towParameters).toEqual(sampleWind.towParameters);
    expect(back.defaultFeedRate).toBe(sampleWind.defaultFeedRate);
    expect(back.layers).toEqual(sampleWind.layers);
  });
});

// Regression guard for #344: a reducing-cone .wind (schemaVersion 1.1,
// mandrelParameters.endDiameter) must survive open -> plan/save without the
// small-end being silently stripped (which planned/exported the cone as a
// cylinder and deleted endDiameter on Save).
const coneWind: WindDefinition = {
  schemaVersion: "1.1",
  mandrelParameters: { diameter: 98, windLength: 120, endDiameter: 54 },
  towParameters: { width: 10, thickness: 0.3 },
  defaultFeedRate: 500,
  layers: [
    {
      windType: "helical",
      windAngle: 30,
      patternNumber: 3,
      skipIndex: 1,
      lockDegrees: 360,
      leadInMM: 20,
      leadOutDegrees: 60,
      skipInitialNearLock: false,
    },
  ],
};

describe("cone endDiameter round-trip (#344)", () => {
  it("preserves endDiameter as end_diameter on load", () => {
    const doc = windDefinitionToDocument(coneWind);
    expect(doc.mandrel).toEqual({ diameter: 98, wind_length: 120, end_diameter: 54 });
  });

  it("emits endDiameter and bumps schemaVersion to 1.1 on save/plan", () => {
    const doc = windDefinitionToDocument(coneWind);
    const back = projectToWindDefinition(doc);
    expect(back.schemaVersion).toBe("1.1");
    expect(back.mandrelParameters).toEqual({ diameter: 98, windLength: 120, endDiameter: 54 });
  });

  it("full round-trip keeps endDiameter intact (no data loss)", () => {
    const back = projectToWindDefinition(windDefinitionToDocument(coneWind));
    expect(back.mandrelParameters).toEqual(coneWind.mandrelParameters);
  });

  it("leaves a plain cylinder unchanged (no spurious end_diameter, stays 1.0)", () => {
    const doc = windDefinitionToDocument(sampleWind);
    expect("end_diameter" in doc.mandrel).toBe(false);
    const back = projectToWindDefinition(doc);
    expect(back.schemaVersion).toBe("1.0");
    expect("endDiameter" in back.mandrelParameters).toBe(false);
  });

  it("preserves endDiameter through the visibleLayerCount preview path", () => {
    // The plan/plot preview slices `layers`; the cone small-end must survive it.
    const doc = windDefinitionToDocument(coneWind);
    const back = projectToWindDefinition(doc, 1);
    expect(back.mandrelParameters).toEqual({ diameter: 98, windLength: 120, endDiameter: 54 });
  });

  it("treats endDiameter: null as a cylinder (no end_diameter, back to 1.0)", () => {
    // null == cylinder on the engine side (PositiveFloat | None); the round-trip
    // collapses an explicit null to an absent field, which is semantically equal.
    const nullCone: WindDefinition = {
      ...coneWind,
      mandrelParameters: { diameter: 98, windLength: 120, endDiameter: null },
    };
    const doc = windDefinitionToDocument(nullCone);
    expect("end_diameter" in doc.mandrel).toBe(false);
    expect(projectToWindDefinition(doc).schemaVersion).toBe("1.0");
  });
});

// Regression guard for #345: a Von Kármán nose .wind (mandrelParameters.profile,
// schemaVersion 1.2) with a non-geodesic helical layer (frictionLambda, 1.3) must
// survive open -> plan/save without the profile or friction ratio being silently
// stripped (which planned/exported the nose as a cylinder and dropped frictionLambda).
const vkFrictionWind: WindDefinition = {
  schemaVersion: "1.3",
  mandrelParameters: { diameter: 98, windLength: 300, profile: { type: "vonKarman" } },
  towParameters: { width: 7, thickness: 0.3 },
  defaultFeedRate: 500,
  layers: [
    {
      windType: "helical",
      windAngle: 30,
      patternNumber: 3,
      skipIndex: 1,
      lockDegrees: 360,
      leadInMM: 20,
      leadOutDegrees: 60,
      skipInitialNearLock: false,
      frictionLambda: 0.15,
    },
  ],
};

describe("Von Kármán profile + frictionLambda round-trip (#345)", () => {
  it("preserves profile as mandrel.profile on load", () => {
    const doc = windDefinitionToDocument(vkFrictionWind);
    expect(doc.mandrel).toEqual({
      diameter: 98,
      wind_length: 300,
      profile: { type: "vonKarman" },
    });
  });

  it("preserves frictionLambda as helical.friction_lambda on load", () => {
    const doc = windDefinitionToDocument(vkFrictionWind);
    expect(doc.layers[0].helical?.friction_lambda).toBe(0.15);
  });

  it("emits profile + frictionLambda and bumps schemaVersion to 1.3 on save/plan", () => {
    const back = projectToWindDefinition(windDefinitionToDocument(vkFrictionWind));
    expect(back.schemaVersion).toBe("1.3");
    expect(back.mandrelParameters).toEqual({
      diameter: 98,
      windLength: 300,
      profile: { type: "vonKarman" },
    });
    expect(back.layers[0]).toMatchObject({ windType: "helical", frictionLambda: 0.15 });
  });

  it("full round-trip keeps profile + frictionLambda intact (no data loss)", () => {
    const back = projectToWindDefinition(windDefinitionToDocument(vkFrictionWind));
    expect(back.mandrelParameters).toEqual(vkFrictionWind.mandrelParameters);
    expect(back.layers).toEqual(vkFrictionWind.layers);
  });

  it("a geodesic VK nose (profile, no friction) stays at schemaVersion 1.2", () => {
    const geodesic: WindDefinition = {
      ...vkFrictionWind,
      schemaVersion: "1.2",
      layers: [{ windType: "hoop", terminal: true }],
    };
    const back = projectToWindDefinition(windDefinitionToDocument(geodesic));
    expect(back.schemaVersion).toBe("1.2");
    expect(back.mandrelParameters.profile).toEqual({ type: "vonKarman" });
  });

  it("preserves profile through the visibleLayerCount preview path", () => {
    const back = projectToWindDefinition(windDefinitionToDocument(vkFrictionWind), 1);
    expect(back.mandrelParameters.profile).toEqual({ type: "vonKarman" });
  });

  it("omits profile/frictionLambda for a plain cylinder (no spurious fields)", () => {
    const doc = windDefinitionToDocument(sampleWind);
    expect("profile" in doc.mandrel).toBe(false);
    const back = projectToWindDefinition(doc);
    expect("profile" in back.mandrelParameters).toBe(false);
    expect(back.layers[1]).not.toHaveProperty("frictionLambda");
  });
});
