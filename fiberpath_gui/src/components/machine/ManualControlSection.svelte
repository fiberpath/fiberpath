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
    <button class="cmd" {disabled} title="Home all axes (G28)" onclick={() => m.sendCommand("G28")}>Home</button>
    <button class="cmd" {disabled} title="Get current position (M114)" onclick={() => m.sendCommand("M114")}>Get Pos</button>
    <button
      class="cmd cmd--danger"
      {disabled}
      title="Emergency stop (M112) — WARNING: disconnects the controller"
      onclick={() => m.sendCommand("M112")}>E-Stop</button
    >
    <button class="cmd" {disabled} title="Disable stepper motors (M18)" onclick={() => m.sendCommand("M18")}>Motors</button>
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
      class="send"
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
  .cmd,
  .send,
  .input {
    appearance: none;
    border: 1px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    font-size: var(--font-size-sm);
    height: var(--input-height-sm);
  }
  .cmd,
  .send {
    background: var(--color-bg-panel-alt);
    color: var(--color-text);
    cursor: pointer;
  }
  .cmd--danger {
    border-color: var(--status-error);
    color: var(--status-error);
  }
  .cmd:disabled,
  .send:disabled,
  .input:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  .field-label {
    display: block;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    margin-bottom: 2px;
  }
  .row {
    display: flex;
    gap: var(--spacing-xs);
  }
  .input {
    flex: 1;
    background: var(--color-bg);
    color: var(--color-text);
    font-family: var(--font-family-mono);
    padding: 0 var(--spacing-sm);
  }
  .send {
    padding: 0 var(--spacing-md);
  }
</style>
