<script lang="ts">
  import type { Snippet } from "svelte";

  interface Props {
    title: string;
    /** Optional action rendered at the right of the header (e.g. an Add button). */
    action?: Snippet;
    children: Snippet;
  }

  let { title, action, children }: Props = $props();
</script>

<section class="section">
  <header class="section__header">
    <h2 class="section-eyebrow">{title}</h2>
    {#if action}<div class="section__action">{@render action()}</div>{/if}
  </header>
  <div class="section__body">
    {@render children()}
  </div>
</section>

<style>
  .section {
    border-bottom: 1px solid var(--color-border);
  }
  .section__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: var(--input-height-sm);
    padding: 0 var(--spacing-md);
    border-bottom: 1px solid var(--color-border-soft);
  }
  .section__body {
    padding: var(--spacing-md);
  }
</style>
