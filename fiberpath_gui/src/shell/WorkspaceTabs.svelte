<script lang="ts">
  import { uiState, type WorkspaceId } from "../state/ui-state.svelte";

  const tabs: { id: WorkspaceId; label: string; hint: string }[] = [
    { id: "prepare", label: "Prepare", hint: "Configure, design and preview (Alt+1)" },
    { id: "machine", label: "Machine", hint: "Connect and stream to hardware (Alt+2)" },
  ];
</script>

<nav class="tabs" aria-label="Workspace">
  {#each tabs as tab (tab.id)}
    <button
      class="tabs__tab"
      class:tabs__tab--active={uiState.workspace === tab.id}
      aria-current={uiState.workspace === tab.id}
      title={tab.hint}
      onclick={() => uiState.setWorkspace(tab.id)}
    >
      {tab.label}
    </button>
  {/each}
</nav>

<style>
  .tabs {
    display: flex;
    gap: 2px;
    align-items: stretch;
    height: 2rem;
    padding: 0 var(--spacing-sm);
    background: var(--color-bg-panel);
    border-bottom: 1px solid var(--color-border);
  }
  .tabs__tab {
    appearance: none;
    border: none;
    background: transparent;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    font-weight: var(--font-weight-medium);
    padding: 0 var(--spacing-md);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: var(--transition-colors);
  }
  .tabs__tab:hover {
    color: var(--color-text);
    background: var(--color-bg-hover);
  }
  .tabs__tab--active {
    color: var(--color-text);
    border-bottom-color: var(--color-primary);
  }
</style>
