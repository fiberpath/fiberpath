<script lang="ts">
  import { projectSession } from "../../state/project-session.svelte";
  import { previewSession } from "../../state/preview-session.svelte";
  import { zoomAt, pan, centered, type Transform } from "../../lib/panzoom";
  import * as fileOps from "../../services/file-operations.svelte";

  const layerCount = $derived(projectSession.document.layers.length);
  const hasLayers = $derived(layerCount > 0);

  let wrapperEl = $state<HTMLDivElement>();
  let transform = $state<Transform>({ scale: 1, x: 0, y: 0 });
  let natural = { w: 0, h: 0 };

  // Keep the visible-layer count synced to the layer count (reset to "all" when
  // layers are added/removed); the scrubber overrides it within that range.
  $effect(() => {
    previewSession.visibleLayerCount = layerCount;
  });

  function fit() {
    if (!wrapperEl || !natural.w || !natural.h) return;
    const scale = Math.min(1, wrapperEl.clientWidth / natural.w, wrapperEl.clientHeight / natural.h);
    transform = centered(wrapperEl.clientWidth, wrapperEl.clientHeight, natural.w, natural.h, scale);
  }

  function onImageLoad(e: Event) {
    const img = e.currentTarget as HTMLImageElement;
    natural = { w: img.naturalWidth, h: img.naturalHeight };
    fit();
  }

  function viewportPoint(e: { clientX: number; clientY: number }) {
    const rect = wrapperEl!.getBoundingClientRect();
    return { px: e.clientX - rect.left, py: e.clientY - rect.top };
  }

  function onWheel(e: WheelEvent) {
    if (!wrapperEl) return;
    e.preventDefault();
    const { px, py } = viewportPoint(e);
    transform = zoomAt(transform, px, py, e.deltaY < 0 ? 1.1 : 1 / 1.1);
  }

  let dragging = false;
  let last = { x: 0, y: 0 };
  function onPointerDown(e: PointerEvent) {
    dragging = true;
    last = { x: e.clientX, y: e.clientY };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: PointerEvent) {
    if (!dragging) return;
    transform = pan(transform, e.clientX - last.x, e.clientY - last.y);
    last = { x: e.clientX, y: e.clientY };
  }
  function onPointerUp() {
    dragging = false;
  }

  function zoomButton(factor: number) {
    if (!wrapperEl) return;
    transform = zoomAt(transform, wrapperEl.clientWidth / 2, wrapperEl.clientHeight / 2, factor);
  }

  const scrubberLabel = $derived(
    previewSession.visibleLayerCount === layerCount
      ? "All"
      : `1-${previewSession.visibleLayerCount}`,
  );
</script>

