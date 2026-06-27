# Tech Stack Details

Complete technical specifications for FiberPath GUI technology stack.

## Frontend Stack

### Svelte 5.x

**Why Svelte:**

- Compiler-tracked, fine-grained reactivity (no virtual DOM, no manual render management)
- Components compile to small, direct DOM updates
- Scoped `<style>` per component alongside the global design tokens
- Strong TypeScript support via `lang="ts"` and `svelte-check`

The GUI is a **plain Vite single-page app** rendered inside the Tauri webview.
There is **no SvelteKit** — no router, no SSR, no server endpoints. `main.svelte.ts`
mounts the root `App.svelte` into `#svelte-root`.

**Key Features Used:**

- Runes for reactivity: `$state`, `$derived`, `$effect`, `$props`
- Reactive state classes (`*.svelte.ts`) as app-wide singletons
- Snippets (`{@render ...}`) for composable slots
- Native events (`onclick`, `oninput`) and `class:`/`bind:` directives

**Example (`src/components/forms/MandrelForm.svelte`):**

```svelte
<script lang="ts">
  import { projectSession } from "../../state/project-session.svelte";
  import { parseNumericInput } from "../../lib/numericFields";
  import NumberField from "../../ui/NumberField.svelte";

  const mandrel = $derived(projectSession.document.mandrel);
</script>

<NumberField
  id="mandrel-diameter"
  label="Diameter"
  unit="mm"
  value={mandrel.diameter}
  oninput={(raw) => projectSession.updateMandrel({ diameter: parseNumericInput(raw) })}
/>
```

Reading `projectSession.document.mandrel` inside `$derived` subscribes the
component to exactly that value — when the diameter changes, only the affected
DOM updates. There is no selector layer and no memoization to manage.

### TypeScript 6.x

**Why TypeScript:**

- Catch errors at compile time
- IntelliSense for better DX
- Refactoring confidence
- Self-documenting interfaces

