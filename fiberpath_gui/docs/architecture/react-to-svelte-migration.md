# ADR: Migrate the GUI from React to Svelte 5

- **Status:** Accepted — implemented (epic [#214], slices #215–#221), 2026-06.
- **Decision:** Replace the React + Zustand frontend with **Svelte 5** (runes) as a
  plain Vite SPA inside the existing Tauri shell. **No SvelteKit.** Paired with a
  restrained desktop UI redesign.

## Context

The GUI is a desktop app that wraps the Python compute backend (via a FastAPI
sidecar) and a Marlin serial path (via Tauri). The React frontend was paying
ecosystem and render-management costs without a matching benefit:

- `App.tsx` assembled whole element trees and threaded them through `MainTab` as
  four `ReactNode` props — indirection without a domain boundary.
- Render management leaked into app design: Zustand `useShallow` selectors,
  memoisation, debounced re-renders, lazy dialogs.
- State mixed persisted document data with transient UI state in one store.
- The dependency surface was large (React, React-DOM, Zustand, Lucide-React,
  `react-zoom-pan-pinch`, `@hello-pangea/dnd`, …).

The app was still bounded (no real vector/WebGL toolpath renderer yet), so it was
the cheapest moment to change.

## Decision & rationale

Svelte 5's compiler-tracked reactivity (`$state` / `$derived` / `$effect`) lets
shared state live in plain `.svelte.ts` runes modules, so Zustand and the
render-management hooks **disappear** rather than being swapped for another
library. Component-scoped `<style>` keeps a small global design-token system while
colocating feature CSS. Tauri is frontend-agnostic and recommends Vite SPAs, so the
Rust shell was unchanged.

SvelteKit was rejected: a desktop SPA needs no router, SSR, or meta-framework.
SolidJS and Vue were considered but offered less reduction for this form-heavy
desktop UI (see the planning evaluation).

## What changed

| Area | Before (React) | After (Svelte 5) |
| --- | --- | --- |
| Components | `.tsx` / JSX | `.svelte` |
| State | Zustand stores + `useShallow` | runes classes in `src/state/*.svelte.ts` |
| Logic | custom hooks (`src/hooks/*`) | runes modules, `src/services/*`, event handlers |
| Build | `@vitejs/plugin-react` | `@sveltejs/vite-plugin-svelte` |
| Tests | `@testing-library/react` | `@testing-library/svelte` |
| Viewport | `react-zoom-pan-pinch` | native `src/lib/panzoom.ts` |
| Layer DnD | `@hello-pangea/dnd` | native HTML5 drag + keyboard |
| Type-check | `tsc` over `.tsx` | `tsc` (`.ts`) + `svelte-check` (`.svelte`) |

State is now split: a persisted `ProjectDocument` (exactly the `.wind` payload)
separate from a transient session (`filePath`, selection, validation, revision-based
dirty tracking) — see [State Management](state-management.md).

**Deliberately unchanged:** the Zod validation boundary, the OpenAPI-generated
client (`src/api/`), the Tauri/Rust bridge + FastAPI sidecar (see
[CLI Integration](cli-integration.md)), the JSON-schema pipeline, and the global
CSS design tokens.

## Migration strategy

A **strangler-on-`main`** approach: each slice shipped to `main` as its own PR
behind a dev-only Svelte entry, with React remaining the live app and the Svelte
code tree-shaken out of the production build, until this final cutover flipped
`index.html` to Svelte and deleted React. Every slice passed full CI plus an
adversarial review gate. Slice #215 was a decision gate that measured the real
reduction before committing the whole app.

## Consequences

- **Production JS bundle: ~599 KB → ~308 KB (−48%).** Fewer state abstractions and
  no render-management glue.
- **−10 frontend packages** removed (React, React-DOM, Zustand, Lucide-React,
  `react-zoom-pan-pinch`, `@hello-pangea/dnd`, `@testing-library/react`,
  `@types/react`, `@types/react-dom`, `@vitejs/plugin-react`).
- Fixed [#147] (viewport zoom was clamped to image bounds) as a byproduct of the
  native pan/zoom rewrite.
- Two type-checkers now run (`tsc` for `.ts`, `svelte-check` for `.svelte`).
- A restrained desktop redesign: **Prepare** / **Machine** workspaces, the layer
  list consolidated into the left inspector, a collapsible utility drawer.

[#214]: https://github.com/fiberpath/fiberpath/issues/214
[#147]: https://github.com/fiberpath/fiberpath/issues/147
