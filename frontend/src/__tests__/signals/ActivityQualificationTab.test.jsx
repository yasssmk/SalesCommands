// frontend/src/__tests__/signals/ActivityQualificationTab.test.jsx
//
// The Activity grouped synthesis, now its own "Qualification" tab (split out
// of ActivitySignalsTab). Renders the theme-grouped qualification column plus
// blockers, with client-side status filtering and CRUD.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

const mockMutateAll = vi.fn();

vi.mock("hooks/useActivityAllSignals", () => ({
  default: vi.fn(() => ({
    qualificationSignals: [
      { id: "p1", status: "PENDING", summary: "Pain signal A", what: "DATA", what_display: "Data", dimension: "TIME", dimension_display: "Time", _signalType: "pain" },
      { id: "o1", status: "VALIDATED", summary: "Objective signal B", what: "DATA", what_display: "Data", dimension: "TIME", dimension_display: "Time", _signalType: "objective" },
      { id: "r1", status: "REJECTED", summary: "Rejected signal C", what: "DATA", what_display: "Data", dimension: "TIME", dimension_display: "Time", _signalType: "pain" },
    ],
    techStackSignals: [],
    blockerSignals: [
      { id: "b1", status: "PENDING", summary: "Budget frozen Q4", source_quote: "Budget blocked", contact: { id: "c1", first_name: "Pierre", last_name: "Dupont" }, _signalType: "blockers" },
    ],
    nextStepSignals: [],
    allSignals: [],
    loading: false,
    error: null,
    mutateAll: mockMutateAll,
  })),
}));

vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: vi.fn(() => ({ choices: {}, choicesLoading: false })),
  validateSignal: vi.fn(() => Promise.resolve({ success: true })),
  rejectSignal: vi.fn(() => Promise.resolve({ success: true })),
  reopenSignal: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivityQualificationTab from "sections/activities/workspace/ActivityQualificationTab";
import { validateSignal, rejectSignal } from "api/signals/signals";
import { ACTIVITY_TABS } from "sections/activities/workspace/ActivityTabs";

const MOCK_ACTIVITY = { id: "act-1", account: "acc-1" };

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

afterEach(() => cleanup());

describe("Activity workspace tabs", () => {
  it("exposes ONE Signals tab and no separate Qualification tab (C6)", () => {
    const ids = ACTIVITY_TABS.map((t) => t.id);
    expect(ids).toContain("signals");
    // The Qualification tab is gone — its view is the Grouped toggle inside Signals.
    expect(ids).not.toContain("qualification");
  });
});

describe("ActivityQualificationTab (grouped by type, flat lists)", () => {
  it("renders type sections (Objectives/Pains/Impacts/Objections), no filter chips", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByText("Objectives")).toBeInTheDocument();
    expect(screen.getByText("Pains")).toBeInTheDocument();
    expect(screen.getByText("Impacts")).toBeInTheDocument();
    expect(screen.getByText("Objections")).toBeInTheDocument();
    // No status filter chips on the grouped synthesis.
    expect(screen.queryByText(/Filter:/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Validated \(/ })).not.toBeInTheDocument();
  });

  it("renders signals as flat rows under their type — NO domain×dimension accordion", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByText(/Pain signal A/)).toBeInTheDocument();
    expect(screen.getByText(/Objective signal B/)).toBeInTheDocument();
    // The old theme grouping header is gone.
    expect(screen.queryByText("Data × Time")).not.toBeInTheDocument();
  });

  it("renders the blocker under the Objections section as a flat row", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByText("Budget frozen Q4")).toBeInTheDocument();
  });

  it("always excludes REJECTED signals (never shown in the grouped synthesis)", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByText(/Rejected signal C/)).not.toBeInTheDocument();
    // And there is no control to reveal them.
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("rows carry no action buttons (actions moved to the drawer)", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByRole("button", { name: /validate/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
  });

  it("validates from the drawer: click a row → Validate", async () => {
    const mutateCounts = vi.fn();
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} mutateCounts={mutateCounts} />);
    // Open the pending pain's drawer, then validate there.
    fireEvent.click(screen.getByText("Pain signal A"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    });
    expect(validateSignal).toHaveBeenCalled();
    expect(mockMutateAll).toHaveBeenCalled();
    expect(mutateCounts).toHaveBeenCalled();
  });

  it("rejects from the drawer: click a row → Reject", async () => {
    const mutateCounts = vi.fn();
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} mutateCounts={mutateCounts} />);
    fireEvent.click(screen.getByText("Pain signal A"));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    });
    expect(rejectSignal).toHaveBeenCalled();
    expect(mockMutateAll).toHaveBeenCalled();
    expect(mutateCounts).toHaveBeenCalled();
  });
});
