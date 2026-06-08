// frontend/src/__tests__/signals/SignalsFilterBar.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import SignalsFilterBar from "sections/activities/signals/SignalsFilterBar";

afterEach(() => {
  cleanup();
});

const MOCK_SIGNALS = [
  { id: "1", status: "PENDING" },
  { id: "2", status: "PENDING" },
  { id: "3", status: "VALIDATED" },
  { id: "4", status: "REJECTED" },
];

describe("SignalsFilterBar", () => {
  it("renders all filter chips with counts", () => {
    render(
      <SignalsFilterBar
        activeFilter="all"
        onChange={vi.fn()}
        signals={MOCK_SIGNALS}
      />,
    );

    expect(screen.getByText("All (4)")).toBeInTheDocument();
    expect(screen.getByText("Pending (2)")).toBeInTheDocument();
    expect(screen.getByText("Validated (1)")).toBeInTheDocument();
    expect(screen.getByText("Rejected (1)")).toBeInTheDocument();
  });

  it("calls onChange with filter value on chip click", () => {
    const onChange = vi.fn();
    render(
      <SignalsFilterBar
        activeFilter="all"
        onChange={onChange}
        signals={MOCK_SIGNALS}
      />,
    );

    fireEvent.click(screen.getByText("Pending (2)"));
    expect(onChange).toHaveBeenCalledWith("PENDING");
  });

  it("highlights active filter chip", () => {
    render(
      <SignalsFilterBar
        activeFilter="PENDING"
        onChange={vi.fn()}
        signals={MOCK_SIGNALS}
      />,
    );

    const pendingChip = screen.getByText("Pending (2)").closest(".MuiChip-root");
    expect(pendingChip).toHaveClass("MuiChip-filled");
  });

  it("renders zero counts when no signals", () => {
    render(
      <SignalsFilterBar activeFilter="all" onChange={vi.fn()} signals={[]} />,
    );

    expect(screen.getByText("All (0)")).toBeInTheDocument();
    expect(screen.getByText("Pending (0)")).toBeInTheDocument();
  });
});
