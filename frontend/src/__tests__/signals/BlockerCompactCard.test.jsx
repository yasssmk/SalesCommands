// frontend/src/__tests__/signals/BlockerCompactCard.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import BlockerCompactCard from "sections/activities/signals/BlockerCompactCard";

afterEach(() => {
  cleanup();
});

const MOCK_BLOCKER = {
  id: "b1",
  status: "PENDING",
  summary: "Budget frozen until Q1",
  source_quote: "We already froze the budget until January",
  contact: { id: "c1", first_name: "Pierre", last_name: "Dupont" },
};

describe("BlockerCompactCard", () => {
  it("renders summary and source quote", () => {
    render(
      <BlockerCompactCard signal={MOCK_BLOCKER} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("Budget frozen until Q1")).toBeInTheDocument();
    expect(
      screen.getByText(/We already froze the budget/),
    ).toBeInTheDocument();
  });

  it("renders contact name", () => {
    render(
      <BlockerCompactCard signal={MOCK_BLOCKER} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("Pierre Dupont")).toBeInTheDocument();
  });

  it('renders "No contact attributed" when contact is null', () => {
    const noContact = { ...MOCK_BLOCKER, contact: null };
    render(
      <BlockerCompactCard signal={noContact} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("No contact attributed")).toBeInTheDocument();
  });

  it("shows validate/reject buttons for PENDING signals", () => {
    render(
      <BlockerCompactCard
        signal={MOCK_BLOCKER}
        onSelect={vi.fn()}
        onValidate={vi.fn()}
        onReject={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /validate/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });

  it("hides validate/reject for VALIDATED blockers", () => {
    const validated = { ...MOCK_BLOCKER, status: "VALIDATED" };
    render(
      <BlockerCompactCard signal={validated} onSelect={vi.fn()} />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
  });

  it("hides validate/reject when locked", () => {
    render(
      <BlockerCompactCard signal={MOCK_BLOCKER} onSelect={vi.fn()} isLocked />,
    );

    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
  });

  it("calls onSelect with signal and type on card click", () => {
    const onSelect = vi.fn();
    render(
      <BlockerCompactCard signal={MOCK_BLOCKER} onSelect={onSelect} />,
    );

    fireEvent.click(screen.getByText("Budget frozen until Q1"));
    expect(onSelect).toHaveBeenCalledWith(MOCK_BLOCKER, "blockers");
  });

  it("calls onValidate without triggering onSelect", () => {
    const onSelect = vi.fn();
    const onValidate = vi.fn();
    render(
      <BlockerCompactCard
        signal={MOCK_BLOCKER}
        onSelect={onSelect}
        onValidate={onValidate}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(onValidate).toHaveBeenCalledWith(MOCK_BLOCKER, "blockers");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("renders with reduced opacity for REJECTED signals", () => {
    const rejected = { ...MOCK_BLOCKER, status: "REJECTED" };
    const { container } = render(
      <BlockerCompactCard signal={rejected} onSelect={vi.fn()} />,
    );

    const card = container.firstChild;
    expect(card).toHaveStyle({ opacity: 0.5 });
  });

  it("renders status chip", () => {
    render(
      <BlockerCompactCard signal={MOCK_BLOCKER} onSelect={vi.fn()} />,
    );

    expect(screen.getByText("Pending")).toBeInTheDocument();
  });
});
