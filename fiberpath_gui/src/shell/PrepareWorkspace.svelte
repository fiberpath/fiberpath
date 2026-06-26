<script lang="ts">
  import { uiState } from "../state/ui-state.svelte";
  import { projectSession } from "../state/project-session.svelte";
  import InspectorSection from "../ui/InspectorSection.svelte";
  import MandrelForm from "../components/forms/MandrelForm.svelte";
  import TowForm from "../components/forms/TowForm.svelte";
  import MachineSettingsForm from "../components/forms/MachineSettingsForm.svelte";

  const layerCount = $derived(projectSession.document.layers.length);
</script>

<div
  class="prepare"
  class:prepare--no-left={uiState.leftCollapsed}
  class:prepare--no-right={uiState.rightCollapsed}
>
  {#if !uiState.leftCollapsed}
    <aside class="prepare__inspector prepare__inspector--left" aria-label="Project inspector">
      <!-- Config forms (migrated #215) plus the layer list, now consolidated into
           the left project hierarchy (was a separate bottom panel in React). Each
           form carries its own title, so they aren't wrapped in InspectorSection. -->
      <div class="form-block"><MandrelForm /></div>
      <div class="form-block"><TowForm /></div>
      <div class="form-block"><MachineSettingsForm /></div>

      <InspectorSection title="Layers">
        {#snippet action()}
          <button class="ghost-btn" disabled title="Layer editing lands in #217">+ Add</button>
        {/snippet}
        {#if layerCount === 0}
          <p class="placeholder">No layers yet.</p>
        {:else}
          <p class="placeholder">{layerCount} layer(s)</p>
        {/if}
      </InspectorSection>
    </aside>
  {/if}

  <section class="prepare__viewport" aria-label="Toolpath viewport">
    <div class="placeholder placeholder--center">
      <p>Toolpath preview</p>
      <p class="placeholder__sub">Viewport migrates in #218</p>
    </div>
  </section>

  {#if !uiState.rightCollapsed}
    <aside class="prepare__inspector prepare__inspector--right" aria-label="Layer inspector">
      <InspectorSection title="Layer Properties">
        <p class="placeholder">Select a layer to edit its properties.</p>
      </InspectorSection>
    </aside>
  {/if}
</div>

<style>
  .prepare {
    display: grid;
    grid-template-columns: 300px 1fr 280px;
    height: 100%;
    min-height: 0;
  }
  .prepare--no-left {
    grid-template-columns: 1fr 280px;
  }
  .prepare--no-right {
    grid-template-columns: 300px 1fr;
  }
  .prepare--no-left.prepare--no-right {
    grid-template-columns: 1fr;
  }
  .prepare__inspector {
    overflow-y: auto;
    background: var(--color-bg-panel);
  }
  .prepare__inspector--left {
    border-right: 1px solid var(--color-border);
  }
  .prepare__inspector--right {
    border-left: 1px solid var(--color-border);
  }
  .form-block {
    padding: var(--spacing-md);
    border-bottom: 1px solid var(--color-border);
  }
  .prepare__viewport {
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-bg);
    min-width: 0;
  }
  .placeholder {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }
  .placeholder--center {
    text-align: center;
  }
  .placeholder__sub {
    margin: var(--spacing-xs) 0 0;
    font-size: var(--font-size-xs);
  }
  .ghost-btn {
    appearance: none;
    border: 1px solid var(--color-border);
    background: transparent;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    padding: 2px var(--spacing-sm);
    border-radius: var(--border-radius-sm);
    cursor: not-allowed;
  }
</style>
