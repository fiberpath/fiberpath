import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import MandrelForm from "./MandrelForm.svelte";
import { projectSession } from "../../state/project-session.svelte";

beforeEach(() => {
  projectSession.newDocument();
});

describe("MandrelForm.svelte", () => {
  it("renders its fields", () => {
    render(MandrelForm);
    expect(screen.getByText("Diameter")).toBeInTheDocument();
  });

  it("shows the current diameter from the session", () => {
    projectSession.document.mandrel.diameter = 200;
    render(MandrelForm);
    const input = screen.getByLabelText("Diameter") as HTMLInputElement;
    expect(input.value).toBe("200");
  });

  it("shows the current wind_length from the session", () => {
    projectSession.document.mandrel.wind_length = 900;
    render(MandrelForm);
    const input = screen.getByLabelText("Wind Length") as HTMLInputElement;
    expect(input.value).toBe("900");
  });

  it("updates the mandrel when the diameter input changes", async () => {
    render(MandrelForm);
    const input = screen.getByLabelText("Diameter");
    await fireEvent.input(input, { target: { value: "180" } });
    expect(projectSession.document.mandrel.diameter).toBe(180);
  });

  it("updates the mandrel when the wind_length input changes", async () => {
    render(MandrelForm);
    const input = screen.getByLabelText("Wind Length");
    await fireEvent.input(input, { target: { value: "600" } });
    expect(projectSession.document.mandrel.wind_length).toBe(600);
  });

  it("shows a backend validation error for diameter", () => {
    projectSession.setValidationError("mandrel.diameter", "Too small");
    render(MandrelForm);
    expect(screen.getByText("Too small")).toBeInTheDocument();
  });

  it("shows a backend validation error for wind_length", () => {
    projectSession.setValidationError("mandrel.wind_length", "Too long");
    render(MandrelForm);
    expect(screen.getByText("Too long")).toBeInTheDocument();
  });

  it("validates on blur and shows a client error for an out-of-range diameter", async () => {
    render(MandrelForm);
    const input = screen.getByLabelText("Diameter");
    await fireEvent.input(input, { target: { value: "0" } });
    await fireEvent.blur(input, { target: { value: "0" } });
    expect(screen.getByText("Diameter must be greater than 0")).toBeInTheDocument();
  });

  it("live-validates after the debounce window without a blur", async () => {
    // Guards the slice's signature behaviour: the error must appear from the
    // 300ms debounced validator alone. Deleting the debounce wiring in onInput
    // makes this time out and fail.
    render(MandrelForm);
    await fireEvent.input(screen.getByLabelText("Diameter"), { target: { value: "0" } });
    await waitFor(() =>
      expect(screen.getByText("Diameter must be greater than 0")).toBeInTheDocument(),
    );
  });
});
