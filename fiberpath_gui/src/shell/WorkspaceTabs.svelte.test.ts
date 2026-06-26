import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import WorkspaceTabs from "./WorkspaceTabs.svelte";
import { uiState } from "../state/ui-state.svelte";

beforeEach(() => uiState.setWorkspace("prepare"));

describe("WorkspaceTabs.svelte", () => {
  it("renders Prepare and Machine tabs", () => {
    render(WorkspaceTabs);
    expect(screen.getByRole("button", { name: "Prepare" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Machine" })).toBeInTheDocument();
  });

  it("marks the active workspace and switches on click", async () => {
    render(WorkspaceTabs);
    const machine = screen.getByRole("button", { name: "Machine" });
    expect(machine).toHaveAttribute("aria-current", "false");

    await fireEvent.click(machine);
    expect(uiState.workspace).toBe("machine");
    expect(machine).toHaveAttribute("aria-current", "true");
  });
});
