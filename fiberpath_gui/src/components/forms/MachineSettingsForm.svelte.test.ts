import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import MachineSettingsForm from "./MachineSettingsForm.svelte";
import { projectSession } from "../../state/project-session.svelte";

beforeEach(() => {
  projectSession.newDocument();
});

describe("MachineSettingsForm.svelte", () => {
  it("renders its fields", () => {
    render(MachineSettingsForm);
    expect(screen.getByText("Default Feed Rate")).toBeInTheDocument();
  });

  it("shows the current feed rate from the session", () => {
    projectSession.document.defaultFeedRate = 1200;
    render(MachineSettingsForm);
    expect((screen.getByLabelText("Default Feed Rate") as HTMLInputElement).value).toBe("1200");
  });

  it("updates the feed rate when the input changes", async () => {
    render(MachineSettingsForm);
    await fireEvent.input(screen.getByLabelText("Default Feed Rate"), {
      target: { value: "800" },
    });
    expect(projectSession.document.defaultFeedRate).toBe(800);
  });

  it("shows a backend validation error for the feed rate", () => {
    projectSession.setValidationError("machine.defaultFeedRate", "Bad feed rate");
    render(MachineSettingsForm);
    expect(screen.getByText("Bad feed rate")).toBeInTheDocument();
  });

  it("validates on blur and rejects a non-positive feed rate", async () => {
    render(MachineSettingsForm);
    const input = screen.getByLabelText("Default Feed Rate");
    await fireEvent.input(input, { target: { value: "0" } });
    await fireEvent.blur(input, { target: { value: "0" } });
    expect(screen.getByText("Feed rate must be greater than 0")).toBeInTheDocument();
  });

  it("validates on blur and rejects an unreasonably high feed rate", async () => {
    render(MachineSettingsForm);
    const input = screen.getByLabelText("Default Feed Rate");
    await fireEvent.input(input, { target: { value: "99999" } });
    await fireEvent.blur(input, { target: { value: "99999" } });
    expect(screen.getByText("Feed rate seems unreasonably high")).toBeInTheDocument();
  });

  it("live-validates after the debounce window without a blur", async () => {
    render(MachineSettingsForm);
    await fireEvent.input(screen.getByLabelText("Default Feed Rate"), { target: { value: "0" } });
    await waitFor(() =>
      expect(screen.getByText("Feed rate must be greater than 0")).toBeInTheDocument(),
    );
  });
});
