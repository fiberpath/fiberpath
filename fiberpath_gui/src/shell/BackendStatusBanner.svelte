<script lang="ts">
  import { backendHealth } from "../state/backend-health.svelte";
  import BackendUnavailableDialog from "../components/dialogs/BackendUnavailableDialog.svelte";

  let showDialog = $state(false);
</script>

{#if backendHealth.isBrowserPreview}
  <div class="backend-warning-banner backend-warning-banner--info">
    <div class="backend-warning-banner__content">
      <span class="backend-warning-banner__icon">🌐</span>
      <div class="backend-warning-banner__text">
        <strong>Browser preview</strong>
        <span>Running without the desktop backend. Use <code>npm run tauri dev</code> for compute, file, and machine features.</span>
      </div>
    </div>
  </div>
{:else if backendHealth.isUnavailable}
  <div class="backend-warning-banner">
    <div class="backend-warning-banner__content">
      <span class="backend-warning-banner__icon">⚠️</span>
      <div class="backend-warning-banner__text">
        <strong>Backend Unavailable</strong>
        <span>Compute and file operations are disabled. The FiberPath backend cannot be detected.</span>
      </div>
    </div>
    <div class="backend-warning-banner__actions">
      <button class="btn btn--small btn--secondary" onclick={() => backendHealth.refresh()}>Retry</button>
      <button class="btn btn--small btn--ghost" onclick={() => (showDialog = true)}>Details</button>
    </div>
  </div>
{/if}

{#if showDialog}
  <BackendUnavailableDialog
    version={backendHealth.version}
    errorMessage={backendHealth.errorMessage}
    onretry={() => backendHealth.refresh()}
    onclose={() => (showDialog = false)}
  />
{/if}
