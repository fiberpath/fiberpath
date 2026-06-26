/**
 * Transient shell UI state (which workspace is active, panel/drawer visibility).
 * Deliberately separate from {@link projectSession} — none of this belongs in a
 * saved document. Replaces the scattered `useState` flags in the React `App`.
 */
export type WorkspaceId = "prepare" | "machine";

export class UiState {
  workspace = $state<WorkspaceId>("prepare");
  leftCollapsed = $state(false);
  rightCollapsed = $state(false);
  /** Bottom utility drawer — closed by default (only opened on demand). */
  drawerOpen = $state(false);

  setWorkspace(id: WorkspaceId) {
    this.workspace = id;
  }

  toggleLeft() {
    this.leftCollapsed = !this.leftCollapsed;
  }

  toggleRight() {
    this.rightCollapsed = !this.rightCollapsed;
  }

  toggleDrawer() {
    this.drawerOpen = !this.drawerOpen;
  }
}

export const uiState = new UiState();
