import { describe, expect, it } from "vitest";
import { createLayer } from "./project";

describe("createLayer()", () => {
  it("creates a hoop layer with expected defaults", () => {
    const layer = createLayer("hoop");
    expect(layer.type).toBe("hoop");
    expect(layer.hoop).toBeDefined();
    expect(layer.hoop?.terminal).toBe(false);
  });

  it("creates a helical layer with expected defaults", () => {
    const layer = createLayer("helical");
    expect(layer.type).toBe("helical");
    expect(layer.helical).toBeDefined();
    expect(layer.helical?.wind_angle).toBe(45);
    expect(layer.helical?.pattern_number).toBe(3);
  });

  it("creates a skip layer with expected defaults", () => {
    const layer = createLayer("skip");
    expect(layer.type).toBe("skip");
    expect(layer.skip).toBeDefined();
    expect(layer.skip?.mandrel_rotation).toBe(90);
  });

  it("assigns a unique id to each created layer", () => {
    const a = createLayer("hoop");
    const b = createLayer("hoop");
    expect(a.id).toBeTruthy();
    expect(a.id).not.toBe(b.id);
  });
});
