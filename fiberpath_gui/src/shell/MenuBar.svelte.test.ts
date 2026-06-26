import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import MenuBar from "./MenuBar.svelte";
import { uiState } from "../state/ui-state.svelte";
import { projectSession } from "../state/project-session.svelte";

beforeEach(() => {
  uiState.setWorkspace("prepare");
  uiState.drawerOpen = false;
  uiState.leftCollapsed = false;
  uiState.rightCollapsed = false;
  projectSession.newDocument();
});

describe("MenuBar.svelte", () => {
  it("renders the top-level menus", () => {
    render(MenuBar);
    for (const label of ["File", "Edit", "View", "Help"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("opens a dropdown on click and closes it on Escape", async () => {
    render(MenuBar);
    await fireEvent.click(screen.getByRole("button", { name: "File" }));
    expect(screen.getByRole("menuitem", { name: "New Project" })).toBeInTheDocument();
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("menuitem", { name: "New Project" })).toBeNull();
  });

  it("closes the open dropdown on an outside pointer press", async () => {
    render(MenuBar);
    await fireEvent.click(screen.getByRole("button", { name: "File" }));
    expect(screen.getByRole("menuitem", { name: "New Project" })).toBeInTheDocument();

    await fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("menuitem", { name: "New Project" })).toBeNull();
  });

  it("New Project resets the document (clears dirty)", async () => {
    projectSession.updateMandrel({ diameter: 999 });
    expect(projectSession.isDirty).toBe(true);

    render(MenuBar);
    await fireEvent.click(screen.getByRole("button", { name: "File" }));
    await fireEvent.click(screen.getByRole("menuitem", { name: "New Project" }));

    expect(projectSession.isDirty).toBe(false);
    expect(projectSession.document.mandrel.diameter).toBe(150);
  });

  it("disables file-operation items that haven't migrated yet", async () => {
    render(MenuBar);
    await fireEvent.click(screen.getByRole("button", { name: "File" }));
    expect(screen.getByRole("menuitem", { name: "Save" })).toBeDisabled();
    expect(screen.getByRole("menuitem", { name: "Export G-code" })).toBeDisabled();
  });

  it("View menu switches workspace and toggles the drawer", async () => {
    render(MenuBar);
    await fireEvent.click(screen.getByRole("button", { name: "View" }));
    await fireEvent.click(screen.getByRole("menuitem", { name: "Machine Workspace" }));
    expect(uiState.workspace).toBe("machine");

    await fireEvent.click(screen.getByRole("button", { name: "View" }));
    await fireEvent.click(screen.getByRole("menuitem", { name: "Toggle Bottom Drawer" }));
    expect(uiState.drawerOpen).toBe(true);
  });
});
