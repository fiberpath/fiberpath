import { expect, vi } from "vitest";
import * as matchers from "@testing-library/jest-dom/matchers";

// Extend Vitest's expect with jest-dom matchers. Component cleanup after each
// test is handled by the @testing-library/svelte vite plugin (svelteTesting()).
expect.extend(matchers);

// The app's primary runtime is the Tauri webview, so isTauri() (and the
// invokeBackend guard) should resolve true by default in tests. Suites that
// exercise the backend-less browser preview delete this global themselves.
(window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ ??= {};

// Mock crypto.randomUUID for tests
if (!global.crypto) {
  (global as any).crypto = {
    randomUUID: () =>
      `test-uuid-${Math.random().toString(36).substring(2, 15)}`,
  };
}

// jsdom implements no Web Animations API. Svelte calls element.animate() when a
// transition runs, and from 5.57 it does so from a deferred microtask, so the
// TypeError escapes the test that triggered it and fails the run even though
// every assertion passes. Hand transitions an inert Animation instead:
// playState "finished" stops Svelte's rAF loop immediately, and onfinish is
// left unfired so transitions stay no-ops rather than half-applying.
if (!Element.prototype.animate) {
  Element.prototype.animate = () =>
    ({
      onfinish: null,
      oncancel: null,
      effect: null,
      playState: "finished",
      cancel: () => {},
      finish: () => {},
      play: () => {},
      pause: () => {},
    }) as unknown as Animation;
}

// Mock window.matchMedia
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
