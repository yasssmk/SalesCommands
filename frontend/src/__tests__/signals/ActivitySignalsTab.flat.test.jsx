// frontend/src/__tests__/signals/ActivitySignalsTab.flat.test.jsx
//
// The Activity "Signals" tab is now flat-only (the grouped synthesis moved to
// ActivityQualificationTab). It is fed by the aggregated endpoint via
// useAggregatedSignals (one server-paginated mixed list) scoped by activity_id.
//
// Proves:
//   - renders SignalLine rows straight from the aggregated hook, each typed
//     from its own signal_type,
//   - drives the aggregated hook's status filter server-side (statuses arg),
//   - opens the signal drawer on row click,
//   - shows Reopen on a rejected row and calls reopenSignal,
//   - advances / rewinds the server page (page arg) via the pager.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/aggregatedSignals", () => ({ default: vi.fn() }));

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

import ActivitySignalsTab from "sections/activities/workspace/ActivitySignalsTab";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { reopenSignal } from "api/signals/signals";
import { displayErrorSnackbar } from "utils/displayError";

const MOCK_ACTIVITY = { id: "act-flat", account: "acc-1" };

function flatReturn(overrides = {}) {
  return {
    signals: [
      { id: "p1", status: "PENDING", summary: "Pain signal flat", _signalType: "pain" },
      { id: "o1", status: "VALIDATED", summary: "Objective signal flat", _signalType: "objective" },
      { id: "b1", status: "PENDING", summary: "Budget frozen flat", _signalType: "blockers" },
    ],
    count: 3,
    next: null,
    previous: null,
    pageCount: 1,
    loading: false,
    validating: false,
    error: null,
    mutate: vi.fn(),
    ...overrides,
  };
}

function lastHookArgs() {
  return useAggregatedSignals.mock.calls.at(-1)[0];
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  useAggregatedSignals.mockImplementation(() => flatReturn());
});

afterEach(() => cleanup());

describe("ActivitySignalsTab — Flat view (aggregated endpoint)", () => {
  it("renders SignalLine rows from the aggregated hook, mixed types", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(screen.getAllByTestId("signal-line")).toHaveLength(3);
    expect(screen.getByText("Pain signal flat")).toBeInTheDocument();
    expect(screen.getByText("Objective signal flat")).toBeInTheDocument();
    expect(screen.getByText("Budget frozen flat")).toBeInTheDocument();
  });

  it("scopes the aggregated call to this activity and the qualification+blocker types", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    const args = lastHookArgs();
    expect(args.activityId).toBe("act-flat");
    // No type filter selected → all activity flat types.
    expect(args.signalTypes).toEqual([
      "pain",
      "objective",
      "impact",
      "tech-stack",
      "blockers",
    ]);
    // Rejected excluded by default.
    expect(args.statuses).toEqual(["PENDING", "VALIDATED"]);
    expect(args.pageSize).toBe(20);
  });

  it("shows the filter icon (not inline chips)", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByLabelText("Open filters")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Validated" })).not.toBeInTheDocument();
  });

  it("filters by type via the drawer", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(screen.getByLabelText("Open filters"));
    fireEvent.click(screen.getByLabelText("Objective"));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(lastHookArgs().signalTypes).toEqual(["objective"]);
  });

  it("adds REJECTED to the statuses arg only when opted in via the drawer", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(screen.getByLabelText("Open filters"));
    fireEvent.click(screen.getByLabelText("Include rejected"));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(lastHookArgs().statuses).toContain("REJECTED");
  });

  it("opens the signal drawer when a row is clicked", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(screen.queryByLabelText("Close drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByTestId("signal-line")[0]);
    expect(screen.getByLabelText("Close drawer")).toBeInTheDocument();
  });

  it("shows Reopen on a rejected row and calls reopenSignal", async () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          { id: "r1", status: "REJECTED", summary: "Rejected flat", _signalType: "pain" },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    const reopenBtn = screen.getByRole("button", { name: /reopen/i });
    await act(async () => {
      fireEvent.click(reopenBtn);
    });
    expect(reopenSignal).toHaveBeenCalledWith("pain", "r1");
  });

  it("advances and rewinds the server page via the pager", () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ pageCount: 3 }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(lastHookArgs().page).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: /go to previous page/i }));
    expect(lastHookArgs().page).toBe(1);
  });

  it("shows the sort select", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
  });

  it("blanks to the red error surface only when the flat list is empty", () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({ signals: [], count: 0, error: new Error("boom") }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByText("Failed to load signals")).toBeInTheDocument();
    expect(screen.queryAllByTestId("signal-line")).toHaveLength(0);
  });

  it("keeps the flat list on a transient page-fetch error and snackbars it", () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({ error: new Error("boom") }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByText("Failed to load signals")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line").length).toBeGreaterThan(0);
    expect(displayErrorSnackbar).toHaveBeenCalled();
  });
});
