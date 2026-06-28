import { describe, it, expect, vi } from "vitest";

vi.mock("../lib/marlin-api", () => ({
  listSerialPorts: vi.fn(() => Promise.resolve([])),
}));

import { render, screen } from "@testing-library/svelte";
import MachineWorkspace from "./MachineWorkspace.svelte";

describe("MachineWorkspace.svelte", () => {
  it("renders the connection, manual, file and log sections", () => {
    render(MachineWorkspace);
    expect(screen.getByText("Connection")).toBeInTheDocument();
    expect(screen.getByText("Manual Control")).toBeInTheDocument();
    expect(screen.getByText("File Streaming")).toBeInTheDocument();
    expect(screen.getByText("Output Log")).toBeInTheDocument();
    // the emergency stop is present and distinct
    expect(screen.getByRole("button", { name: "E-Stop" })).toBeInTheDocument();
  });
});
