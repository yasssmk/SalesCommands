// frontend/src/__tests__/signals/SignalsFlatView.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import SignalsFlatView from "sections/activities/signals/SignalsFlatView";

afterEach(() => {
  cleanup();
});

const SIGNALS = [
  {
    id: "p1",
    status: "PENDING",
    summary: "Pain signal alpha",
    _signalType: "pain",
    created_at: "2025-06-01T10:00:00Z",
    what_display: "Data",
    dimension_display: "Time",
  },
  {
    id: "o1",
    status: "VALIDATED",
    summary: "Objective signal beta",
    _signalType: "objective",
    created_at: "2025-06-02T10:00:00Z",
    what_display: "Data",
    dimension_display: "Quality",
  },
  {
    id: "b1",
    status: "PENDING",
    summary: "Budget frozen Q4",
    _signalType: "blockers",
    created_at: "2025-05-30T10:00:00Z",
    contact: { id: "c1", first_name: "Pierre", last_name: "Dupont" },
  },
];

describe("SignalsFlatView", () => {
  it("renders all signal cards", () => {
    render(<SignalsFlatView signals={SIGNALS} sortKey="date-desc" />);

    expect(screen.getByText("Pain signal alpha")).toBeInTheDocument();
    expect(screen.getByText("Objective signal beta")).toBeInTheDocument();
    expect(screen.getByText("Budget frozen Q4")).toBeInTheDocument();
  });

  it("renders empty state when no signals", () => {
    render(<SignalsFlatView signals={[]} sortKey="date-desc" />);

    expect(
      screen.getByText("No signals found for this activity"),
    ).toBeInTheDocument();
  });

  it("sorts by date descending (newest first)", () => {
    const { container } = render(
      <SignalsFlatView signals={SIGNALS} sortKey="date-desc" />,
    );

    const summaries = container.querySelectorAll("h6");
    const texts = Array.from(summaries).map((el) => el.textContent);
    expect(texts[0]).toBe("Objective signal beta");
    expect(texts[1]).toBe("Pain signal alpha");
    expect(texts[2]).toBe("Budget frozen Q4");
  });

  it("sorts by date ascending (oldest first)", () => {
    const { container } = render(
      <SignalsFlatView signals={SIGNALS} sortKey="date-asc" />,
    );

    const summaries = container.querySelectorAll("h6");
    const texts = Array.from(summaries).map((el) => el.textContent);
    expect(texts[0]).toBe("Budget frozen Q4");
    expect(texts[1]).toBe("Pain signal alpha");
    expect(texts[2]).toBe("Objective signal beta");
  });

  it("sorts by type using TYPE_ORDER", () => {
    const { container } = render(
      <SignalsFlatView signals={SIGNALS} sortKey="type" />,
    );

    const summaries = container.querySelectorAll("h6");
    const texts = Array.from(summaries).map((el) => el.textContent);
    // pain (0) < objective (1) < blockers (4)
    expect(texts[0]).toBe("Pain signal alpha");
    expect(texts[1]).toBe("Objective signal beta");
    expect(texts[2]).toBe("Budget frozen Q4");
  });

  it("sorts by status (PENDING first, VALIDATED second)", () => {
    const { container } = render(
      <SignalsFlatView signals={SIGNALS} sortKey="status" />,
    );

    const summaries = container.querySelectorAll("h6");
    const texts = Array.from(summaries).map((el) => el.textContent);
    // PENDING (0) before VALIDATED (1)
    expect(texts[0]).not.toBe("Objective signal beta");
    expect(texts[2]).toBe("Objective signal beta");
  });

  it("passes onEdit callback to cards", () => {
    const onEdit = vi.fn();
    render(
      <SignalsFlatView signals={SIGNALS} sortKey="date-desc" onEdit={onEdit} />,
    );

    const editButtons = screen.getAllByRole("button", { name: /edit/i });
    expect(editButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("passes isLocked to cards — hides action buttons", () => {
    render(
      <SignalsFlatView signals={SIGNALS} sortKey="date-desc" isLocked />,
    );

    expect(
      screen.queryByRole("button", { name: /edit/i }),
    ).not.toBeInTheDocument();
  });
});