**Configuration:** (`tsconfig.json`)

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  }
}
```

**Key Patterns:**

- Discriminated unions for layer types
- Strict null checks
- Exhaustive switch statements
- Type guards for runtime safety

Two type-check gates run because two file kinds carry types:

- `npm run lint` → `tsc --noEmit` covers plain `.ts` modules.
- `npm run check:svelte` → `svelte-check` covers `.svelte` components and the
  `.svelte.ts` reactive state modules.

### Vite 8.x

**Why Vite:**

- Instant dev server startup with ESM
- Lightning-fast HMR (Hot Module Replacement)
- Optimized production builds with Rollup
- Native TypeScript support

**Configuration:** (`vite.config.ts`)

```typescript
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte()],
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
```

**Performance:**

- Dev server starts in <1 second
- HMR updates in ~50ms
- Production build in ~10 seconds

### Reactive State (Svelte runes)

State lives in **reactive classes** under `src/state/*.svelte.ts`, exported as
app-wide singletons. This replaces the previous Zustand stores.

**Why runes classes:**

- No store library, no provider, no selector boilerplate
- `$state` fields are deeply reactive; `$derived` computes update automatically
- Persisted vs. transient state is separated explicitly (see
  [State Management](state-management.md))
- Plain class methods replace action creators

**Pattern (`src/state/project-session.svelte.ts`):**

```typescript
export class ProjectSession {
  document = $state<ProjectDocument>(createEmptyDocument());
  filePath = $state<string | null>(null);
  selectedLayerId = $state<string | null>(null);

  // Dirtiness is derived from a revision counter, not a boolean toggled on
  // every mutation (one less thing to forget).
  revision = $state(0);
  savedRevision = $state(0);
  readonly isDirty = $derived(this.revision !== this.savedRevision);

  updateMandrel(patch: Partial<Mandrel>) {
    Object.assign(this.document.mandrel, patch);
    this.revision++;
  }
}

export const projectSession = new ProjectSession();
```

### Zod 4.x

**Why Zod:**

- Runtime validation with TypeScript inference
- Composable schemas
- Clear error messages
- JSON schema generation

**Schema Definition:**

```typescript
export const MandrelParametersSchema = z.object({
  diameter: z.number().positive(),
  windLength: z.number().positive(),
});
// TypeScript type inferred automatically
export type MandrelParameters = z.infer<typeof MandrelParametersSchema>;
```

**Validation:**

```typescript
const result = MandrelParametersSchema.safeParse(data);
if (!result.success) {
  console.error(result.error.issues);
  // [{ code: 'too_small', minimum: 0, path: ['diameter'], message: '...' }]
}
```

### Layer reordering (native drag + keyboard)

Layer reordering is implemented with **native HTML5 drag-and-drop plus keyboard
arrows** in `src/components/layers/LayerList.svelte` — no drag-and-drop library.

```svelte
<li
  draggable="true"
  ondragstart={() => (dragIndex = index)}
  ondragover={(e) => e.preventDefault()}
  ondrop={(e) => { e.preventDefault(); onDrop(index); }}
>
  <span
    class="row__handle"
    role="button"
    tabindex="0"
    onkeydown={(e) => onHandleKey(e, index)}>⋮⋮</span
  >
</li>
```

`onHandleKey` moves the row with ArrowUp/ArrowDown for accessibility; both paths
call `projectSession.reorderLayers(from, to)`.

### Viewport pan/zoom (native controller)

The toolpath preview viewport uses a small framework-neutral transform module,
`src/lib/panzoom.ts`, instead of a pan/zoom library. It exposes pure functions
(`zoomAt`, `pan`, `centered`, `clampScale` with `MIN_SCALE`/`MAX_SCALE`) that
`Viewport.svelte` applies as a CSS `transform`.

## Desktop Shell

### Tauri 2.x

**Why Tauri:**

- Small bundle size (~3-5 MB vs Electron's ~120 MB)
- Native webview (no embedded Chromium)
- Rust security and performance
- Cross-platform (Windows, macOS, Linux)

**Architecture:**

```text
┌────────────────────────────────┐
│     WebView (Svelte UI)        │  JavaScript
├────────────────────────────────┤
│  Tauri IPC (invoke/listen)     │  Async bridge
├────────────────────────────────┤
│   Rust Backend (Commands)      │  Rust
│   - File I/O                   │
│   - Sidecar supervision        │
│   - Serial port access         │
└────────────────────────────────┘
```

**Key Features:**

- **Commands:** Rust functions callable from JavaScript
- **Events:** Pub/sub for streaming updates
- **File System:** Secure path resolution
- **Updater:** Auto-update mechanism (v0.5.0+)

**Security Model:**

- Allowlist of permitted APIs
- No eval() or inline scripts
- CSP headers enforced
- Path traversal protection

### Rust 1.70+

**Why Rust:**

- Memory safety without garbage collection
- Zero-cost abstractions
- Fearless concurrency
- Strong type system

The Rust shell supervises the FastAPI compute sidecar and drives the Marlin
serial path. See [CLI Integration Details](cli-integration.md) for the backend
architecture and [Streaming State](streaming-state.md) for the Marlin state
manager.

## Testing Stack

### Vitest

**Why Vitest:**

- Vite-native (same config, fast startup)
- Jest-compatible API
- ES modules support
- Watch mode with HMR

**Features:**

- Parallel test execution
- Coverage with v8
- Snapshot testing
- UI mode for exploration

### Svelte Testing Library

**Why @testing-library/svelte:**

- Focus on user behavior, not implementation
- Accessible queries (getByRole, getByLabelText)
- Async utilities (waitFor, findBy)
- Its `svelteTesting()` Vite plugin handles component cleanup between tests

**Example:**

```typescript
import { render, screen, fireEvent } from "@testing-library/svelte";
import MandrelForm from "./MandrelForm.svelte";

it("should update mandrel diameter", async () => {
  render(MandrelForm);
  const input = screen.getByLabelText("Diameter");
  await fireEvent.input(input, { target: { value: "200" } });
  expect((input as HTMLInputElement).value).toBe("200");
});
```

## Build Tools

### TypeScript Compiler (tsc) + svelte-check

Static analysis runs in two gates:

- `npm run lint` → `tsc --noEmit` for `.ts` modules.
- `npm run check:svelte` → `svelte-check` for `.svelte` and `.svelte.ts` files.

**Key Flags (tsconfig):**

- `strict: true` - All strict checks
- `noUncheckedIndexedAccess: true` - Array access safety
- `noUnusedLocals: true` - Dead code detection

### Stylelint 17.x

CSS quality is enforced through:

- `npm run lint:css` - standard CSS lint checks
- `npm run lint:css:vars` - verifies referenced CSS variables are defined

### Rustfmt + Clippy

Tauri-side Rust quality gates are part of the GUI workflow:

- `npm run format:check` - `cargo fmt --check`
- `npm run clippy` - `cargo clippy -- -D warnings`

## Version Matrix

| Package                      | Version | Purpose                |
| ---------------------------- | ------- | ---------------------- |
| svelte                       | 5.56.4  | UI framework           |
| @sveltejs/vite-plugin-svelte | 7.1.2   | Svelte build/HMR       |
| svelte-check                 | 4.7.1   | `.svelte` type checks  |
| typescript                   | 6.0.3   | Type safety            |
| vite                         | 8.1.0   | Build tool             |
| zod                          | 4.4.3   | Runtime validation     |
| @tauri-apps/api              | 2.11.1  | Tauri bindings         |
| openapi-fetch                | 0.14.1  | Typed sidecar client   |
| vitest                       | 4.1.4   | Test runner            |
| @testing-library/svelte      | 5.4.2   | Component testing       |
| stylelint                    | 17.13.0 | CSS linting            |

## Platform Support

### Windows

- **Minimum:** Windows 10 1809+
- **Webview:** Edge WebView2 (bundled)
- **Installer:** MSI

### macOS

- **Minimum:** macOS 10.15 Catalina
- **Webview:** WKWebView (native)
- **Installer:** DMG

### Linux

- **Minimum:** Ubuntu 20.04, Fedora 36, Arch (current)
- **Webview:** webkit2gtk 4.1
- **Installer:** AppImage, DEB

## Performance Characteristics

### Bundle Size

- **Production JS:** ~308 kB (down from ~599 kB under React — a 48% drop, mostly
  from removing the React runtime, Zustand, and the drag-and-drop/pan-zoom libs)
- **Production CSS:** ~64 kB
- **Tauri shell:** ~3-5 MB
- **Installer:** ~10-15 MB

### Startup Time

- **Cold start:** ~1-2 seconds
- **Warm start:** ~500ms

### Memory Usage

- **Idle:** ~50-80 MB
- **Active:** ~100-150 MB
- **Heavy use:** ~200-300 MB

### Build Time

- **Dev server:** <1 second
- **HMR update:** ~50ms
- **Production build:** ~10-15 seconds
- **Full rebuild:** ~20-30 seconds

## Next Steps

- [State Management Architecture](state-management.md)
- [CLI Integration Details](cli-integration.md)
- [Performance Guide](../guides/performance.md)
