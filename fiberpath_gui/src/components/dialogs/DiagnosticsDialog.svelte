<script lang="ts">
  import { onMount } from "svelte";
  import Dialog from "../../ui/Dialog.svelte";
  import { backendHealth } from "../../state/backend-health.svelte";
  import { projectSession } from "../../state/project-session.svelte";
  import { getRecentFiles } from "../../lib/recentFiles";

  let { onclose }: { onclose: () => void } = $props();

  const recentCount = getRecentFiles().length;
  const doc = $derived(projectSession.document);

  onMount(() => void backendHealth.refresh());
</script>

<Dialog title="Diagnostics" {onclose}>
  {#snippet footer()}
    <button class="btn btn--secondary" onclick={onclose}>Close</button>
  {/snippet}

  <div class="diagnostics-section">
    <h3 class="section-eyebrow">Backend Status</h3>
    <div class="diagnostics-grid">
      <div class="diagnostics-item">
        <span class="diagnostics-label">Health:</span>
        <span class="diagnostics-value" class:status-healthy={backendHealth.isHealthy} class:status-error={!backendHealth.isHealthy}>
          {backendHealth.isHealthy ? "✓ Healthy" : "✗ Unavailable"}
        </span>
      </div>
      <div class="diagnostics-item">
        <span class="diagnostics-label">Version:</span>
        <span class="diagnostics-value">{backendHealth.version || "Unknown"}</span>
      </div>
      {#if !backendHealth.isHealthy && backendHealth.errorMessage}
        <div class="diagnostics-item diagnostics-item--full-width">
          <span class="diagnostics-label">Error:</span>
          <span class="diagnostics-value diagnostics-value--error">{backendHealth.errorMessage}</span>
        </div>
      {/if}
      {#if backendHealth.lastChecked}
        <div class="diagnostics-item">
          <span class="diagnostics-label">Last Checked:</span>
          <span class="diagnostics-value">{backendHealth.lastChecked.toLocaleTimeString()}</span>
        </div>
      {/if}
    </div>
    <button class="btn btn--secondary diagnostics-refresh-btn" onclick={() => backendHealth.refresh()}>
      Refresh Backend Status
    </button>
  </div>

  <div class="diagnostics-section">
    <h3 class="section-eyebrow">Project Status</h3>
    <div class="diagnostics-grid">
      <div class="diagnostics-item">
        <span class="diagnostics-label">File Path:</span>
        <span class="diagnostics-value diagnostics-value--path">{projectSession.filePath || "Untitled"}</span>
      </div>
      <div class="diagnostics-item">
        <span class="diagnostics-label">Layer Count:</span>
        <span class="diagnostics-value">{doc.layers.length}</span>
      </div>
      <div class="diagnostics-item">
        <span class="diagnostics-label">Unsaved Changes:</span>
        <span class="diagnostics-value" class:status-warning={projectSession.isDirty} class:status-healthy={!projectSession.isDirty}>
          {projectSession.isDirty ? "⚠ Yes" : "✓ No"}
        </span>
      </div>
    </div>
  </div>

  <div class="diagnostics-section">
    <h3 class="section-eyebrow">Application Data</h3>
    <div class="diagnostics-grid">
      <div class="diagnostics-item">
        <span class="diagnostics-label">Recent Files:</span>
        <span class="diagnostics-value">{recentCount} / 10</span>
      </div>
      <div class="diagnostics-item">
        <span class="diagnostics-label">Temp Files:</span>
        <span class="diagnostics-value">Cleaned on exit</span>
      </div>
    </div>
  </div>

  <div class="diagnostics-section">
    <h3 class="section-eyebrow">System Information</h3>
    <div class="diagnostics-grid">
      <div class="diagnostics-item">
        <span class="diagnostics-label">Platform:</span>
        <span class="diagnostics-value">{navigator.platform}</span>
      </div>
      <div class="diagnostics-item diagnostics-item--full-width">
        <span class="diagnostics-label">User Agent:</span>
        <span class="diagnostics-value diagnostics-value--path">{navigator.userAgent}</span>
      </div>
    </div>
  </div>
</Dialog>
