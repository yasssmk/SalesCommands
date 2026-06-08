// frontend/src/__tests__/signals/ActivitySignalsTab.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

const mockMutateAll = vi.fn();

vi.mock("hooks/useActivityAllSignals", () => ({
  default: vi.fn(() => ({
    qualificationSignals: [
      {
        id: "p1",
        status: "PENDING",
        summary: "Pain signal A",
        what: "DATA",
        what_display: "Data",
        dimension: "TIME",
        dimension_display: "Time",
        _signalType: "pain",
      },
      {
        id: "o1",
        status: "VALIDATED",
        summary: "Objective signal B",
        what: "DATA",
        what_display: "Data",
        dimension: "TIME",
        dimension_display: "Time",
        _signalType: "objective",
      },
    ],
    blockerSignals: [
      {
        id: "b1",
        status: "PENDING",
        summary: "Budget frozen Q4",
        source_quote: "Budget blocked",
        contact: { id: "c1", first_name: "Pierre", last_name: "Dupont" },
        _signalType: "blockers",
      },
    ],
    nextStepSignals: [],
    allSignals: [],
    loading: false,
    error: null,
    mutateAll: mockMutateAll,
  })),
}));

vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: vi.fn(() => ({
    choices: {},
    choicesLoading: false,
  })),
  validateSignal: vi.fn(() => Promise.resolve({ success: true })),
  rejectSignal: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivitySignalsTab from "sections/activities/workspace/ActivitySignalsTab";
import { validateSignal, rejectSignal } from "api/signals/signals";

// ==============================|| TESTS ||============================== //

const MOCK_ACTIVITY = {
  id: "act-1",
  account: "acc-1",
};

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
});

describe("ActivitySignalsTab", () => {
  it("renders filter bar and view toggle", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(screen.getByText(/Filter:/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /grouped/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /flat/i })).toBeInTheDocument();
  });

  it("renders Grouped view by default with qualification and blocker sections", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(screen.getByText("Qualification")).toBeInTheDocument();
    expect(screen.getByText(/Blockers/)).toBeInTheDocument();
  });

  it("renders theme block with signals", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(screen.getByText("Data × Time")).toBeInTheDocument();
    expect(screen.getByText(/Pain signal A/)).toBeInTheDocument();
    expect(screen.getByText(/Objective signal B/)).toBeInTheDocument();
  });

  it("renders blocker card", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(screen.getByText("Budget frozen Q4")).toBeInTheDocument();
    expect(screen.getByText("Pierre Dupont")).toBeInTheDocument();
  });

  it("shows Flat view with signal cards when toggling to Flat", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    fireEvent.click(screen.getByRole("button", { name: /flat/i }));
    expect(screen.getByText(/Pain signal A/)).toBeInTheDocument();
    expect(screen.getByText(/Budget frozen Q4/)).toBeInTheDocument();
  });

  it("filters signals by status", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    // Click Validated filter chip (matches "Validated (1)")
    fireEvent.click(screen.getByText(/Validated \(/));

    // Only validated signal should be visible
    expect(screen.getByText(/Objective signal B/)).toBeInTheDocument();
    // Pending signals should be hidden
    expect(screen.queryByText(/Pain signal A/)).not.toBeInTheDocument();
  });

  it("calls validateSignal and mutates on validate action", async () => {
    const mutateCounts = vi.fn();
    render(
      <ActivitySignalsTab
        activity={MOCK_ACTIVITY}
        mutateCounts={mutateCounts}
      />,
    );

    // Click validate on first available signal (pain signal in theme block)
    const validateButtons = screen.getAllByRole("button", { name: /validate signal|validate blocker/i });
    await act(async () => {
      fireEvent.click(validateButtons[0]);
    });

    expect(validateSignal).toHaveBeenCalled();
    expect(mockMutateAll).toHaveBeenCalled();
    expect(mutateCounts).toHaveBeenCalled();
  });

  it("calls rejectSignal and mutates on reject action", async () => {
    const mutateCounts = vi.fn();
    render(
      <ActivitySignalsTab
        activity={MOCK_ACTIVITY}
        mutateCounts={mutateCounts}
      />,
    );

    const rejectButtons = screen.getAllByRole("button", { name: /reject signal|reject blocker/i });
    await act(async () => {
      fireEvent.click(rejectButtons[0]);
    });

    expect(rejectSignal).toHaveBeenCalled();
    expect(mockMutateAll).toHaveBeenCalled();
    expect(mutateCounts).toHaveBeenCalled();
  });
});
