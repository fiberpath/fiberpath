<script lang="ts">
  import { uiState } from "../state/ui-state.svelte";
  import { projectSession } from "../state/project-session.svelte";
  import InspectorSection from "../ui/InspectorSection.svelte";
  import MandrelForm from "../components/forms/MandrelForm.svelte";
  import TowForm from "../components/forms/TowForm.svelte";
  import MachineSettingsForm from "../components/forms/MachineSettingsForm.svelte";
  import LayerList from "../components/layers/LayerList.svelte";
  import HoopLayerEditor from "../components/editors/HoopLayerEditor.svelte";
  import HelicalLayerEditor from "../components/editors/HelicalLayerEditor.svelte";
  import SkipLayerEditor from "../components/editors/SkipLayerEditor.svelte";
  import Viewport from "../components/canvas/Viewport.svelte";

  const selected = $derived(projectSession.selectedLayer);
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
        <LayerList />
      </InspectorSection>
    </aside>
  {/if}

  <section class="prepare__viewport" aria-label="Toolpath viewport">
    <Viewport />
  </section>

  {#if !uiState.rightCollapsed}
    <aside class="prepare__inspector prepare__inspector--right" aria-label="Layer inspector">
      <InspectorSection title="Layer Properties">
        {#if selected?.type === "hoop"}
          <HoopLayerEditor layerId={selected.id} />
        {:else if selected?.type === "helical"}
          <HelicalLayerEditor layerId={selected.id} />
        {:else if selected?.type === "skip"}
          <SkipLayerEditor layerId={selected.id} />
        {:else}
          <p class="placeholder">Select a layer to edit its properties.</p>
        {/if}
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
    background: var(--color-bg);
    min-width: 0;
    overflow: hidden;
  }
  .placeholder {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }
</style>
