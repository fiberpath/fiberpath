<script lang="ts">
  import { onMount } from "svelte";
  import { getVersion } from "@tauri-apps/api/app";
  import { open as openExternal } from "@tauri-apps/plugin-shell";
  import Dialog from "../../ui/Dialog.svelte";

  let { onclose }: { onclose: () => void } = $props();

  let version = $state("…");
  onMount(() => {
    getVersion()
      .then((v) => (version = v))
      .catch(() => (version = "—"));
  });

  const link = (url: string) => () => void openExternal(url).catch(() => {});
</script>

<Dialog title="About FiberPath" {onclose} contentClass="dialog-content--small">
  <div class="about-section">
    <div class="about-logo">
      <div class="about-icon">🧵</div>
      <div class="about-title">
        <h3>FiberPath</h3>
        <p class="about-version">Version {version}</p>
      </div>
    </div>
  </div>

  <div class="about-section">
    <p class="about-description">
      Filament winding path planning and G-code generation for composite manufacturing.
      Create optimized winding patterns for cylindrical mandrels with helical, hoop and
      skip layers.
    </p>
  </div>

  <div class="about-section">
    <h4>Links</h4>
    <div class="about-links">
      <button class="btn btn--secondary btn--block btn--start" onclick={link("https://fiberpath.org/fiberpath")}>📚 Documentation</button>
      <button class="btn btn--secondary btn--block btn--start" onclick={link("https://github.com/fiberpath/fiberpath")}>💻 GitHub Repository</button>
    </div>
  </div>

  <div class="about-section about-footer">
    <p class="about-copyright">© 2026 Cameron Brooks</p>
    <p class="about-license">Open source software licensed under AGPL v3.</p>
  </div>
</Dialog>
