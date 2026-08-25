// frontend/src/__tests__/signals/DCSignalsTab.aggregated.test.jsx
//
// Decision-cycle Signals tab (flat) after the B2-FE rewire: fed by the
// aggregated endpoint (useAggregatedSignals) scoped by decision_cycle_id,
// with server-driven status filter, type filter, sort and 20/page pagination.
//
// Proves:
//   - rows render straight from the aggregated hook, mixed types, each typed
//     from its own signal_type,
//   - the cycle scope + default status set (PENDING+VALIDATED) reach the hook,
//   - the status filter and type filter drive the hook server-side and reset
//     to page 1,
//   - a full page renders 20 rows and the pager advances / rewinds the page arg,
//   - clicking a row opens the signal drawer,
//   - a rejected row shows Reopen and calls reopenSignal.

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

import SignalsTab from "sections/accounts/dc-workspace/SignalsTab";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { reopenSignal } from "api/signals/signals";
import { displayErrorSnackbar } from "utils/displayError";

const CYCLE_ID = "cycle-1";
const ACCOUNT_ID = "acc-1";

function aggReturn(overrides = {}) {
  return {
    signals: [
      { id: "p1", status: "PENDING", summary: "Pain DC", _signalType: "pain" },
      { id: "t1", status: "PENDING", summary: "Tool DC", tech_name: "Snowflake", _signalType: "tech-stack" },
      { id: "b1", status: "PENDING", summary: "Blocker DC", _signalType: "blockers" },
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

function manyRows(n) {
  return Array.from({ length: n }, (_, i) => ({
    id: `s${i}`,
    status: "PENDING",
    summary: `Signal ${i}`,
    _signalType: "pain",
  }));
}

function lastHookArgs() {
  return useAggregatedSignals.mock.calls.at(-1)[0];
}

beforeEach(() => {
  vi.clearAllMocks();
  useAggregatedSignals.mockImplementation(() => aggReturn());
});

afterEach(() => cleanup());

describe("DC SignalsTab — aggregated flat list", () => {
  it("renders SignalLine rows from the aggregated hook, mixed types", () => {
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);

    expect(screen.getAllByTestId("signal-line")).toHaveLength(3);
    expect(screen.getByText("Pain DC")).toBeInTheDocument();
    expect(screen.getByText("Blocker DC")).toBeInTheDocument();
  });

  it("scopes the call to the decision cycle with the default active status set", () => {
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);
    const args = lastHookArgs();
    expect(args.decisionCycleId).toBe(CYCLE_ID);
    expect(args.statuses).toEqual(["PENDING", "VALIDATED"]);
    expect(args.signalTypes).toBeUndefined(); // "all" types
    expect(args.pageSize).toBe(20);
  });

  it("drives the status filter server-side and resets to page 1", () => {
    useAggregatedSignals.mockImplementation(() => aggReturn({ pageCount: 3 }));
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);

    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: "Validated" }));
    const args = lastHookArgs();
    expect(args.statuses).toEqual(["VALIDATED"]);
    expect(args.page).toBe(1);
  });

  it("drives the type filter server-side and resets to page 1", () => {
    useAggregatedSignals.mockImplementation(() => aggReturn({ pageCount: 3 }));
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);

    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: "Pain" }));
    const args = lastHookArgs();
    expect(args.signalTypes).toEqual(["pain"]);
    expect(args.page).toBe(1);
  });

  it("renders a full page of 20 rows and pages forward/back via the server arg", () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({ signals: manyRows(20), count: 55, pageCount: 3 }),
    );
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);

    expect(screen.getAllByTestId("signal-line")).toHaveLength(20);
    expect(lastHookArgs().page).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: /go to previous page/i }));
    expect(lastHookArgs().page).toBe(1);
  });

  it("opens the signal drawer when a row is clicked", () => {
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);
    expect(screen.queryByLabelText("Close drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByTestId("signal-line")[0]);
    expect(screen.getByLabelText("Close drawer")).toBeInTheDocument();
  });

  it("shows Reopen on a rejected row and calls reopenSignal", async () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({
        signals: [
          { id: "r1", status: "REJECTED", summary: "Rejected DC", _signalType: "pain" },
        ],
      }),
    );
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /reopen/i }));
    });
    expect(reopenSignal).toHaveBeenCalledWith("pain", "r1");
  });

  it("blanks to the red error surface only when there is nothing to show", () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({ signals: [], count: 0, error: new Error("boom") }),
    );
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);
    expect(screen.getByText("Failed to load signals")).toBeInTheDocument();
    expect(screen.queryAllByTestId("signal-line")).toHaveLength(0);
  });

  it("keeps the list on a transient page-fetch error and snackbars it (no blank)", () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({ error: new Error("boom") }),
    );
    render(<SignalsTab cycleId={CYCLE_ID} accountId={ACCOUNT_ID} />);
    expect(screen.queryByText("Failed to load signals")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line").length).toBeGreaterThan(0);
    expect(displayErrorSnackbar).toHaveBeenCalled();
  });
});
