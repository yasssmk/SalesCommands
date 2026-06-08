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

const DEFAULT_PROPS = {
  activeFilter: "all-active",
  onChange: vi.fn(),
  includeRejected: false,
  onToggleRejected: vi.fn(),
  signals: MOCK_SIGNALS,
};

describe("SignalsFilterBar", () => {
  it("renders 3 radio chips and 1 checkbox", () => {
    render(<SignalsFilterBar {...DEFAULT_PROPS} />);

    expect(screen.getByText("All Active (3)")).toBeInTheDocument();
    expect(screen.getByText("Pending (2)")).toBeInTheDocument();
    expect(screen.getByText("Validated (1)")).toBeInTheDocument();
    expect(screen.getByText(/Include rejected \(1\)/)).toBeInTheDocument();
  });

  it("calls onChange with filter value on chip click", () => {
    const onChange = vi.fn();
    render(<SignalsFilterBar {...DEFAULT_PROPS} onChange={onChange} />);

    fireEvent.click(screen.getByText("Pending (2)"));
    expect(onChange).toHaveBeenCalledWith("PENDING");
  });

  it("highlights active filter chip", () => {
    render(<SignalsFilterBar {...DEFAULT_PROPS} activeFilter="PENDING" />);

    const pendingChip = screen.getByText("Pending (2)").closest(".MuiChip-root");
    expect(pendingChip).toHaveClass("MuiChip-filled");
  });

  it("calls onToggleRejected when checkbox is clicked", () => {
    const onToggleRejected = vi.fn();
    render(
      <SignalsFilterBar
        {...DEFAULT_PROPS}
        onToggleRejected={onToggleRejected}
      />,
    );

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(onToggleRejected).toHaveBeenCalledWith(true);
  });

  it("shows checkbox as checked when includeRejected is true", () => {
    render(<SignalsFilterBar {...DEFAULT_PROPS} includeRejected={true} />);

    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("renders zero counts when no signals", () => {
    render(<SignalsFilterBar {...DEFAULT_PROPS} signals={[]} />);

    expect(screen.getByText("All Active (0)")).toBeInTheDocument();
    expect(screen.getByText("Pending (0)")).toBeInTheDocument();
    expect(screen.getByText(/Include rejected \(0\)/)).toBeInTheDocument();
  });

  it("does not include REJECTED in 'All Active' count", () => {
    render(<SignalsFilterBar {...DEFAULT_PROPS} />);

    expect(screen.getByText("All Active (3)")).toBeInTheDocument();
  });
});
