<script lang="ts">
  import { cliHealth } from "../../state/cli-health.svelte";
  import CliUnavailableDialog from "../dialogs/CliUnavailableDialog.svelte";

  let showDialog = $state(false);
</script>

{#if cliHealth.isBrowserPreview}
  <div class="cli-warning-banner cli-warning-banner--info">
    <div class="cli-warning-banner__content">
      <span class="cli-warning-banner__icon">🌐</span>
      <div class="cli-warning-banner__text">
        <strong>Browser preview</strong>
        <span>Running without the desktop backend. Use <code>npm run tauri dev</code> for compute, file, and machine features.</span>
      </div>
    </div>
  </div>
{:else if cliHealth.isUnavailable}
  <div class="cli-warning-banner">
    <div class="cli-warning-banner__content">
      <span class="cli-warning-banner__icon">⚠️</span>
      <div class="cli-warning-banner__text">
        <strong>CLI Backend Unavailable</strong>
        <span>Compute and file operations are disabled. The FiberPath backend cannot be detected.</span>
      </div>
    </div>
    <div class="cli-warning-banner__actions">
      <button class="btn btn--small btn--secondary" onclick={() => cliHealth.refresh()}>Retry</button>
      <button class="btn btn--small btn--ghost" onclick={() => (showDialog = true)}>Details</button>
    </div>
  </div>
{/if}

{#if showDialog}
  <CliUnavailableDialog
    version={cliHealth.version}
    errorMessage={cliHealth.errorMessage}
    onretry={() => cliHealth.refresh()}
    onclose={() => (showDialog = false)}
  />
{/if}
