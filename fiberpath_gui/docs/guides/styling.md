# Styling Guide

This guide documents the actual styling architecture used in FiberPath GUI.

## Architecture Summary

FiberPath GUI uses **global CSS for shared design**, with **Svelte scoped
`<style>`** for component-specific rules. It does not use CSS Modules.

- Global styles are loaded in a fixed order from `src/styles/index.css`.
- Shared primitives and design tokens live in `src/styles/*.css`.
- Component-specific rules live in a scoped `<style>` block inside the
  `.svelte` file (Svelte scopes them automatically — no class-name collisions).
  A few older feature stylesheets still exist (e.g. `src/components/StreamTab/*.css`)
  and are being folded into their components.
- Class naming for shared/global styles follows semantic, BEM-like patterns
  (`block__element--modifier`).

## CSS File Structure

### Global Style Layers (`src/styles/index.css` import order)

1. `tokens.css` (design tokens)
2. `reset.css`
3. `typography.css`
4. `buttons.css`
5. `forms.css`
6. `panels.css`
7. `canvas.css`
8. `layout.css`
9. `tabs.css`
10. `dialogs.css`
11. `notifications.css`

### Component-Level CSS

Use a scoped `<style>` block (or, for the legacy files, component CSS) only for
behavior/layout unique to that component. Do not re-declare shared
panel/button/form/dialog chrome there — reach for the global primitives and
tokens instead.

```svelte
<div class="param-form__group">
  <!-- uses the global forms primitive -->
  <span class="field-tooltip" title={tooltip}>ⓘ</span>
</div>

<style>
  /* Scoped to this component — only its own unique chrome. */
  .field-tooltip {
    margin-left: var(--spacing-xs);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }
</style>
```

## Token Taxonomy

All tokens are defined in `src/styles/tokens.css`.

### Surface / Elevation

- `--color-bg`
- `--color-bg-panel`
- `--color-bg-panel-alt`
- `--color-bg-hover`
- `--color-bg-active`
- `--shadow-sm` .. `--shadow-xl`

### Text Hierarchy

- `--color-text`
- `--color-text-muted`
- `--color-text-inverse`
- `--font-family-*`
- `--font-size-*`
- `--font-weight-*`
- `--line-height-*`

### Border / Separator

- `--color-border`
- `--color-border-soft`
- `--color-border-focus`
- `--border-width-*`

### Status / State

Canonical status aliases:

- `--status-success`, `--status-success-bg`
- `--status-warning`, `--status-warning-bg`
- `--status-caution`
- `--status-error`, `--status-error-bg`
- `--status-info`, `--status-info-bg`

These map to the underlying palette tokens and should be used for semantic state styling.

### Spacing, Radius, Motion, Layers, Dimensions

- Spacing: `--spacing-xs` .. `--spacing-3xl`
- Radius: `--border-radius-sm` .. `--border-radius-round`
- Motion: `--transition-fast`, `--transition-base`, `--transition-colors`
- Z-index: `--z-index-*`
- Dimensions: `--panel-header-height`, `--input-height`, etc.

## Theme Architecture

Theme handling is token-based and centralized.

- Dark defaults are defined in `:root` in `tokens.css`.
- Manual light mode uses `[data-theme="light"]` overrides in `tokens.css`.
- System fallback uses `@media (prefers-color-scheme: light)` with `:root:not([data-theme])`.
- Runtime theme state is the `theme` runes singleton in `src/state/theme.svelte.ts`.
  `App.svelte` applies it with a `$effect` that sets/removes the `data-theme`
  attribute on the document root, and an `onMount` watcher tracks the OS preference.
- Theme selection UI is the "Cycle Theme" menubar action in `src/shell/MenuBar.svelte`.
- Preference persistence uses `localStorage` key `fiberpath-theme` (`"dark"`, `"light"`, or system via removed key).

## Shared Primitives

Prefer these before creating new component-local styles.

### Panels (`src/styles/panels.css`)

- `.panel`
- `.panel--compact`
- `.panel-container`
- `.panel-header`
- `.panel-title`
- `.panel-body`

### Dialogs (`src/styles/dialogs.css`)

- `.dialog-overlay`
- `.dialog-content`
- `.dialog-content--small`
- `.dialog-content--medium`
- `.dialog-header`
- `.dialog-body`
- `.dialog-footer`
- `.dialog-close`

### Buttons (`src/styles/buttons.css`)

- Base: `.btn`
- Variants: `.btn--primary`, `.btn--secondary`, `.btn--danger`, `.btn--success`, `.btn--warning`, `.btn--ghost`
- Utilities: `.btn--small`, `.btn--icon-only`, `.btn--loading`

### Forms (`src/styles/forms.css`)

- `.param-form`
- `.param-form__group`
- `.param-form__label`
- `.param-form__input`
- `.param-form__select`
- `.param-form__input--error`
- `.param-form__input--success`

### Typography Utilities (`src/styles/typography.css`)

- `.text-muted`
- `.text-center`
- `.text-mono`
- `.text-uppercase`

## Inline Style Exception Policy

Default rule: **no static inline styles**.

An inline `style="…"` (or `style:` directive) is allowed only when a value is
truly runtime-dynamic and cannot be expressed safely as classes.

If inline style is required:

- Keep scope minimal (single dynamic property when possible).
- Add an inline comment: `/* dynamic: reason */`.

Current approved dynamic exceptions:

- `src/components/canvas/Viewport.svelte` (the pan/zoom `transform` computed from
  the `panzoom` controller state)

Note: the streaming progress bar now uses a native `<progress value max>`
element, and layer reordering uses native HTML5 drag — neither needs an inline
style anymore.

## How To Add Styles Safely

Use this sequence for all new UI work:

1. Choose existing token(s) from `tokens.css`.
2. Reuse a shared primitive (`panel`, `btn`, `param-form`, `dialog`) when possible.
3. Add a scoped `<style>` block in the `.svelte` file only for unique layout/behavior.
4. Keep selectors shallow and semantic.
5. Avoid hardcoded values when an existing token covers the need.

## Quality Gates

Run from `fiberpath_gui/`:

```bash
npm run check:all
npm run test
```

`check:all` includes TypeScript, stylelint, CSS variable guard, Rust format check, and clippy.

## Guardrails

Do:

- Use tokens (`var(--token)`) for color/spacing/typography/motion.
- Keep component CSS focused on component-specific behavior.
- Use status aliases (`--status-*`) for semantic state UI.

Do not:

- Reintroduce CSS Modules patterns into this codebase.
- Re-declare shared primitive styles in feature CSS files.
- Add new static inline styles.
- Add hardcoded color literals when equivalent tokens exist.
