import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(() => Promise.reject(new Error("no cli"))) }));

import { render, screen, fireEvent } from "@testing-library/svelte";
import BackendStatusBanner from "./BackendStatusBanner.svelte";
import { backendHealth } from "../state/backend-health.svelte";

beforeEach(() => {
  backendHealth.status = "ready";
});

describe("BackendStatusBanner.svelte", () => {
  it("shows nothing while the backend is healthy", () => {
    backendHealth.status = "ready";
    render(BackendStatusBanner);
    expect(screen.queryByText("Backend Unavailable")).toBeNull();
  });

  it("shows the banner when unavailable and opens the details dialog", async () => {
    backendHealth.status = "unavailable";
    backendHealth.errorMessage = "CLI not found on PATH";
    render(BackendStatusBanner);

    expect(screen.getByText("Backend Unavailable")).toBeInTheDocument();

    await fireEvent.click(screen.getByRole("button", { name: "Details" }));
    // the dialog (separate title) opens
    expect(screen.getByText("Troubleshooting")).toBeInTheDocument();
    expect(screen.getByText("CLI not found on PATH")).toBeInTheDocument();
  });
});
