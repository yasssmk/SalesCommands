// frontend/src/__tests__/signals/SignalsFlatView.test.jsx

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import SignalsFlatView from "components/signals/SignalsFlatView";

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
    source_context: { contacts: [{ id: "c1", first_name: "Pierre", last_name: "Dupont" }] },
  },
];

// Read the ordered message text of the rendered SignalLine rows.
function rowMessages() {
  return screen
    .getAllByTestId("signal-line")
    .map((row) => within(row).getByText(/signal|Budget/i).textContent);
}

describe("SignalsFlatView", () => {
  it("renders all signals as SignalLine rows (not the old cards)", () => {
    render(<SignalsFlatView signals={SIGNALS} sortKey="date-desc" />);
    expect(screen.getAllByTestId("signal-line")).toHaveLength(3);
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

  it("uses a custom empty message when provided", () => {
    render(<SignalsFlatView signals={[]} sortKey="date-desc" emptyMessage="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("sorts by date descending (newest first)", () => {
    render(<SignalsFlatView signals={SIGNALS} sortKey="date-desc" />);
    const texts = rowMessages();
    expect(texts[0]).toBe("Objective signal beta");
    expect(texts[1]).toBe("Pain signal alpha");
    expect(texts[2]).toBe("Budget frozen Q4");
  });

  it("sorts by date ascending (oldest first)", () => {
    render(<SignalsFlatView signals={SIGNALS} sortKey="date-asc" />);
    const texts = rowMessages();
    expect(texts[0]).toBe("Budget frozen Q4");
    expect(texts[1]).toBe("Pain signal alpha");
    expect(texts[2]).toBe("Objective signal beta");
  });

  it("sorts by type using TYPE_ORDER", () => {
    render(<SignalsFlatView signals={SIGNALS} sortKey="type" />);
    const texts = rowMessages();
    expect(texts[0]).toBe("Pain signal alpha");
    expect(texts[1]).toBe("Objective signal beta");
    expect(texts[2]).toBe("Budget frozen Q4");
  });

  it("opens the drawer (onSelect) when a row is clicked", () => {
    const onSelect = vi.fn();
    render(<SignalsFlatView signals={SIGNALS} sortKey="type" onSelect={onSelect} />);
    fireEvent.click(screen.getAllByTestId("signal-line")[0]);
    expect(onSelect).toHaveBeenCalledWith(
      expect.objectContaining({ id: "p1" }),
      "pain",
    );
  });

  it("renders no lifecycle action buttons on any row (actions live in the drawer)", () => {
    const rejected = [{ ...SIGNALS[0], id: "r1", status: "REJECTED", summary: "Rejected pain" }];
    render(<SignalsFlatView signals={rejected} sortKey="date-desc" onReopen={vi.fn()} />);
    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
  });

  it("paginates at 20 per page — only 20 render, next page advances", () => {
    const many = Array.from({ length: 25 }, (_, i) => ({
      id: `s${i}`,
      status: "PENDING",
      summary: `Signal number ${i}`,
      _signalType: "pain",
      created_at: `2025-06-${String((i % 27) + 1).padStart(2, "0")}T10:00:00Z`,
    }));
    render(<SignalsFlatView signals={many} sortKey="type" />);
    // page 1 shows exactly 20 rows
    expect(screen.getAllByTestId("signal-line")).toHaveLength(20);
    // advance to page 2 → the remaining 5
    fireEvent.click(screen.getByRole("button", { name: /go to page 2/i }));
    expect(screen.getAllByTestId("signal-line")).toHaveLength(5);
  });
});
