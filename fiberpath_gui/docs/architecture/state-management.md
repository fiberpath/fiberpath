# State Management Architecture

Complete guide to state management in FiberPath GUI using Svelte 5 runes.

## Overview

FiberPath GUI manages state with **Svelte 5 reactive classes** (runes), not a
store library. Each concern is a class in `src/state/*.svelte.ts` exported as an
app-wide singleton. Components import a singleton and read its `$state`/`$derived`
fields directly; reads inside a component or a `$derived` subscribe to exactly
the values touched, so updates are fine-grained without selectors.

## The state modules

| Singleton        | Module                              | Responsibility                                                      |
| ---------------- | ----------------------------------- | ------------------------------------------------------------------ |
| `projectSession` | `project-session.svelte.ts`         | The open project: persisted `ProjectDocument` + transient session  |
| `uiState`        | `ui-state.svelte.ts`                | Shell UI (active workspace, panel/drawer visibility, open dialog)  |
| `machineSession` | `machine-session.svelte.ts`         | Marlin connection, streaming, manual control, log                  |
| `previewSession` | `preview-session.svelte.ts`         | Toolpath preview generation (plan → PNG) with stale-request guard  |
| `notifications`  | `notifications.svelte.ts`           | Transient toast notifications                                      |
| `theme`          | `theme.svelte.ts`                   | Theme preference + system resolution                              |
| `cliHealth`      | `cli-health.svelte.ts`              | Backend/CLI health polling                                        |

Logic that used to live in React custom hooks now lives in these modules, in
plain service functions (`src/services/*`), or in component event handlers.

## Persisted vs. transient: `ProjectSession`

The biggest design point is the split between what round-trips to a `.wind` file
and what is session-only.

### `ProjectDocument` (persisted)

`ProjectDocument` (`src/types/document.ts`) is a plain domain type — no Svelte —
so the tsc-checked modules (converters, services) and the runes session can share
it. It is **exactly** the `.wind` payload:

```typescript
export interface ProjectDocument {
  mandrel: Mandrel; // { diameter, wind_length }
  tow: Tow; // { width, thickness }
  layers: Layer[];
  defaultFeedRate: number;
}
```

No `filePath`, `isDirty`, or selection lives in the document.

### Session wrapper (transient)

```typescript
export class ProjectSession {
  document = $state<ProjectDocument>(createEmptyDocument());
  filePath = $state<string | null>(null);
  selectedLayerId = $state<string | null>(null);
  validationErrors = $state<UiValidationErrors>({});

  /** Bumped on every document mutation; compared against savedRevision. */
  revision = $state(0);
  savedRevision = $state(0);

  readonly isDirty = $derived(this.revision !== this.savedRevision);

  readonly selectedLayer = $derived(
    this.document.layers.find((l) => l.id === this.selectedLayerId) ?? null,
  );
}

export const projectSession = new ProjectSession();
```

### Revision-based dirty tracking

Instead of setting `isDirty: true` in every action (easy to forget), dirtiness is
**derived**: each document mutation bumps `revision`, and `isDirty` is
`revision !== savedRevision`. Saving calls `markSaved()`, which sets
`savedRevision = revision`. Loading a document resets both to `0`.

```typescript
markSaved() {
  this.savedRevision = this.revision;
}

loadDocument(document: ProjectDocument, filePath: string | null = null) {
  this.document = document;
  this.filePath = filePath;
  this.selectedLayerId = null;
  this.validationErrors = {};
  this.revision = 0;
  this.savedRevision = 0;
}
```

## Mutating state

Because `$state` is deeply reactive, methods mutate in place and bump the
revision — no spread-and-replace dance.

### Update partial state

```typescript
updateMandrel(patch: Partial<Mandrel>) {
  Object.assign(this.document.mandrel, patch);
  this.revision++;
}
```

### Add to array

```typescript
addLayer(type: LayerType): string {
  const layer = createLayer(type);
  this.document.layers.push(layer);
  this.selectedLayerId = layer.id;
  this.revision++;
  return layer.id;
}
```

`push` is observed directly. The new ID is returned for the UI. Selection is
session-only, so changing it alone does **not** bump the revision.

### Remove from array

```typescript
removeLayer(id: string) {
  const index = this.document.layers.findIndex((l) => l.id === id);
  if (index === -1) return;
  this.document.layers.splice(index, 1);
  if (this.selectedLayerId === id) {
    this.selectedLayerId = this.document.layers[0]?.id ?? null;
  }
  this.revision++;
}
```

### Reorder array

```typescript
reorderLayers(from: number, to: number) {
  const layers = this.document.layers;
  if (from === to) return;
  const [moved] = layers.splice(from, 1);
  layers.splice(to, 0, moved);
  this.revision++;
}
```

## Usage in components

A component reads the singleton's reactive fields. Wrapping a read in `$derived`
makes it track that value and nothing else.

```svelte
<script lang="ts">
  import { projectSession } from "../../state/project-session.svelte";

  const mandrel = $derived(projectSession.document.mandrel);
</script>

<input
  value={mandrel.diameter}
  oninput={(e) => projectSession.updateMandrel({ diameter: +e.currentTarget.value })}
/>
```

Two inputs reading two different fields update independently — the compiler
tracks the dependencies, so there is no selector and no shallow-comparison helper
to reach for. Derived values like `projectSession.selectedLayer` and
`projectSession.isDirty` recompute only when their inputs change.

## Transient UI state: `UiState`

Shell chrome that should never be saved lives in its own singleton — what was a
scatter of `useState` flags in the React `App`:

```typescript
export class UiState {
  workspace = $state<WorkspaceId>("prepare"); // "prepare" | "machine"
  leftCollapsed = $state(false);
  rightCollapsed = $state(false);
  drawerOpen = $state(false);
  activeDialog = $state<"about" | "diagnostics" | null>(null);

  setWorkspace(id: WorkspaceId) {
    this.workspace = id;
  }
  toggleLeft() {
    this.leftCollapsed = !this.leftCollapsed;
  }
}

export const uiState = new UiState();
```

## Derived state

Prefer `$derived` over recomputing in markup or methods:

```typescript
readonly isHealthy = $derived(this.status === "ready");
readonly canStartStream = $derived(Boolean(this.filePath) && this.isConnected);
```

For one-off display values, deriving inline in the component is fine; for values
reused by methods, declare a `$derived` field on the class.

## Testing state

Each singleton's class is exported so tests can instantiate a fresh, isolated
instance — no global reset hook needed:

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { ProjectSession, createEmptyDocument } from "./project-session.svelte";

describe("ProjectSession", () => {
  let session: ProjectSession;
  beforeEach(() => {
    session = new ProjectSession();
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

Component tests drive the shared singleton and reset it in `beforeEach`:

```typescript
import { projectSession } from "../../state/project-session.svelte";
beforeEach(() => {
  projectSession.newDocument();
});
```

## Common Pitfalls

### Reading a singleton field non-reactively

Destructuring a `$state` field into a local `const` at the top of `<script>`
captures a snapshot. Wrap reads you want to stay live in `$derived` (or read
`projectSession.document.x` directly in markup).

### Putting transient state in the document

`ProjectDocument` is the `.wind` payload. Selection, dirtiness, file path, and UI
flags belong on the session/`UiState`, not in the document.

### Forgetting the revision bump

Document mutations must `this.revision++` so `isDirty` and any document-derived
preview/validation react. Session-only changes (selection) intentionally do not.

## Next Steps

- [CLI Integration](cli-integration.md) - State → backend bridge
- [Schema Validation](../guides/schemas.md) - Zod integration
- [Testing Guide](../testing.md) - State testing patterns
