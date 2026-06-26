import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import App from "./App.svelte";
import { uiState } from "./state/ui-state.svelte";
import { projectSession } from "./state/project-session.svelte";

beforeEach(() => {
  uiState.setWorkspace("prepare");
  uiState.leftCollapsed = false;
  uiState.rightCollapsed = false;
  uiState.drawerOpen = false;
  projectSession.newDocument();
});

describe("App.svelte (shell)", () => {
  it("renders the Prepare workspace with the config forms and viewport placeholder", () => {
    render(App);
    expect(screen.getByText("Mandrel Parameters")).toBeInTheDocument();
    expect(screen.getByText("Tow Parameters")).toBeInTheDocument();
    expect(screen.getByText("Machine Settings")).toBeInTheDocument();
    expect(screen.getByText("Toolpath preview")).toBeInTheDocument();
    expect(screen.getByText("Layer Properties")).toBeInTheDocument();
    expect(screen.getByText("Not connected")).toBeInTheDocument();
  });

  it("switches to the Machine workspace on Alt+2 and back on Alt+1", async () => {
    render(App);
    await fireEvent.keyDown(window, { key: "2", altKey: true });
    expect(screen.getByText("Machine control")).toBeInTheDocument();
    expect(screen.queryByText("Mandrel Parameters")).toBeNull();

    await fireEvent.keyDown(window, { key: "1", altKey: true });
    expect(screen.getByText("Mandrel Parameters")).toBeInTheDocument();
  });

  it("hides the left inspector when collapsed", () => {
    uiState.leftCollapsed = true;
    render(App);
    expect(screen.queryByText("Mandrel Parameters")).toBeNull();
    // viewport still present
    expect(screen.getByText("Toolpath preview")).toBeInTheDocument();
  });

  it("opens the utility drawer from its handle", async () => {
    render(App);
    expect(screen.queryByText(/Console, G-code and diagnostics/)).toBeNull();
    await fireEvent.click(screen.getByRole("button", { name: /Utility/ }));
    expect(screen.getByText(/Console, G-code and diagnostics/)).toBeInTheDocument();
  });

  it("blocks unload only when the document is dirty", () => {
    render(App);

    const clean = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(clean);
    expect(clean.defaultPrevented).toBe(false);

    projectSession.updateMandrel({ diameter: 123 });
    const dirty = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(dirty);
    expect(dirty.defaultPrevented).toBe(true);
  });
});
