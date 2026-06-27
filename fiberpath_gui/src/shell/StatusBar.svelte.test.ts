import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/svelte";
import StatusBar from "./StatusBar.svelte";
import { projectSession } from "../state/project-session.svelte";

beforeEach(() => projectSession.newDocument());

describe("StatusBar.svelte", () => {
  it("shows Untitled and no layer count for a fresh document", () => {
    render(StatusBar);
    expect(screen.getByText("Untitled")).toBeInTheDocument();
    expect(screen.queryByText("Layers:")).toBeNull();
    expect(screen.getByText("Backend: Unknown")).toBeInTheDocument();
  });

  it("derives the project name from the file path", () => {
    projectSession.filePath = "/home/cam/cylinder.wind";
    render(StatusBar);
    expect(screen.getByText("cylinder.wind")).toBeInTheDocument();
  });

  it("shows the layer count when there are layers", () => {
    projectSession.document.layers = [
      { id: "a", type: "hoop", hoop: { terminal: false } },
    ];
    render(StatusBar);
    expect(screen.getByText("Layers:")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("shows the dirty marker after a mutation", () => {
    projectSession.updateMandrel({ diameter: 99 });
    render(StatusBar);
    expect(screen.getByText(/unsaved changes/i)).toBeInTheDocument();
  });
});
