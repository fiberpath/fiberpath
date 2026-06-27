<script lang="ts">
  import { fly, fade } from "svelte/transition";
  import { flip } from "svelte/animate";
  import { prefersReducedMotion } from "svelte/motion";
  import { notifications, type ToastType } from "../state/notifications.svelte";

  const symbol = (t: ToastType) =>
    t === "success" ? "✓" : t === "error" ? "✕" : t === "warning" ? "⚠" : "ⓘ";

  // Collapse the JS transitions to instant under reduced motion (the CSS
  // @media reset cannot reach Svelte's rAF-driven transitions).
  const motionDuration = $derived(prefersReducedMotion.current ? 0 : 150);
</script>

{#if notifications.toasts.length > 0}
  <div class="toast-container">
    {#each notifications.toasts as toast (toast.id)}
      <div
        class="toast"
        data-type={toast.type}
        role={toast.type === "error" || toast.type === "warning" ? "alert" : "status"}
        onmouseenter={() => notifications.pause(toast.id)}
        onmouseleave={() => notifications.resume(toast.id)}
        onfocusin={() => notifications.pause(toast.id)}
        onfocusout={() => notifications.resume(toast.id)}
        in:fly={{ x: prefersReducedMotion.current ? 0 : 16, duration: motionDuration }}
        out:fade={{ duration: motionDuration }}
        animate:flip={{ duration: motionDuration }}
      >
        <span class="toast__icon" aria-hidden="true">{symbol(toast.type)}</span>
        <span class="toast__message">{toast.message}</span>
        <button
          class="icon-btn"
          aria-label="Close notification"
          onclick={() => notifications.dismiss(toast.id)}>×</button
        >
      </div>
    {/each}
  </div>
{/if}

<style>
  /* Self-contained (ported from the React ToastContainer.css, which the Svelte
     entry doesn't import). A fixed overlay so it floats above the app shell. */
  .toast-container {
    position: fixed;
    top: calc(var(--menubar-height) + var(--statusbar-height) + var(--spacing-lg));
    right: var(--spacing-xl);
    z-index: var(--z-index-toast);
    display: flex;
    flex-direction: column;
    gap: var(--spacing-md);
    max-width: 25rem;
  }
  .toast {
    display: flex;
    align-items: center;
    gap: var(--spacing-md);
    padding: var(--spacing-md) var(--spacing-lg);
    border: 1px solid var(--color-border);
    border-radius: var(--border-radius-md);
    background: var(--color-bg-panel);
    box-shadow: var(--shadow-md);
  }
  .toast__icon {
    flex-shrink: 0;
  }
  .toast__message {
    flex: 1;
    color: var(--color-text);
    font-size: var(--font-size-base);
    line-height: var(--line-height-normal);
  }
  .toast[data-type="success"] {
    border-color: var(--status-success-fg);
  }
  .toast[data-type="success"] .toast__icon {
    color: var(--status-success-fg);
  }
  .toast[data-type="error"] {
    border-color: var(--status-error-fg);
  }
  .toast[data-type="error"] .toast__icon {
    color: var(--status-error-fg);
  }
  .toast[data-type="warning"] {
    border-color: var(--status-warning-fg);
  }
  .toast[data-type="warning"] .toast__icon {
    color: var(--status-warning-fg);
  }
  .toast[data-type="info"] {
    border-color: var(--status-info-fg);
  }
  .toast[data-type="info"] .toast__icon {
    color: var(--status-info-fg);
  }
  /* Close uses the shared .icon-btn system (buttons.css); only nudge layout. */
  .toast .icon-btn {
    flex-shrink: 0;
  }
</style>
