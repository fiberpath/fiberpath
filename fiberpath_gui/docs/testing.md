# Testing Guide

Comprehensive testing documentation for FiberPath GUI test suite.

## Test Stack

- **Framework:** Vitest (Vite-native test runner)
- **Assertions:** Expect API (Jest-compatible) + `@testing-library/jest-dom` matchers
- **Component testing:** `@testing-library/svelte`
- **Environment:** jsdom (simulated DOM)
- **Coverage:** v8 provider

Component cleanup between tests is handled automatically by the
`@testing-library/svelte` Vite plugin (`svelteTesting()`), wired in
`vitest.config.ts` alongside the `svelte()` plugin. The setup file
(`src/tests/setup.ts`) only extends `expect` with the jest-dom matchers and mocks
`crypto.randomUUID` / `window.matchMedia`.

## Running Tests

### All Tests

```sh
npm test
```

Runs all tests in `src/**/*.{test,spec}.{ts,tsx}` and displays summary.

### Watch Mode

```sh
npm test -- --watch
```

Re-runs tests on file changes. Useful during development.

### Specific Test File

```sh
npm test -- schemas.test.ts
npm test -- validation.test.ts
npm test -- project-session.svelte.test.ts
```

### With Coverage

```sh
npm test -- --coverage
```

Generates coverage report in `coverage/` directory.

### UI Mode

```sh
npm test -- --ui
```

Opens interactive test UI in browser for exploring tests and results.

## Test Organization

Tests live next to the code they cover. Reactive state modules and services use
the `.svelte.ts` suffix, so their tests are `*.svelte.test.ts`; component tests
are `*.svelte.test.ts` beside each `.svelte` file.

```sh
src/
├── lib/
│   ├── schemas.test.ts            # Zod schema validation
│   ├── validation.test.ts         # JSON schema validation (AJV)
│   └── panzoom.test.ts            # Viewport transform math
├── state/
│   ├── project-session.svelte.test.ts   # Project session (document + dirty tracking)
│   ├── machine-session.svelte.test.ts   # Marlin streaming session
│   ├── preview-session.svelte.test.ts   # Preview generation
│   └── ...                              # ui-state, theme, notifications, cli-health
├── services/
│   └── file-operations.svelte.test.ts   # File open/save/export flows
├── types/
│   └── converters.test.ts         # Document ↔ wind-definition conversion
└── components/
    ├── forms/MandrelForm.svelte.test.ts
    ├── layers/LayerList.svelte.test.ts
    └── ...                        # editors, dialogs, machine panels
```

## Writing Tests

### Schema Validation Tests

**Purpose:** Verify Zod schemas accept valid data and reject invalid data.

```typescript
import { describe, it, expect } from "vitest";
import { MandrelParametersSchema } from "./schemas";
describe("MandrelParametersSchema", () => {
  it("should validate correct mandrel parameters", () => {
    const valid = { diameter: 150, windLength: 800 };
    const result = MandrelParametersSchema.safeParse(valid);
    expect(result.success).toBe(true);
  });
  it("should reject negative diameter", () => {
    const invalid = { diameter: -10, windLength: 800 };
    const result = MandrelParametersSchema.safeParse(invalid);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues[0].message).toContain("positive");
    }
  });
});
```

### State Tests

**Purpose:** Verify reactive state classes update correctly. Because each state
module exports its class, tests instantiate a fresh, isolated instance.

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { ProjectSession, createEmptyDocument } from "./project-session.svelte";

describe("ProjectSession", () => {
  let session: ProjectSession;
  beforeEach(() => {
    session = new ProjectSession();
  });

  it("starts from the canonical empty document", () => {
    expect(session.document).toEqual(createEmptyDocument());
    expect(session.document.mandrel.diameter).toBe(150);
  });

  it("is not dirty until a mutation, then dirty until saved", () => {
    expect(session.isDirty).toBe(false);
    session.updateMandrel({ diameter: 200 });
    expect(session.isDirty).toBe(true);
    session.markSaved();
    expect(session.isDirty).toBe(false);
  });
});
```

> `.svelte.test.ts` files run through the Svelte compiler, so runes (`$state`,
> `$derived`) work inside the class under test — that's why state tests carry the
> `.svelte` suffix.

### Component Tests

**Purpose:** Verify Svelte components render correctly and handle interactions.
Pass the component (and any props) to `render`; drive the shared state singleton
and reset it in `beforeEach`.

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import MandrelForm from "./MandrelForm.svelte";
import { projectSession } from "../../state/project-session.svelte";

beforeEach(() => {
  projectSession.newDocument();
});

describe("MandrelForm.svelte", () => {
  it("shows the current diameter from the session", () => {
    projectSession.document.mandrel.diameter = 200;
    render(MandrelForm);
    const input = screen.getByLabelText("Diameter") as HTMLInputElement;
    expect(input.value).toBe("200");
  });

  it("updates the mandrel when the diameter input changes", async () => {
    render(MandrelForm);
    const input = screen.getByLabelText("Diameter");
    await fireEvent.input(input, { target: { value: "180" } });
    expect(projectSession.document.mandrel.diameter).toBe(180);
  });
});
```

For props, pass them as the second argument: `render(NumberField, { id, label, value, oninput })`.

### Integration Tests

