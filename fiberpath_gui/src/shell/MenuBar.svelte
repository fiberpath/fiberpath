<script lang="ts">
  import { uiState } from "../state/ui-state.svelte";
  import { projectSession } from "../state/project-session.svelte";
  import { theme } from "../state/theme.svelte";
  import * as fileOps from "../services/file-operations.svelte";

  interface MenuItem {
    label: string;
    action?: () => void;
    disabled?: boolean;
    hint?: string;
    separatorBefore?: boolean;
  }

  function duplicateSelected() {
    if (projectSession.selectedLayerId) {
      projectSession.duplicateLayer(projectSession.selectedLayerId);
    }
  }
  function deleteSelected() {
    if (projectSession.selectedLayerId) {
      projectSession.removeLayer(projectSession.selectedLayerId);
    }
  }
  interface Menu {
    id: string;
    label: string;
    items: MenuItem[];
  }

  // Items whose backing slice hasn't landed are present but disabled (About →
  // dialogs migrate in #220).
  const menus: Menu[] = [
    {
      id: "file",
      label: "File",
      items: [
        { label: "New Project", action: () => fileOps.newProject() },
        { label: "Open…", action: () => fileOps.openProject(), separatorBefore: true },
        { label: "Save", action: () => fileOps.saveProject() },
        { label: "Save As…", action: () => fileOps.saveProjectAs() },
        { label: "Export G-code", action: () => fileOps.exportGcode(), separatorBefore: true },
      ],
    },
    {
      id: "edit",
      label: "Edit",
      items: [
        { label: "Duplicate Layer", action: duplicateSelected },
        { label: "Delete Layer", action: deleteSelected },
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
        { label: "Cycle Theme (dark / light / system)", action: () => theme.cycle(), separatorBefore: true },
      ],
    },
    {
      id: "help",
      label: "Help",
      items: [
        { label: "Diagnostics", action: () => uiState.openDialog("diagnostics") },
        { label: "About FiberPath", action: () => uiState.openDialog("about") },
      ],
    },
  ];

  let openMenu = $state<string | null>(null);
  let root = $state<HTMLElement>();

  function toggle(id: string) {
    openMenu = openMenu === id ? null : id;
  }

  function run(item: MenuItem) {
    if (item.disabled) return;
    openMenu = null;
    // File ops are async and self-report errors via toasts; swallow any rejection
    // (e.g. a dialog cancelled at the OS level) so it never bubbles as unhandled.
    const result = item.action?.() as unknown;
    if (result instanceof Promise) result.catch(() => {});
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
              class="menu-item"
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
  /* Dropdown items use the shared .menu-item class (buttons.css). */
  .menubar__sep {
    height: 1px;
    margin: var(--spacing-xs) 0;
    background: var(--color-border);
  }
</style>
