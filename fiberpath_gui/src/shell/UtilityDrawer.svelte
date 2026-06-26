<script lang="ts">
  import { uiState } from "../state/ui-state.svelte";
</script>

<div class="drawer" class:drawer--open={uiState.drawerOpen}>
  <button
    class="drawer__handle"
    aria-expanded={uiState.drawerOpen}
    onclick={() => uiState.toggleDrawer()}
  >
    <span class="drawer__chevron" class:drawer__chevron--open={uiState.drawerOpen}>›</span>
    Utility
  </button>
  {#if uiState.drawerOpen}
    <div class="drawer__body">
      <!-- Width-hungry surfaces (machine console, G-code, diagnostics, warnings)
           land here as their slices migrate. Closed by default. -->
      <p class="drawer__placeholder">Console, G-code and diagnostics will appear here.</p>
    </div>
  {/if}
</div>

<style>
  .drawer {
    border-top: 1px solid var(--color-border);
    background: var(--color-bg-panel);
  }
  .drawer__handle {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    width: 100%;
    height: 1.5rem;
    padding: 0 var(--spacing-md);
    appearance: none;
    border: none;
    background: transparent;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
    text-align: left;
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .drawer__handle:hover {
    color: var(--color-text);
    background: var(--color-bg-hover);
  }
  .drawer__chevron {
    display: inline-block;
    transition: transform var(--transition-fast);
  }
  .drawer__chevron--open {
    transform: rotate(90deg);
  }
  .drawer__body {
    height: 9rem;
    overflow-y: auto;
    padding: var(--spacing-md);
    border-top: 1px solid var(--color-border);
  }
  .drawer__placeholder {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }
</style>
