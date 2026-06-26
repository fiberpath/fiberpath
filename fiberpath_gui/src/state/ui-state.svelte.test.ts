import { describe, it, expect, beforeEach } from "vitest";
import { UiState } from "./ui-state.svelte";

describe("UiState", () => {
  let ui: UiState;
  beforeEach(() => {
    ui = new UiState();
  });

  it("defaults to the Prepare workspace with panels shown and drawer closed", () => {
    expect(ui.workspace).toBe("prepare");
    expect(ui.leftCollapsed).toBe(false);
    expect(ui.rightCollapsed).toBe(false);
    expect(ui.drawerOpen).toBe(false);
  });

  it("switches workspace", () => {
    ui.setWorkspace("machine");
    expect(ui.workspace).toBe("machine");
    ui.setWorkspace("prepare");
    expect(ui.workspace).toBe("prepare");
  });

  it("toggles the inspectors and the drawer", () => {
    ui.toggleLeft();
    ui.toggleRight();
    ui.toggleDrawer();
    expect(ui.leftCollapsed).toBe(true);
    expect(ui.rightCollapsed).toBe(true);
    expect(ui.drawerOpen).toBe(true);
    ui.toggleLeft();
    expect(ui.leftCollapsed).toBe(false);
  });
});
