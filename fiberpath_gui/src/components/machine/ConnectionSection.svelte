<script lang="ts">
  import { onMount } from "svelte";
  import { machineSession as m } from "../../state/machine-session.svelte";
  import { BAUD_RATES } from "../../lib/constants";
  import { isTauri } from "../../lib/tauri";
  import InspectorSection from "../../ui/InspectorSection.svelte";

  // Only auto-probe ports when the backend exists; in the browser preview this
  // would surface an unsolicited error on tab entry.
  onMount(() => {
    if (isTauri()) void m.refreshPorts();
  });

  const statusText = $derived(
    m.status === "connected"
      ? `Connected to ${m.selectedPort}`
      : m.status === "connecting"
        ? "Connecting…"
        : m.status === "paused"
          ? "Paused"
          : "Disconnected",
  );

  // #146: surface the connected controller's reported capabilities (enabled only).
  const enabledCapabilities = $derived(
    Object.entries(m.capabilities)
      .filter(([, on]) => on)
      .map(([name]) => name),
  );
</script>

<InspectorSection title="Connection">
  <div class="field">
    <label for="port-select">Port</label>
    <div class="row">
      <select id="port-select" bind:value={m.selectedPort} disabled={m.status !== "disconnected"}>
        {#if m.ports.length === 0}
          <option value={null}>No ports found</option>
        {:else}
          {#each m.ports as p (p.port)}<option value={p.port}>{p.port} — {p.description}</option>{/each}
        {/if}
      </select>
      <button
        class="icon-btn"
        title="Refresh serial ports"
        aria-label="Refresh serial ports"
        disabled={m.refreshing || m.status !== "disconnected"}
        onclick={() => m.refreshPorts()}>⟳</button
      >
    </div>
  </div>

  <div class="field">
    <label for="baud-select">Baud</label>
    <select id="baud-select" bind:value={m.baudRate} disabled={m.status !== "disconnected"}>
      {#each BAUD_RATES as b (b)}<option value={b}>{b}</option>{/each}
    </select>
  </div>

  <div class="status" data-tone={m.status}>
    <span class="status__dot" aria-hidden="true"></span>
    <span>{statusText}</span>
  </div>

  {#if m.isConnected && m.firmware}
    <div class="info">
      <div class="info__row">
        <span class="info__label">Firmware</span>
        <span class="info__value mono">{m.firmware}</span>
      </div>
      {#if enabledCapabilities.length > 0}
        <div class="info__row">
          <span class="info__label">Capabilities</span>
          <span class="info__value">{enabledCapabilities.join(", ")}</span>
        </div>
      {/if}
    </div>
  {/if}

  {#if m.status === "disconnected"}
    <button
      class="btn btn--primary btn--block"
      disabled={!m.selectedPort || m.ports.length === 0}
      onclick={() => m.connect()}>Connect</button
    >
  {:else}
    <button class="btn btn--secondary btn--block" disabled={m.status === "connecting"} onclick={() => m.disconnect()}>
      Disconnect
    </button>
  {/if}
</InspectorSection>

<style>
  .field {
    margin-bottom: var(--spacing-sm);
  }
  .field label {
    display: block;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin-bottom: var(--spacing-xs);
  }
  .row {
    display: flex;
    gap: var(--spacing-xs);
  }
  select {
    flex: 1;
    height: var(--input-height-sm);
    background: var(--color-bg-panel-alt);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    font-size: var(--font-size-sm);
    padding: 0 var(--spacing-xs);
  }
  .status {
    display: flex;
    align-items: center;
    gap: var(--spacing-xs);
    font-size: var(--font-size-sm);
    margin: var(--spacing-sm) 0;
  }
  .status__dot {
    width: var(--dot-size);
    height: var(--dot-size);
    border-radius: var(--border-radius-round);
    background: var(--color-text-muted);
  }
  .status[data-tone="connected"] .status__dot {
    background: var(--status-success-fg);
  }
  .status[data-tone="connecting"] .status__dot {
    background: var(--status-warning-fg);
  }
  .status[data-tone="paused"] .status__dot {
    background: var(--status-caution-fg);
  }
  .info {
    margin: var(--spacing-sm) 0;
    padding: var(--spacing-xs) var(--spacing-sm);
    background: var(--color-bg-panel-alt);
    border: 1px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    font-size: var(--font-size-xs);
  }
  .info__row {
    display: flex;
    justify-content: space-between;
    gap: var(--spacing-sm);
  }
  .info__row + .info__row {
    margin-top: var(--spacing-xs);
  }
  .info__label {
    color: var(--color-text-muted);
  }
  .info__value {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--color-text);
  }
  .info__value.mono {
    font-family: var(--font-family-mono);
  }
</style>
