import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import Viewport from "./Viewport.svelte";
import { projectSession } from "../../state/project-session.svelte";
import { previewSession } from "../../state/preview-session.svelte";

beforeEach(() => {
  vi.restoreAllMocks();
  projectSession.newDocument();
  previewSession.reset();
});

describe("Viewport.svelte", () => {
  it("shows the empty state when there are no layers", () => {
    render(Viewport);
    expect(screen.getByText("No layers to visualize")).toBeInTheDocument();
  });

  it("shows the scrubber and generate button when layers exist", () => {
    projectSession.addLayer("helical");
    render(Viewport);
    expect(screen.getByText(/Preview Layers/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Generate preview" })).toBeInTheDocument();
  });

  it("calls generate when the button is clicked", async () => {
    projectSession.addLayer("helical");
    const spy = vi.spyOn(previewSession, "generate").mockResolvedValue();
    render(Viewport);
    await fireEvent.click(screen.getByRole("button", { name: "Generate preview" }));
    expect(spy).toHaveBeenCalled();
  });

  it("shows the error state with a retry button", () => {
    projectSession.addLayer("helical");
    previewSession.error = "backend down";
    render(Viewport);
    expect(screen.getByText("backend down")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("renders the image and zoom controls when a preview exists", () => {
    projectSession.addLayer("helical");
    previewSession.image = "data:image/png;base64,QUJD";
    render(Viewport);
    expect(screen.getByAltText("Toolpath preview")).toBeInTheDocument();
    expect(screen.getByTitle("Zoom in")).toBeInTheDocument();
    expect(screen.getByTitle("Zoom out")).toBeInTheDocument();
    expect(screen.getByTitle("Reset zoom")).toBeInTheDocument();
    expect(screen.getByTitle("Export G-code")).toBeInTheDocument();
  });

  it("zooms via the wheel (wired to the pan/zoom controller)", async () => {
    projectSession.addLayer("helical");
    previewSession.image = "data:image/png;base64,QUJD";
    const { container } = render(Viewport);
    const stage = container.querySelector(".vp__stage")!;
    const content = container.querySelector(".vp__transform") as HTMLElement;

    await fireEvent.wheel(stage, { deltaY: -100, clientX: 100, clientY: 100 });
    expect(content.style.transform).toContain("scale(1.1)");
  });

  it("zooms via the toolbar buttons", async () => {
    projectSession.addLayer("helical");
    previewSession.image = "data:image/png;base64,QUJD";
    const { container } = render(Viewport);
    const content = container.querySelector(".vp__transform") as HTMLElement;

    await fireEvent.click(screen.getByTitle("Zoom in"));
    expect(content.style.transform).toContain("scale(1.2)");
  });
});
