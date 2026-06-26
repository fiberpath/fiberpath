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
    <h2 class="section__title">{title}</h2>
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
    height: 1.75rem;
    padding: 0 var(--spacing-md);
    background: var(--color-bg-panel-alt);
  }
  .section__title {
    margin: 0;
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-semibold);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  .section__body {
    padding: var(--spacing-md);
  }
</style>
