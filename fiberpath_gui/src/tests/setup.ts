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
