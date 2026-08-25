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
  it("exposes both a Signals (flat) and a Qualification (grouped) tab", () => {
    const ids = ACTIVITY_TABS.map((t) => t.id);
    expect(ids).toContain("signals");
    expect(ids).toContain("qualification");
  });
});

describe("ActivityQualificationTab (grouped)", () => {
  it("renders the grouped qualification + blocker sections, with no filter chips", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByText("Qualification")).toBeInTheDocument();
    expect(screen.getByText(/Blockers/)).toBeInTheDocument();
    // Grouped has no filter chips (no status filter bar).
    expect(screen.queryByText(/Filter:/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Validated \(/ })).not.toBeInTheDocument();
  });

  it("renders the theme block with signals", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByText("Data × Time")).toBeInTheDocument();
    expect(screen.getByText(/Pain signal A/)).toBeInTheDocument();
    expect(screen.getByText(/Objective signal B/)).toBeInTheDocument();
  });

  it("renders the blocker card", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByText("Budget frozen Q4")).toBeInTheDocument();
    expect(screen.getByText("Pierre Dupont")).toBeInTheDocument();
  });

  it("always excludes REJECTED signals (never shown in the grouped synthesis)", () => {
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByText(/Rejected signal C/)).not.toBeInTheDocument();
    // And there is no control to reveal them.
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("calls validateSignal and mutates on validate", async () => {
    const mutateCounts = vi.fn();
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} mutateCounts={mutateCounts} />);
    const validateButtons = screen.getAllByRole("button", { name: /validate signal|validate blocker/i });
    await act(async () => {
      fireEvent.click(validateButtons[0]);
    });
    expect(validateSignal).toHaveBeenCalled();
    expect(mockMutateAll).toHaveBeenCalled();
    expect(mutateCounts).toHaveBeenCalled();
  });

  it("calls rejectSignal and mutates on reject", async () => {
    const mutateCounts = vi.fn();
    render(<ActivityQualificationTab activity={MOCK_ACTIVITY} mutateCounts={mutateCounts} />);
    const rejectButtons = screen.getAllByRole("button", { name: /reject signal|reject blocker/i });
    await act(async () => {
      fireEvent.click(rejectButtons[0]);
    });
    expect(rejectSignal).toHaveBeenCalled();
    expect(mockMutateAll).toHaveBeenCalled();
    expect(mutateCounts).toHaveBeenCalled();
  });
});
