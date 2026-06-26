/**
 * Framework-neutral pan/zoom transform math for an image viewport, replacing
 * react-zoom-pan-pinch. Applied as `transform: translate(x px, y px) scale(s)`
 * with `transform-origin: 0 0`.
 *
 * Fixes #147: translate is NEVER clamped to the image/container bounds (pan to
 * any overflow freely), and scale is clamped only to [MIN, MAX] — so a plot
 * larger than the viewport can be panned to, and one smaller can be zoomed up.
 */
export interface Transform {
  scale: number;
  x: number;
  y: number;
}

export const MIN_SCALE = 0.1;
export const MAX_SCALE = 8;

export function clampScale(scale: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
}

/** Zoom by `factor` keeping the viewport point (px, py) visually fixed. */
export function zoomAt(t: Transform, px: number, py: number, factor: number): Transform {
  const scale = clampScale(t.scale * factor);
  const k = scale / t.scale; // actual factor after clamping
  return {
    scale,
    x: px - (px - t.x) * k,
    y: py - (py - t.y) * k,
  };
}

/** Translate by a screen-space delta (unbounded — this is the #147 fix). */
export function pan(t: Transform, dx: number, dy: number): Transform {
  return { scale: t.scale, x: t.x + dx, y: t.y + dy };
}

/** Center content of size (cw, ch) at `scale` within a viewport of (vw, vh). */
export function centered(
  vw: number,
  vh: number,
  cw: number,
  ch: number,
  scale = 1,
): Transform {
  return { scale, x: (vw - cw * scale) / 2, y: (vh - ch * scale) / 2 };
}
