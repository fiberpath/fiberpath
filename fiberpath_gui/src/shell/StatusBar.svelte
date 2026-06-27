<script lang="ts">
  import { projectSession } from "../state/project-session.svelte";
  import { backendHealth } from "../state/backend-health.svelte";

  const projectName = $derived(
    projectSession.filePath
      ? (projectSession.filePath.split(/[\\/]/).pop() || "Untitled")
      : "Untitled",
  );
  const layerCount = $derived(projectSession.document.layers.length);

  const cliText = $derived(
    backendHealth.isBrowserPreview
      ? "Browser preview"
      : backendHealth.status === "ready"
        ? "Backend: Ready"
        : backendHealth.status === "checking"
          ? "Backend: Checking…"
          : backendHealth.status === "unavailable"
            ? "Backend: Unavailable"
            : "Backend: Unknown",
  );
</script>

<footer class="statusbar">
  <div class="statusbar__item">
    <span class="statusbar__label">Project:</span>
    <span class="statusbar__value">
      {projectName}{#if projectSession.isDirty}<span class="statusbar__dirty" aria-hidden="true">●</span><span class="statusbar__sr"> (unsaved changes)</span>{/if}
    </span>
  </div>

  {#if layerCount > 0}
    <div class="statusbar__item">
      <span class="statusbar__label">Layers:</span>
      <span class="statusbar__value">{layerCount}</span>
    </div>
  {/if}

  <div class="statusbar__item statusbar__item--meta">
    <span class="statusbar__dot" data-status={backendHealth.status} aria-hidden="true"></span>
    <span class="statusbar__value">{cliText}</span>
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
    margin-left: var(--spacing-xs);
    font-size: 0.6em;
    vertical-align: middle;
  }
  .statusbar__sr {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  .statusbar__dot {
    width: var(--dot-size);
    height: var(--dot-size);
    border-radius: var(--border-radius-round);
    background: var(--color-text-muted);
  }
  .statusbar__dot[data-status="ready"] {
    background: var(--status-success-fg);
  }
  .statusbar__dot[data-status="checking"] {
    background: var(--status-warning-fg);
  }
  .statusbar__dot[data-status="unavailable"] {
    background: var(--status-error-fg);
  }
</style>
