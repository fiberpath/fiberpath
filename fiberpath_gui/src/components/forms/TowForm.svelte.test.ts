import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import TowForm from "./TowForm.svelte";
import { projectSession } from "../../state/project-session.svelte";

beforeEach(() => {
  projectSession.newDocument();
});

describe("TowForm.svelte", () => {
  it("renders its fields", () => {
    render(TowForm);
    expect(screen.getByText("Width")).toBeInTheDocument();
  });

  it("shows the current width and thickness from the session", () => {
    projectSession.document.tow.width = 8;
    projectSession.document.tow.thickness = 0.5;
    render(TowForm);
    expect((screen.getByLabelText("Width") as HTMLInputElement).value).toBe("8");
    expect((screen.getByLabelText("Thickness") as HTMLInputElement).value).toBe("0.5");
  });

  it("updates the tow when the width input changes", async () => {
    render(TowForm);
    await fireEvent.input(screen.getByLabelText("Width"), { target: { value: "10" } });
    expect(projectSession.document.tow.width).toBe(10);
  });

  it("updates the tow when the thickness input changes", async () => {
    render(TowForm);
    await fireEvent.input(screen.getByLabelText("Thickness"), { target: { value: "0.3" } });
    expect(projectSession.document.tow.thickness).toBe(0.3);
  });

  it("shows backend validation errors for width and thickness", () => {
    projectSession.setValidationError("tow.width", "Bad width");
    render(TowForm);
    expect(screen.getByText("Bad width")).toBeInTheDocument();
  });

  it("validates on blur and shows a client error for a non-positive width", async () => {
    render(TowForm);
    const input = screen.getByLabelText("Width");
    await fireEvent.input(input, { target: { value: "0" } });
    await fireEvent.blur(input, { target: { value: "0" } });
    expect(screen.getByText("Width must be greater than 0")).toBeInTheDocument();
  });

  it("live-validates after the debounce window without a blur", async () => {
    render(TowForm);
    await fireEvent.input(screen.getByLabelText("Width"), { target: { value: "0" } });
    await waitFor(() =>
      expect(screen.getByText("Width must be greater than 0")).toBeInTheDocument(),
    );
  });
});