{#if !hasLayers}
  <div class="vp__empty">
    <p class="vp__empty-title">No layers to visualize</p>
    <p class="vp__empty-hint">Add layers to see the toolpath preview</p>
  </div>
{:else}
  <div class="vp">
    <div class="vp__header">
      <span class="vp__scrub-label">Preview Layers: {scrubberLabel} of {layerCount}</span>
      <input
        class="vp__scrub"
        type="range"
        min="1"
        max={layerCount}
        value={previewSession.visibleLayerCount}
        oninput={(e) => (previewSession.visibleLayerCount = Number(e.currentTarget.value))}
        title="Adjust visible layers in preview (does not affect export)"
      />
    </div>

    <div class="vp__content">
      {#if previewSession.isGenerating}
        <div class="vp__state"><span class="vp__spinner"></span> Generating preview…</div>
      {:else if previewSession.error}
        <div class="vp__state vp__state--error">
          <p>{previewSession.error}</p>
          <button class="vp__btn" onclick={() => previewSession.generate()}>Retry</button>
        </div>
      {:else if !previewSession.image}
        <div class="vp__state">
          <button class="vp__btn" onclick={() => previewSession.generate()}>Generate preview</button>
        </div>
      {:else}
        <div class="vp__controls">
          <button class="vp__btn" title="Regenerate preview" onclick={() => previewSession.generate()}>↻</button>
          <span class="vp__sep"></span>
          <button class="vp__btn" title="Zoom in" onclick={() => zoomButton(1.2)}>+</button>
          <button class="vp__btn" title="Reset zoom" onclick={fit}>⟲</button>
          <button class="vp__btn" title="Zoom out" onclick={() => zoomButton(1 / 1.2)}>−</button>
          <span class="vp__sep"></span>
          <button class="vp__btn" title="Export G-code" onclick={() => fileOps.exportGcode()}>⭳</button>
        </div>
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="vp__stage"
          bind:this={wrapperEl}
          onwheel={onWheel}
          onpointerdown={onPointerDown}
          onpointermove={onPointerMove}
          onpointerup={onPointerUp}
          onpointerleave={onPointerUp}
        >
          <div
            class="vp__transform"
            style="transform: translate({transform.x}px, {transform.y}px) scale({transform.scale});"
          >
            <img class="vp__image" src={previewSession.image} alt="Toolpath preview" onload={onImageLoad} draggable="false" />
          </div>
        </div>
      {/if}

      {#if previewSession.warnings.length > 0 && !previewSession.isGenerating}
        <div class="vp__warnings">
          <strong>⚠ Planner Warnings</strong>
          {#each previewSession.warnings as w, i (i)}<p>{w}</p>{/each}
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .vp,
  .vp__empty {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }
  .vp__empty {
    align-items: center;
    justify-content: center;
    color: var(--color-text-muted);
    text-align: center;
  }
  .vp__empty-title {
    margin: 0;
    font-size: var(--font-size-sm);
  }
  .vp__empty-hint {
    margin: var(--spacing-xs) 0 0;
    font-size: var(--font-size-xs);
  }
  .vp__header {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-xs) var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-panel);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .vp__scrub {
    flex: 1;
    max-width: 16rem;
  }
  .vp__content {
    position: relative;
    flex: 1;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .vp__state {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--spacing-sm);
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }
  .vp__state--error {
    color: var(--status-error);
  }
  .vp__btn {
    appearance: none;
    border: 1px solid var(--color-border);
    background: var(--color-bg-panel-alt);
    color: var(--color-text);
    font-size: var(--font-size-sm);
    min-width: 1.75rem;
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--border-radius-sm);
    cursor: pointer;
  }
  .vp__btn:hover {
    background: var(--color-bg-hover);
  }
  .vp__controls {
    position: absolute;
    top: var(--spacing-sm);
    right: var(--spacing-sm);
    z-index: var(--z-controls);
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    padding: var(--spacing-xs);
    background: var(--color-bg-panel);
    border: 1px solid var(--color-border);
    border-radius: var(--border-radius-sm);
  }
  .vp__sep {
    width: 1px;
    align-self: stretch;
    background: var(--color-border);
  }
  .vp__stage {
    position: absolute;
    inset: 0;
    overflow: hidden;
    cursor: grab;
    touch-action: none;
  }
  .vp__stage:active {
    cursor: grabbing;
  }
  .vp__transform {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
  }
  .vp__image {
    display: block;
    user-select: none;
  }
  .vp__warnings {
    position: absolute;
    bottom: var(--spacing-sm);
    left: var(--spacing-sm);
    right: var(--spacing-sm);
    padding: var(--spacing-sm);
    background: var(--status-warning-bg);
    border: 1px solid var(--status-warning);
    border-radius: var(--border-radius-sm);
    font-size: var(--font-size-xs);
    color: var(--color-text);
  }
  .vp__warnings p {
    margin: var(--spacing-xs) 0 0;
  }
  .vp__spinner {
    width: 1rem;
    height: 1rem;
    border: 2px solid var(--color-border);
    border-top-color: var(--color-primary);
    border-radius: var(--border-radius-round);
    display: inline-block;
    animation: vp-spin 0.8s linear infinite;
  }
  @keyframes vp-spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
