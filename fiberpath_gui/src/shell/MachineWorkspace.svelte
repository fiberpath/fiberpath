<script lang="ts">
  import ConnectionSection from "../components/machine/ConnectionSection.svelte";
  import ManualControlSection from "../components/machine/ManualControlSection.svelte";
  import FileStreamingSection from "../components/machine/FileStreamingSection.svelte";
  import StreamLog from "../components/machine/StreamLog.svelte";
</script>

<div class="machine">
  <div class="machine__controls">
    <ConnectionSection />
    <ManualControlSection />
    <FileStreamingSection />
  </div>
  <div class="machine__log">
    <StreamLog />
  </div>
</div>

<style>
  .machine {
    display: grid;
    grid-template-columns: var(--rail-width) 1fr;
    height: 100%;
    min-height: 0;
  }
  .machine__controls {
    overflow-y: auto;
    background: var(--color-bg-panel);
  }
  .machine__log {
    min-width: 0;
    min-height: 0;
  }
</style>
