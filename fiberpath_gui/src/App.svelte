<script lang="ts">
  // The Svelte app shell: each region is a component that owns its own layout
  // (the former React `App` assembled element trees and threaded them through
  // `MainTab` as four `ReactNode` props).
  import MenuBar from "./shell/MenuBar.svelte";
  import WorkspaceTabs from "./shell/WorkspaceTabs.svelte";
  import StatusBar from "./shell/StatusBar.svelte";
  import PrepareWorkspace from "./shell/PrepareWorkspace.svelte";
  import MachineWorkspace from "./shell/MachineWorkspace.svelte";
  import UtilityDrawer from "./shell/UtilityDrawer.svelte";
  import Toasts from "./shell/Toasts.svelte";
  import CliHealthWarning from "./components/machine/CliHealthWarning.svelte";
  import AboutDialog from "./components/dialogs/AboutDialog.svelte";
  import DiagnosticsDialog from "./components/dialogs/DiagnosticsDialog.svelte";
  import { onMount } from "svelte";
  import { uiState } from "./state/ui-state.svelte";
  import { projectSession } from "./state/project-session.svelte";
  import { theme } from "./state/theme.svelte";
  import { cliHealth } from "./state/cli-health.svelte";
  import * as fileOps from "./services/file-operations.svelte";

  // Apply the theme preference to the document root.
  $effect(() => {
    const root = document.documentElement;
    if (theme.preference === null) root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme.preference);
  });

  onMount(() => {
    const stopWatch = theme.watchSystem();
    const stopPoll = cliHealth.startPolling();
    return () => {
      stopWatch();
      stopPoll();
    };
  });

  function isTyping(target: EventTarget | null): boolean {
    const el = target as HTMLElement | null;
    if (!el) return false;
    return (
      el.tagName === "INPUT" ||
      el.tagName === "TEXTAREA" ||
      el.tagName === "SELECT" ||
      el.isContentEditable === true
    );
  }

  function ignore(p: Promise<unknown>) {
    p.catch(() => {});
  }

  function onKeydown(e: KeyboardEvent) {
    // Workspace switch works anywhere (Alt+1/2).
    if (e.altKey && !e.ctrlKey && !e.shiftKey && !e.metaKey) {
      if (e.key === "1") {
        e.preventDefault();
        uiState.setWorkspace("prepare");
        return;
      }
      if (e.key === "2") {
        e.preventDefault();
        uiState.setWorkspace("machine");
        return;
      }
    }

    // The rest are disabled while typing in a field (matches the React app).
    if (isTyping(e.target)) return;

    // Exclude Alt so Ctrl+Alt (AltGr on international layouts) can't fire shortcuts.
    const mod = (e.metaKey || e.ctrlKey) && !e.altKey;
    if (mod) {
      switch (e.key.toLowerCase()) {
        case "n": e.preventDefault(); ignore(fileOps.newProject()); break;
        case "o": e.preventDefault(); ignore(fileOps.openProject()); break;
        case "s":
          e.preventDefault();
          ignore(e.shiftKey ? fileOps.saveProjectAs() : fileOps.saveProject());
          break;
        case "e": e.preventDefault(); ignore(fileOps.exportGcode()); break;
        case "d":
          e.preventDefault();
          if (projectSession.selectedLayerId) {
            projectSession.duplicateLayer(projectSession.selectedLayerId);
          }
          break;
      }
    } else if (e.key === "Delete" && projectSession.selectedLayerId) {
      projectSession.removeLayer(projectSession.selectedLayerId);
    }
  }

  function onBeforeUnload(e: BeforeUnloadEvent) {
    if (projectSession.isDirty) {
      e.preventDefault();
      e.returnValue = "";
    }
  }
</script>

<svelte:window onkeydown={onKeydown} onbeforeunload={onBeforeUnload} />

<svelte:boundary>
  <div class="app">
    <CliHealthWarning />
    <MenuBar />
    <WorkspaceTabs />
    <main class="app__workspace">
      {#if uiState.workspace === "prepare"}
        <PrepareWorkspace />
      {:else}
        <MachineWorkspace />
      {/if}
    </main>
    <UtilityDrawer />
    <StatusBar />
  </div>

  <Toasts />

  {#if uiState.activeDialog === "about"}
    <AboutDialog onclose={() => uiState.closeDialog()} />
  {:else if uiState.activeDialog === "diagnostics"}
    <DiagnosticsDialog onclose={() => uiState.closeDialog()} />
  {/if}

  {#snippet failed(error)}
    <div class="error-boundary">
      <h1 class="error-boundary__title">Something went wrong</h1>
      <p class="error-boundary__message">An unexpected error occurred. Please reload the app.</p>
      <details class="error-boundary__details">
        <summary class="error-boundary__summary">Error details</summary>
        <pre class="error-boundary__stack">{String(error)}</pre>
      </details>
      <button class="btn btn--primary error-boundary__reload" onclick={() => location.reload()}>
        Reload Application
      </button>
    </div>
  {/snippet}
</svelte:boundary>

<style>
  .app {
    display: grid;
    /* banner (0 when healthy) · menubar · tabs · workspace · drawer · statusbar */
    grid-template-rows: auto auto auto 1fr auto auto;
    height: 100vh;
    overflow: hidden;
    background: var(--color-bg);
    color: var(--color-text);
    font-family: var(--font-family-base);
    font-size: var(--font-size-base);
  }
  .app__workspace {
    min-height: 0;
    overflow: hidden;
  }
</style>
