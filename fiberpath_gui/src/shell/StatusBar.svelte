<script lang="ts">
  import { projectSession } from "../state/project-session.svelte";

  const projectName = $derived(
    projectSession.filePath
      ? (projectSession.filePath.split(/[\\/]/).pop() || "Untitled")
      : "Untitled",
  );
  const layerCount = $derived(projectSession.document.layers.length);
</script>

<footer class="statusbar">
  <div class="statusbar__item">
    <span class="statusbar__label">Project:</span>
    <span class="statusbar__value">
      {projectName}{#if projectSession.isDirty}<span class="statusbar__dirty" title="Unsaved changes">*</span>{/if}
    </span>
  </div>

  {#if layerCount > 0}
    <div class="statusbar__item">
      <span class="statusbar__label">Layers:</span>
      <span class="statusbar__value">{layerCount}</span>
    </div>
  {/if}

  <!-- minimal: machine/CLI health is a static placeholder until the health
       hook migrates (#220) and the Machine workspace lands (#219). -->
  <div class="statusbar__item statusbar__item--meta">
    <span class="statusbar__dot" aria-hidden="true"></span>
    <span class="statusbar__value">Not connected</span>
  </div>
</footer>

<style>
  .statusbar {
    display: flex;
    align-items: center;
    gap: var(--spacing-lg);
    height: var(--statusbar-height);
    padding: 0 var(--spacing-md);
    background: var(--color-bg-panel);
    border-top: 1px solid var(--color-border);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .statusbar__item {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
  }
  .statusbar__item--meta {
    margin-left: auto;
  }
  .statusbar__label {
    color: var(--color-text-muted);
  }
  .statusbar__value {
    color: var(--color-text);
  }
  .statusbar__dirty {
    color: var(--color-accent);
    margin-left: 2px;
  }
  .statusbar__dot {
    width: 7px;
    height: 7px;
    border-radius: var(--border-radius-round);
    background: var(--color-text-muted);
  }
</style>
