<script lang="ts">
  import { machineSession as m } from "../../state/machine-session.svelte";
  import InspectorSection from "../../ui/InspectorSection.svelte";
</script>

<InspectorSection title="File Streaming">
  <div class="file">
    <span class="file__label">File</span>
    <span class="file__name">{m.selectedFile ?? "No file selected"}</span>
    {#if m.selectedFile && !m.isStreaming}
      <button class="file__clear" title="Clear file selection" aria-label="Clear file selection" onclick={() => m.clearFile()}>×</button>
    {/if}
  </div>
  <button class="action" disabled={m.isStreaming} onclick={() => m.selectFile()}>Select File</button>

  {#if m.progress}
    <div class="progress">
      <div class="progress__head">
        <span>Progress</span><span>{m.progress.sent} / {m.progress.total}</span>
      </div>
      <progress value={m.progress.sent} max={Math.max(m.progress.total, 1)}></progress>
      <div class="progress__cmd"><span>Current</span><span class="mono">{m.progress.currentCommand}</span></div>
    </div>
  {/if}

  <div class="controls">
    {#if !m.isStreaming}
      <button class="action action--start" disabled={!m.canStartStream} onclick={() => m.startStream()}>
        Start Stream
      </button>
    {:else}
      <div class="grid">
        {#if !m.isPaused}
          <button class="action action--warn" disabled={m.streamControlLoading} onclick={() => m.pause()}>Pause</button>
        {:else}
          <button class="action action--start" disabled={m.streamControlLoading} onclick={() => m.resume()}>Resume</button>
        {/if}
        {#if m.isPaused}
          <button class="action" disabled={m.streamControlLoading} onclick={() => m.cancel()} title="Cancel job (stays connected)">
            Cancel Job
          </button>
        {:else}
          <button
            class="action action--stop"
            disabled={m.streamControlLoading}
            onclick={() => m.stop()}
            title="Emergency stop (M112) — WARNING: disconnects the controller">Stop</button
          >
        {/if}
      </div>
    {/if}
  </div>
</InspectorSection>

<style>
  .file {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    margin-bottom: var(--spacing-xs);
  }
  .file__label {
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .file__name {
    flex: 1;
    min-width: 0;
    font-family: var(--font-family-mono);
    font-size: var(--font-size-xs);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .file__clear {
    appearance: none;
    border: none;
    background: transparent;
    color: var(--color-text-muted);
    cursor: pointer;
    font-size: var(--font-size-base);
  }
  .action {
    appearance: none;
    width: 100%;
    height: var(--input-height-sm);
    border: 1px solid var(--color-border);
    background: var(--color-bg-panel-alt);
    color: var(--color-text);
    border-radius: var(--border-radius-sm);
    font-size: var(--font-size-sm);
    cursor: pointer;
  }
  .action:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .action--start {
    background: var(--status-success);
    border-color: var(--status-success);
    color: var(--color-text-inverse);
  }
  .action--warn {
    background: var(--status-warning);
    border-color: var(--status-warning);
    color: var(--color-text-inverse);
  }
  .action--stop {
    background: var(--status-error);
    border-color: var(--status-error);
    color: var(--color-text-inverse);
  }
  .controls {
    margin-top: var(--spacing-sm);
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-xs);
  }
  .progress {
    margin-top: var(--spacing-sm);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
  .progress__head,
  .progress__cmd {
    display: flex;
    justify-content: space-between;
    gap: var(--spacing-sm);
  }
  .progress progress {
    width: 100%;
    height: 6px;
    margin: 2px 0;
  }
  .mono {
    font-family: var(--font-family-mono);
    color: var(--color-text);
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