**Purpose:** Test complete flows across state, services, and conversion.

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { projectSession } from "../state/project-session.svelte";

describe("Prepare workflow", () => {
  beforeEach(() => projectSession.newDocument());

  it("creates a project, adds a layer, and updates the mandrel", () => {
    const id = projectSession.addLayer("helical");
    projectSession.updateLayer(id, { helical: { wind_angle: 45 } as any });
    projectSession.updateMandrel({ diameter: 200, wind_length: 1000 });

    expect(projectSession.document.layers).toHaveLength(1);
    expect(projectSession.document.mandrel.diameter).toBe(200);
    expect(projectSession.isDirty).toBe(true);
  });
});
```

## Test Patterns

### Valid/Invalid Data Pairs

For every schema, test both valid and invalid inputs:

```typescript
describe("HelicalLayerSchema", () => {
  const validCases = [
    { windAngle: 45, terminal: false },
    { windAngle: 30, terminal: true, skipEvery: 2 },
  ];
  const invalidCases = [
    { windAngle: 100, terminal: false }, // Angle > 90
    { windAngle: -10, terminal: false }, // Negative angle
  ];
  validCases.forEach((data, i) => {
    it(`should accept valid case ${i + 1}`, () => {
      expect(HelicalLayerSchema.safeParse(data).success).toBe(true);
    });
  });
  invalidCases.forEach((data, i) => {
    it(`should reject invalid case ${i + 1}`, () => {
      expect(HelicalLayerSchema.safeParse(data).success).toBe(false);
    });
  });
});
```

### Mocking Tauri Commands

When testing state/services that call Tauri commands, mock `@tauri-apps/api/core`:

```typescript
import { vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";
vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

it("streams via the Marlin bridge", async () => {
  vi.mocked(invoke).mockResolvedValue({ /* StreamSummary */ });
  await streamProgram("out.gcode", { baudRate: 115200, dryRun: true });
  expect(invoke).toHaveBeenCalledWith(
    "stream_program",
    expect.objectContaining({ gcodePath: "out.gcode" }),
  );
});
```

Compute wrappers are tested against a mocked `openapi-fetch` client — see
[CLI Integration](architecture/cli-integration.md).

### Testing Error Handling

Verify components surface errors:

```typescript
it("shows a backend validation error for diameter", () => {
  projectSession.setValidationError("mandrel.diameter", "Too small");
  render(MandrelForm);
  expect(screen.getByText("Too small")).toBeInTheDocument();
});
```

### Testing Debounced Behavior

Use `waitFor` to assert state that lands after a debounce window:

```typescript
import { waitFor } from "@testing-library/svelte";
it("live-validates after the debounce window", async () => {
  render(MandrelForm);
  await fireEvent.input(screen.getByLabelText("Diameter"), { target: { value: "0" } });
  await waitFor(() =>
    expect(screen.getByText("Diameter must be greater than 0")).toBeInTheDocument(),
  );
});
```

## Coverage Goals

Coverage thresholds are enforced in `vitest.config.ts`:

- **Lines:** 60%+
- **Functions:** 65%+
- **Branches:** 50%+
- **Statements:** 60%+

### Critical Areas (high coverage expected)

- Schema validation (`src/lib/schemas.ts`)
- Error handling (`src/lib/validation.ts`)
- Project session (`src/state/project-session.svelte.ts`)

### Lower Priority

- Presentational components (focus on critical paths)
- Type definitions

## Debugging Tests

### View Test Output

```sh
npm test -- --reporter=verbose
```

### Debug Single Test

```typescript
it.only("should validate mandrel", () => {
  // This is the only test that will run
});
```

### Print Debug Info

```typescript
it("updates state", () => {
  session.updateMandrel({ diameter: 200 });
  console.log("Document:", session.document);
  expect(session.document.mandrel.diameter).toBe(200);
});
```

### Use Vitest UI

```sh
npm test -- --ui
```

Opens a browser UI showing the test hierarchy, pass/fail status, console output,
coverage, and re-run buttons.

## CI Integration

Tests run automatically on every push and PR via GitHub Actions:

```yaml
- name: Run tests
  run: npm test -- --run
```

**PR Requirements:**

- All tests must pass
- No new `tsc`/`svelte-check` type errors
- Coverage must not drop below the configured thresholds

## Common Issues

### "Cannot find module '@/lib/schemas'"

**Solution:** Check the path alias in `vitest.config.ts`:

```typescript
resolve: {
  alias: {
    '@': path.resolve(__dirname, './src'),
  },
}
```

### Runes don't work in a test

**Solution:** Code using `$state`/`$derived` must compile through Svelte. Name the
file `*.svelte.test.ts` (and the module under test `*.svelte.ts`) so the Svelte
plugin processes it.

### Tests fail but the app works

**Solution:** You may be asserting implementation details. Prefer visible behavior:

```typescript
// Avoid: asserting private internals
// Prefer: asserting rendered output
expect(screen.getByText("Count: 1")).toBeInTheDocument();
```

### Mock not working

**Solution:** Ensure `vi.mock` is hoisted above imports:

```typescript
vi.mock("@tauri-apps/api/core"); // Must be at top
```

## Next Steps

- [Schema Validation Guide](guides/schemas.md) - Writing schemas
- [State Management](architecture/state-management.md) - State patterns
- [Type Safety](reference/type-safety.md) - TypeScript patterns
