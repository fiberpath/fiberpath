# Performance Guide

Complete guide to profiling and optimizing FiberPath GUI performance.

## Overview

FiberPath GUI is built on Svelte 5, whose compiler tracks reactivity at the level
of individual values. There is no virtual DOM diff and no render-management layer
to tune — updates touch only the DOM nodes that depend on the changed state. The
optimization work that dominated the React build (selectors, `memo`, debounced
re-renders) is gone; this guide focuses on what still matters: bundle size, lazy
work, and keeping reactive dependencies tight.

## Bundle Baseline and Budget

Baseline values are tracked in `fiberpath_gui/perf/bundle-baseline.json` and
enforced in CI with `npm run perf:bundle` (`scripts/check-bundle-budget.mjs`).

| Metric           | Baseline   | Source                                          |
| ---------------- | ---------- | ----------------------------------------------- |
| Total JS bundle  | ~308 kB    | React → Svelte 5 cutover snapshot (2026-06-26)  |
| Total CSS bundle | ~64 kB     | React → Svelte 5 cutover snapshot (2026-06-26)  |

The JS total dropped ~48% (from ~599 kB) at the cutover: removing the React
runtime, Zustand, `@hello-pangea/dnd`, and `react-zoom-pan-pinch` more than paid
for Svelte's (tiny) runtime, and the compiler emits less per-component code.

Bundle guardrail policy (from `bundle-baseline.json`):

- Regression limit: +15% over baseline for JS/CSS totals
- Absolute cap: 400 kB JS, 80 kB CSS
- CI artifact: `gui-bundle-metrics` (`fiberpath_gui/perf/reports/bundle-metrics.json`)
- Preview caching policy: no persistent cache (a monotonic request-id guard in
  `previewSession` drops stale responses instead).

## Profiling Tools

### Browser Performance Tab

The Tauri webview is Chromium/WebKit, so the browser DevTools Performance panel
is the primary profiler.

**Recording:**

1. Open DevTools → Performance tab
2. Click record
3. Perform actions (add layers, edit mandrel, scrub the preview)
4. Stop recording

**Analysis:**

- **Main thread:** JavaScript execution, layout, paint
- **Frames:** Green = good (60fps), red = dropped frames
- **Summary:** Time breakdown (scripting, rendering, painting)

**Look for:**

- Long tasks (>50ms)
- Layout thrashing
- Excessive repaints

Because Svelte updates are surgical, "wasted render" hunting is rarely the
problem — look instead for expensive synchronous work in event handlers or
`$effect`s.

### Vite Build Analyzer

**Analyze Bundle Size:**

```sh
npm run build
```

Generates `dist/assets/*.js` files with size reports.

**Identify Large Dependencies:**

```sh
npx vite-bundle-visualizer
```

Opens interactive visualization of bundle contents.

## Optimization Patterns

### 1. Keep `$derived` dependencies tight

`$derived` recomputes only when the values it reads change. Read the narrowest
thing you need so derivations don't recompute on unrelated updates.

```svelte
<script lang="ts">
  import { projectSession } from "../../state/project-session.svelte";

  // ✅ Tracks only the layers array
  const layerCount = $derived(projectSession.document.layers.length);
</script>
```

There is no selector or shallow-comparison helper to configure — the compiler
derives the dependency graph from your reads.

### 2. Derive expensive transforms with `$derived`

Sorting/filtering belongs in a `$derived`, which memoizes by dependency:

```svelte
<script lang="ts">
  const sorted = $derived([...layers].sort((a, b) => a.index - b.index));
</script>

{#each sorted as layer (layer.id)}
  <LayerRow {layer} />
{/each}
```

The sort runs only when `layers` changes, not on every unrelated update. Always
key `{#each}` blocks with a stable id so Svelte moves DOM nodes instead of
rebuilding them.

### 3. Debounce expensive side effects

Debouncing still matters for work that hits the backend or does heavy computation
(preview regeneration, validation). Use the shared `debounce` helper
(`src/lib/debounce.ts`) in the event handler — not a re-render hook:

```svelte
<script lang="ts">
  import { debounce } from "../../lib/debounce";
  import { projectSession } from "../../state/project-session.svelte";

  const validate = debounce((v: number) => {
    errors = { ...errors, diameter: validateDiameter(v) };
  });

  function onInput(raw: string) {
    const value = parseNumericInput(raw);
    projectSession.updateMandrel({ diameter: value }); // state updates immediately
    validate(value); // validation is debounced
  }
</script>
```

### 4. Drop stale async results

For async work that can be superseded (preview generation), guard with a
monotonic request id so a slow earlier response can't overwrite a newer one —
this is how `PreviewSession` avoids a stale-image race:

