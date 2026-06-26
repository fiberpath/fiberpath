<script lang="ts">
  import { uiState } from "../state/ui-state.svelte";
  import { projectSession } from "../state/project-session.svelte";

  interface MenuItem {
    label: string;
    action?: () => void;
    disabled?: boolean;
    hint?: string;
    separatorBefore?: boolean;
  }
  interface Menu {
    id: string;
    label: string;
    items: MenuItem[];
  }

  // Items whose backing slice hasn't landed are present but disabled, so the menu
  // structure is faithful without dead-ending. They get wired in #217 (files /
  // layers) and #220 (dialogs / theme).
  const menus: Menu[] = [
    {
      id: "file",
      label: "File",
      items: [
        { label: "New Project", action: () => projectSession.newDocument() },
        { label: "Open…", disabled: true, hint: "File operations migrate in #217", separatorBefore: true },
        { label: "Save", disabled: true, hint: "File operations migrate in #217" },
        { label: "Save As…", disabled: true, hint: "File operations migrate in #217" },
        { label: "Export G-code", disabled: true, hint: "File operations migrate in #217", separatorBefore: true },
      ],
    },
    {
      id: "edit",
      label: "Edit",
      items: [
        { label: "Duplicate Layer", disabled: true, hint: "Layer editing migrates in #217" },
        { label: "Delete Layer", disabled: true, hint: "Layer editing migrates in #217" },
      ],
    },
    {
      id: "view",
      label: "View",
      items: [
        { label: "Prepare Workspace", action: () => uiState.setWorkspace("prepare") },
        { label: "Machine Workspace", action: () => uiState.setWorkspace("machine") },
        { label: "Toggle Left Inspector", action: () => uiState.toggleLeft(), separatorBefore: true },
        { label: "Toggle Right Inspector", action: () => uiState.toggleRight() },
        { label: "Toggle Bottom Drawer", action: () => uiState.toggleDrawer() },
      ],
    },
    {
      id: "help",
      label: "Help",
      items: [{ label: "About FiberPath", disabled: true, hint: "Dialogs migrate in #220" }],
    },
  ];

  let openMenu = $state<string | null>(null);
  let root = $state<HTMLElement>();

  function toggle(id: string) {
    openMenu = openMenu === id ? null : id;
  }

  function run(item: MenuItem) {
    if (item.disabled) return;
    item.action?.();
    openMenu = null;
  }

  function onWindowPointerDown(e: PointerEvent) {
    if (openMenu && root && !root.contains(e.target as Node)) {
      openMenu = null;
    }
  }
</script>

<svelte:window
  onpointerdown={onWindowPointerDown}
  onkeydown={(e) => e.key === "Escape" && (openMenu = null)}
/>

<div class="menubar" bind:this={root}>
  <span class="menubar__brand">FiberPath</span>
  {#each menus as menu (menu.id)}
    <div class="menubar__menu">
      <button
        class="menubar__top"
        class:menubar__top--open={openMenu === menu.id}
        aria-haspopup="true"
        aria-expanded={openMenu === menu.id}
        onclick={() => toggle(menu.id)}
        onpointerenter={() => openMenu !== null && (openMenu = menu.id)}
      >
        {menu.label}
      </button>
      {#if openMenu === menu.id}
        <div class="menubar__dropdown" role="menu">
          {#each menu.items as item (item.label)}
            {#if item.separatorBefore}<div class="menubar__sep" role="separator"></div>{/if}
            <button
              class="menubar__item"
              role="menuitem"
              disabled={item.disabled}
              title={item.hint ?? ""}
              onclick={() => run(item)}
            >
              {item.label}
            </button>
          {/each}
        </div>
      {/if}
    </div>
  {/each}
</div>

<style>
  .menubar {
    display: flex;
    align-items: stretch;
    height: var(--menubar-height);
    background: var(--color-bg-panel);
    border-bottom: 1px solid var(--color-border);
    font-size: var(--font-size-sm);
  }
  .menubar__brand {
    display: flex;
    align-items: center;
    padding: 0 var(--spacing-md);
    font-weight: var(--font-weight-semibold);
    color: var(--color-primary);
  }
  .menubar__menu {
    position: relative;
    display: flex;
  }
  .menubar__top {
    appearance: none;
    border: none;
    background: transparent;
    color: var(--color-text-muted);
    padding: 0 var(--spacing-md);
    cursor: pointer;
    transition: var(--transition-colors);
  }
  .menubar__top:hover,
  .menubar__top--open {
    color: var(--color-text);
    background: var(--color-bg-hover);
  }
  .menubar__dropdown {
    position: absolute;
    top: 100%;
    left: 0;
    min-width: 11rem;
    padding: var(--spacing-xs);
    background: var(--color-bg-panel-alt);
    border: 1px solid var(--color-border);
    border-radius: var(--border-radius-sm);
    box-shadow: var(--shadow-md);
    z-index: var(--z-index-dropdown);
  }
  .menubar__item {
    display: block;
    width: 100%;
    text-align: left;
    appearance: none;
    border: none;
    background: transparent;
    color: var(--color-text);
    font-size: var(--font-size-sm);
    padding: var(--spacing-xs) var(--spacing-sm);
    border-radius: var(--border-radius-sm);
    cursor: pointer;
  }
  .menubar__item:hover:not(:disabled) {
    background: var(--color-bg-hover);
  }
  .menubar__item:disabled {
    color: var(--color-text-muted);
    opacity: 0.5;
    cursor: not-allowed;
  }
  .menubar__sep {
    height: 1px;
    margin: var(--spacing-xs) 0;
    background: var(--color-border);
  }
</style>
