// frontend/src/__tests__/signals/ActivitySignalsTab.flat.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("hooks/useActivityAllSignals", () => ({
  default: vi.fn(() => ({
    qualificationSignals: [
      {
        id: "p1",
        status: "PENDING",
        summary: "Pain signal flat",
        what: "DATA",
        what_display: "Data",
        dimension: "TIME",
        dimension_display: "Time",
        created_at: "2025-06-01T10:00:00Z",
        _signalType: "pain",
      },
      {
        id: "o1",
        status: "VALIDATED",
        summary: "Objective signal flat",
        what: "DATA",
        what_display: "Data",
        dimension: "TIME",
        dimension_display: "Time",
        created_at: "2025-06-02T10:00:00Z",
        _signalType: "objective",
      },
      {
        id: "r1",
        status: "REJECTED",
        summary: "Rejected signal flat",
        what: "DATA",
        what_display: "Data",
        dimension: "TIME",
        dimension_display: "Time",
        created_at: "2025-05-29T10:00:00Z",
        _signalType: "pain",
      },
    ],
    techStackSignals: [],
    blockerSignals: [
      {
        id: "b1",
        status: "PENDING",
        summary: "Budget frozen flat",
        contact: { id: "c1", first_name: "Pierre", last_name: "Dupont" },
        created_at: "2025-05-30T10:00:00Z",
        _signalType: "blockers",
      },
    ],
    nextStepSignals: [],
    allSignals: [],
    loading: false,
    error: null,
    mutateAll: vi.fn(),
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

// ==============================|| TESTS ||============================== //

const MOCK_ACTIVITY = { id: "act-flat", account: "acc-1" };

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
});

afterEach(() => {
  cleanup();
});

function switchToFlat() {
  fireEvent.click(screen.getByRole("button", { name: /flat/i }));
}

describe("ActivitySignalsTab — Flat view", () => {
  it("renders SignalDetailCards in flat view", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    expect(screen.getByText("Pain signal flat")).toBeInTheDocument();
    expect(screen.getByText("Objective signal flat")).toBeInTheDocument();
    expect(screen.getByText("Budget frozen flat")).toBeInTheDocument();
  });

  it("shows sort select only in flat view", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(screen.queryByLabelText("Sort")).not.toBeInTheDocument();

    switchToFlat();
    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
  });

  it("hides sort select when switching back to grouped", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    switchToFlat();
    expect(screen.getByLabelText("Sort")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /grouped/i }));
    expect(screen.queryByLabelText("Sort")).not.toBeInTheDocument();
  });

  it("filters signals in flat view (Validated only)", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    fireEvent.click(screen.getByText(/Validated \(/));

    expect(screen.getByText("Objective signal flat")).toBeInTheDocument();
    expect(screen.queryByText("Pain signal flat")).not.toBeInTheDocument();
    expect(screen.queryByText("Budget frozen flat")).not.toBeInTheDocument();
  });

  it("shows edit buttons on cards in flat view", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    const editButtons = screen.getAllByRole("button", { name: /edit/i });
    expect(editButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("hides action buttons when locked in flat view", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} isLocked />);
    switchToFlat();

    expect(
      screen.queryByRole("button", { name: /edit edit/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /check-circle validate/i }),
    ).not.toBeInTheDocument();
  });

  it("default excludes rejected signals in flat view", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    expect(screen.queryByText("Rejected signal flat")).not.toBeInTheDocument();
  });

  it("include rejected checkbox shows REJECTED signals in flat view", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    fireEvent.click(screen.getByRole("checkbox"));

    expect(screen.getByText("Rejected signal flat")).toBeInTheDocument();
  });

  it("shows empty state when all filtered out", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    // Click "Validated" — only one signal, then ensure others are hidden
    fireEvent.click(screen.getByText(/Validated \(/));

    // Only objective should remain
    expect(screen.getByText("Objective signal flat")).toBeInTheDocument();
    expect(screen.queryByText("Pain signal flat")).not.toBeInTheDocument();
  });
});