```typescript
const requestId = ++this.#requestId;
const result = await plotDefinition(/* … */);
if (requestId !== this.#requestId) return; // superseded
this.image = result.image;
```

### 5. Lazy work and code splitting

Use dynamic `import()` for heavy, rarely-used modules so they stay out of the
initial bundle:

```typescript
const { renderHeavyThing } = await import("./heavyThing");
```

Prefer doing expensive work on demand (e.g. only when a panel opens) rather than
eagerly at mount.

## Common Performance Issues

### Issue: Slow event handler

**Symptom:** A click or input feels janky.

**Diagnosis:** Record the interaction in the Performance tab; look for a long
task inside the handler.

**Solutions:**

- Move heavy computation into a `$derived` (memoized) or off the critical path
- Debounce backend-bound work
- Avoid synchronous JSON of large payloads in the handler

### Issue: Slow list rendering

**Symptom:** Adding a layer is sluggish with many rows.

**Solutions:**

- Key every `{#each}` with a stable id so Svelte reuses DOM nodes
- Derive sorted/filtered views once, not per row
- Virtualize only if lists realistically reach hundreds of items

### Issue: Large bundle size

**Symptom:** `npm run perf:bundle` fails the budget, or initial load is slow.

**Diagnosis:** Run `npx vite-bundle-visualizer`.

**Solutions:**

- Code split heavy/optional features behind dynamic `import()`
- Tree-shake unused dependencies
- Question whether a new dependency is needed at all

### Issue: Leaked subscriptions

**Symptom:** Memory grows over time.

**Common Causes:**

- Tauri event listeners not unlistened
- Timers/intervals not cleared

**Solution:** Return a cleanup from `onMount`/`$effect`, mirroring how the shell
tears down the theme watcher, CLI health polling, and stream subscription:

```svelte
<script lang="ts">
  import { onMount } from "svelte";
  import { machineSession } from "../state/machine-session.svelte";

  onMount(() => {
    let cleanup = () => {};
    machineSession.subscribe().then((fn) => (cleanup = fn));
    return () => cleanup();
  });
</script>
```

## Performance Budgets

### Target Metrics

| Metric                 | Target | Critical |
| ---------------------- | ------ | -------- |
| First Contentful Paint | <1s    | <2s      |
| Time to Interactive    | <2s    | <3s      |
| Interaction handling   | <16ms  | <50ms    |
| State update           | <5ms   | <16ms    |
| Bundle Size (JS)       | <400KB | <750KB   |
| Memory Usage (idle)    | <100MB | <200MB   |

### Measuring

```typescript
performance.mark("op-start");
// ...work
performance.mark("op-end");
performance.measure("op", "op-start", "op-end");
const [measure] = performance.getEntriesByName("op");
console.log(`Took ${measure.duration.toFixed(2)}ms`);
```

## Optimizing Tauri / Backend Calls

### Show loading state for async work

```typescript
session.isGenerating = true;
try {
  const result = await plotDefinition(/* … */);
  session.image = result.image;
} finally {
  session.isGenerating = false;
}
```

### Debounce preview updates

```typescript
const regenerate = debounce(() => previewSession.generate(), 300);
// call regenerate() from slider/scrubber input
```

**Prevents:** Rapid-fire backend calls on slider drag. The request-id guard then
ensures only the latest response is applied.

## Testing Performance

### Synthetic Benchmarks

State logic is plain classes, so it benchmarks without rendering:

```typescript
import { ProjectSession } from "../state/project-session.svelte";

it("handles 1000 layer adds quickly", () => {
  const session = new ProjectSession();
  const start = performance.now();
  for (let i = 0; i < 1000; i++) session.addLayer("hoop");
  expect(performance.now() - start).toBeLessThan(100);
});
```

## Profiling Checklist

Before optimizing:

- [ ] Record the interaction in the Performance tab
- [ ] Identify the long task (>50ms) and where it runs
- [ ] Check `$derived`/`$effect` dependencies aren't over-broad
- [ ] Confirm `{#each}` blocks are keyed with stable ids
- [ ] Confirm backend-bound work is debounced

After optimizing:

- [ ] Re-profile to verify improvement
- [ ] Test edge cases (100+ layers, large files)
- [ ] Run `npm run perf:bundle` to confirm the budget holds

## Resources

- [Svelte 5 reactivity (runes)](https://svelte.dev/docs/svelte/what-are-runes)
- [Web Vitals](https://web.dev/vitals/)

## Next Steps

- [State Management](../architecture/state-management.md) - Reactive state design
- [Tech Stack](../architecture/tech-stack.md) - Understanding Vite optimizations
- [Testing Guide](../testing.md) - Performance testing patterns
