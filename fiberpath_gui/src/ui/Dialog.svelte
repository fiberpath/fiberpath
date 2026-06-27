<script lang="ts" module>
  let nextDialogId = 0;
</script>

<script lang="ts">
  import { onMount, tick, type Snippet } from "svelte";

  interface Props {
    title: string;
    onclose: () => void;
    contentClass?: string;
    footer?: Snippet;
    children: Snippet;
  }

  let { title, onclose, contentClass = "", footer, children }: Props = $props();

  const titleId = `dialog-title-${nextDialogId++}`;
  let contentEl = $state<HTMLDivElement | null>(null);

  function focusable(): HTMLElement[] {
    if (!contentEl) return [];
    return Array.from(
      contentEl.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => el.offsetParent !== null);
  }

  // On open: remember the trigger, move focus inside; on close: restore it.
  onMount(() => {
    const trigger = document.activeElement as HTMLElement | null;
    void tick().then(() => (focusable()[0] ?? contentEl)?.focus());
    return () => trigger?.focus?.();
  });

  function onKeydown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      onclose();
      return;
    }
    if (e.key !== "Tab") return;
    const items = focusable();
    if (items.length === 0) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function onOverlay(e: MouseEvent) {
    if (e.target === e.currentTarget) onclose();
  }
</script>

<svelte:window onkeydown={onKeydown} />

<!-- The backdrop click-to-close is an enhancement; Escape and the × button are
     the accessible closers. role=presentation marks the backdrop as decorative. -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div class="dialog-overlay" role="presentation" onclick={onOverlay}>
  <div
    bind:this={contentEl}
    class={`dialog-content ${contentClass}`}
    role="dialog"
    aria-modal="true"
    aria-labelledby={titleId}
  >
    <div class="dialog-header">
      <h2 id={titleId}>{title}</h2>
      <button class="icon-btn icon-btn--lg" aria-label="Close" onclick={onclose}>×</button>
    </div>
    <div class="dialog-body">{@render children()}</div>
    {#if footer}<div class="dialog-footer">{@render footer()}</div>{/if}
  </div>
</div>
