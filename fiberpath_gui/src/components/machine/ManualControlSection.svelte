<script lang="ts">
  import { machineSession as m } from "../../state/machine-session.svelte";
  import InspectorSection from "../../ui/InspectorSection.svelte";

  const disabled = $derived(!m.manualControlsEnabled || m.commandLoading);

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Enter") m.manualSend();
  }
</script>

<InspectorSection title="Manual Control">
  <div class="commands">
    <button class="btn btn--secondary btn--small" {disabled} title="Home all axes (G28)" onclick={() => m.sendCommand("G28")}>Home</button>
    <button class="btn btn--secondary btn--small" {disabled} title="Get current position (M114)" onclick={() => m.sendCommand("M114")}>Get Pos</button>
    <button
      class="btn btn--danger btn--small"
      {disabled}
      title="Emergency stop (M112) — WARNING: disconnects the controller"
      onclick={() => m.emergencyStop()}>E-Stop</button
    >
    <button class="btn btn--secondary btn--small" {disabled} title="Disable stepper motors (M18)" onclick={() => m.sendCommand("M18")}>Motors</button>
  </div>

  <label class="field-label" for="command-input">Command</label>
  <div class="row">
    <input
      id="command-input"
      class="input"
      type="text"
      placeholder="e.g. G0 X10 A20"
      bind:value={m.commandInput}
      onkeydown={onKeydown}
      {disabled}
    />
    <button
      class="btn btn--secondary btn--small"
      title="Send command"
      disabled={disabled || !m.commandInput.trim()}
      onclick={() => m.manualSend()}>Send</button
    >
  </div>
</InspectorSection>

<style>
  .commands {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--spacing-xs);
    margin-bottom: var(--spacing-sm);
  }
  .field-label {
    display: block;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin-bottom: var(--spacing-xs);
  }
  .row {
    display: flex;
    gap: var(--spacing-xs);
  }
  .input {
    flex: 1;
    height: var(--input-height-sm);
    border: 1px solid var(--color-border-control);
    border-radius: var(--border-radius-sm);
    background: var(--color-bg-panel-alt);
    color: var(--color-text);
    font-family: var(--font-family-mono);
    font-size: var(--font-size-sm);
    padding: 0 var(--spacing-sm);
    transition:
      var(--transition-colors),
      box-shadow var(--transition-fast);
  }
  .input:focus-visible {
    /* Transparent outline so forced-colors / high-contrast modes still show a ring. */
    outline: var(--border-width-medium) solid transparent;
    outline-offset: 2px;
    border-color: var(--color-border-focus);
    box-shadow: 0 0 0 var(--border-width-medium) var(--color-border-focus);
  }
  .input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
