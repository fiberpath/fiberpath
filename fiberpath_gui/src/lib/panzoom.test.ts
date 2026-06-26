import { describe, it, expect } from "vitest";
import {
  zoomAt,
  pan,
  centered,
  clampScale,
  MIN_SCALE,
  MAX_SCALE,
  type Transform,
} from "./panzoom";

const screenOf = (t: Transform, contentX: number, contentY: number) => ({
  x: t.x + contentX * t.scale,
  y: t.y + contentY * t.scale,
});

describe("panzoom", () => {
  it("clamps scale to [MIN, MAX]", () => {
    expect(clampScale(0.01)).toBe(MIN_SCALE);
    expect(clampScale(100)).toBe(MAX_SCALE);
    expect(clampScale(2)).toBe(2);
  });

  it("zooms while keeping the cursor point visually fixed", () => {
    const t: Transform = { scale: 1, x: 30, y: 10 };
    const px = 120;
    const py = 80;
    // content point currently under the cursor
    const cp = { x: (px - t.x) / t.scale, y: (py - t.y) / t.scale };

    const z = zoomAt(t, px, py, 2);
    expect(z.scale).toBe(2);
    const after = screenOf(z, cp.x, cp.y);
    expect(after.x).toBeCloseTo(px);
    expect(after.y).toBeCloseTo(py);
  });

  // #147: a plot SMALLER than the viewport must zoom up (no clamp to image bounds).
  it("zooms a small image up to MAX_SCALE", () => {
    let t: Transform = { scale: 1, x: 0, y: 0 };
    for (let i = 0; i < 100; i++) t = zoomAt(t, 50, 50, 1.5);
    expect(t.scale).toBe(MAX_SCALE);
  });

  // #147: a plot LARGER than the viewport must pan freely to reveal overflow —
  // translate is never clamped to bounds.
  it("pans without bounding the translation", () => {
    const t = pan({ scale: 4, x: 0, y: 0 }, -100000, 50000);
    expect(t.x).toBe(-100000);
    expect(t.y).toBe(50000);
    expect(t.scale).toBe(4);
  });

  it("centers content within the viewport", () => {
    // 200x100 content at scale 1 in a 1000x400 viewport
    expect(centered(1000, 400, 200, 100, 1)).toEqual({ scale: 1, x: 400, y: 150 });
  });
});
