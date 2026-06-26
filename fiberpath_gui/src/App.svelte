<script lang="ts">
  // The Svelte app shell. Unlike the React `App`, which assembled every region as
  // element trees and threaded them through `MainTab` as four `ReactNode` props,
  // each region is a component that owns its own layout here.
  //
  // index.html keeps mounting React until the #221 cutover; this is reachable via
  // the dev-only index.svelte.html entry.
  import MenuBar from "./shell/MenuBar.svelte";
  import WorkspaceTabs from "./shell/WorkspaceTabs.svelte";
  import StatusBar from "./shell/StatusBar.svelte";
  import PrepareWorkspace from "./shell/PrepareWorkspace.svelte";
  import MachineWorkspace from "./shell/MachineWorkspace.svelte";
  import UtilityDrawer from "./shell/UtilityDrawer.svelte";
  import { uiState } from "./state/ui-state.svelte";
  import { projectSession } from "./state/project-session.svelte";

  function onKeydown(e: KeyboardEvent) {
    if (e.altKey && !e.ctrlKey && !e.shiftKey) {
      if (e.key === "1") {
        e.preventDefault();
        uiState.setWorkspace("prepare");
      } else if (e.key === "2") {
        e.preventDefault();
        uiState.setWorkspace("machine");
      }
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

<div class="app">
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

<style>
  .app {
    display: grid;
    grid-template-rows: auto auto 1fr auto auto;
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
