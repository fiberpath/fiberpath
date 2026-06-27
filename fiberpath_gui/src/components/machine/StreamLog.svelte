<script lang="ts">
  import { prefersReducedMotion } from "svelte/motion";
  import { machineSession as m } from "../../state/machine-session.svelte";
  import type { LogEntry } from "../../state/machine-session.svelte";
  import EmptyState from "../../ui/EmptyState.svelte";

  let endEl = $state<HTMLDivElement>();

  $effect(() => {
    // Re-run when entries are appended; scroll to the latest if auto-scroll is on.
    m.log.length;
    if (m.autoScroll) {
      endEl?.scrollIntoView({ behavior: prefersReducedMotion.current ? "auto" : "smooth" });
    }
  });

  const prefix = (t: LogEntry["type"]) =>
    t === "command" ? ">" : t === "response" ? "<" : t === "stream" ? "•" : t === "error" ? "!" : t === "progress" ? "→" : "●";
</script>

<div class="log">
  <header class="log__header">
    <h3 class="section-eyebrow">Output Log</h3>
    <div class="log__actions">
      <button
        class="icon-btn"
        class:icon-btn--active={m.autoScroll}
        title={m.autoScroll ? "Auto-scroll on (click to disable)" : "Auto-scroll off (click to enable)"}
        aria-label="Toggle auto-scroll"
        aria-pressed={m.autoScroll}
        onclick={() => m.toggleAutoScroll()}>⤓</button
      >
      <button class="icon-btn" title="Clear log" aria-label="Clear log" disabled={m.log.length === 0} onclick={() => m.clearLog()}>🗑</button>
    </div>
  </header>
  <div class="log__body">
    {#if m.log.length === 0}
      <EmptyState title="No log entries yet" hint="Connect to a device to get started." />
    {:else}
      {#each m.log as e (e.id)}
        <div class="entry" data-type={e.type}>
          <span class="entry__prefix">{prefix(e.type)}</span><span class="entry__content">{e.content}</span>
        </div>
      {/each}
      <div bind:this={endEl}></div>
    {/if}
  </div>
</div>

<style>
  .log {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
    border-left: 1px solid var(--color-border);
    background: var(--color-bg-panel);
  }
  .log__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: var(--input-height-sm);
    padding: 0 var(--spacing-md);
    background: var(--color-bg-panel-alt);
    border-bottom: 1px solid var(--color-border);
  }
  .log__actions {
    display: flex;
    gap: var(--spacing-xs);
  }
  .log__body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
    padding: var(--spacing-sm);
    font-family: var(--font-family-mono);
    font-size: var(--font-size-xs);
    line-height: var(--line-height-normal);
  }
  .entry {
    display: flex;
    gap: var(--spacing-sm);
    color: var(--color-text);
  }
  .entry__prefix {
    color: var(--color-text-muted);
  }
  .entry[data-type="command"] {
    color: var(--color-primary-soft);
  }
  .entry[data-type="response"] {
    color: var(--color-slate-400);
  }
  .entry[data-type="error"] {
    color: var(--status-error-fg);
  }
  .entry[data-type="stream"] {
    color: var(--color-text-muted);
  }
</style>
