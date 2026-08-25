// frontend/src/__tests__/signals/AccountSignalsTab.aggregated.test.jsx
//
// Account Signals tab after the B2-FE rewire: the flat list is fed by the
// aggregated endpoint (useAggregatedSignals) with true server pagination
// (20/page) instead of four per-type client fetches. The type toggle drives
// signal_type and the status Select drives status — both server-side.
//
// Proves:
//   - rows render straight from the aggregated hook, each typed from its own
//     signal_type (SignalLine reads _signalType),
//   - the type toggle re-scopes the aggregated call and resets to page 1,
//   - a full page renders 20 rows and the pager advances / rewinds the
//     server page arg,
//   - clicking a row opens the signal drawer,
//   - a rejected row shows Reopen and calls reopenSignal.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

vi.mock("api/signals/aggregatedSignals", () => ({ default: vi.fn() }));

vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: vi.fn(() => ({ choices: {}, choicesLoading: false })),
  validateSignal: vi.fn(() => Promise.resolve({ success: true })),
  reopenSignal: vi.fn(() => Promise.resolve({ success: true })),
  deleteSignal: vi.fn(() => Promise.resolve({ success: true })),
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import AccountSignalsTab from "sections/accounts/workspace/AccountSignalsTab";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { reopenSignal } from "api/signals/signals";
import { displayErrorSnackbar } from "utils/displayError";

const ACCOUNT_ID = "acc-1";

function aggReturn(overrides = {}) {
  return {
    signals: [
      { id: "p1", status: "PENDING", summary: "Pain one", _signalType: "pain" },
      { id: "o1", status: "VALIDATED", summary: "Objective one", _signalType: "objective" },
    ],
    count: 2,
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

describe("AccountSignalsTab — aggregated flat list", () => {
  it("renders SignalLine rows from the aggregated hook, each typed from signal_type", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);

    const rows = screen.getAllByTestId("signal-line");
    expect(rows).toHaveLength(2);
    expect(screen.getByText("Pain one")).toBeInTheDocument();
    expect(screen.getByText("Objective one")).toBeInTheDocument();
  });

  it("scopes to the account and all account types by default, pending+validated only", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    const args = lastHookArgs();
    expect(args.accountId).toBe(ACCOUNT_ID);
    // No type filter selected → all four account types.
    expect(args.signalTypes).toEqual(["pain", "objective", "impact", "tech-stack"]);
    // Rejected is excluded by default.
    expect(args.statuses).toEqual(["PENDING", "VALIDATED"]);
    expect(args.statuses).not.toContain("REJECTED");
    expect(args.pageSize).toBe(20);
  });

  it("shows the filter icon (not inline chips)", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    expect(screen.getByLabelText("Open filters")).toBeInTheDocument();
    // The old inline status chip is gone.
    expect(screen.queryByRole("button", { name: "Validated" })).not.toBeInTheDocument();
  });

  it("filters by type via the drawer and resets to page 1", () => {
    useAggregatedSignals.mockImplementation(() => aggReturn({ pageCount: 3 }));
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);

    // advance to page 2 first
    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    // open drawer, select Tech Stack, apply
    fireEvent.click(screen.getByLabelText("Open filters"));
    fireEvent.click(screen.getByLabelText("Tech Stack"));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    const args = lastHookArgs();
    expect(args.signalTypes).toEqual(["tech-stack"]);
    expect(args.page).toBe(1);
  });

  it("includes rejected only when opted in via the drawer", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    fireEvent.click(screen.getByLabelText("Open filters"));
    fireEvent.click(screen.getByLabelText("Include rejected"));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(lastHookArgs().statuses).toContain("REJECTED");
  });

  it("renders a full page of 20 rows and pages forward/back via the server arg", () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({ signals: manyRows(20), count: 55, pageCount: 3 }),
    );
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);

    expect(screen.getAllByTestId("signal-line")).toHaveLength(20);
    expect(lastHookArgs().page).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: /go to previous page/i }));
    expect(lastHookArgs().page).toBe(1);
  });

  it("opens the signal drawer when a row is clicked", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    expect(screen.queryByLabelText("Close drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByTestId("signal-line")[0]);
    expect(screen.getByLabelText("Close drawer")).toBeInTheDocument();
  });

  it("shows Reopen on a rejected row and calls reopenSignal", async () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({
        signals: [
          { id: "r1", status: "REJECTED", summary: "Rejected pain", _signalType: "pain" },
        ],
      }),
    );
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /reopen/i }));
    });
    expect(reopenSignal).toHaveBeenCalledWith("pain", "r1");
  });

  it("blanks to the red error surface only when there is nothing to show", () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({ signals: [], count: 0, error: new Error("boom") }),
    );
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    expect(screen.getByText("Failed to load signals")).toBeInTheDocument();
    expect(screen.queryAllByTestId("signal-line")).toHaveLength(0);
  });

  it("keeps the list on a transient page-fetch error and snackbars it (no blank)", () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({ error: new Error("boom") }),
    );
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    // Previous page still shown — not replaced by the red surface.
    expect(screen.queryByText("Failed to load signals")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line").length).toBeGreaterThan(0);
    // Transient failure surfaced through the standard snackbar.
    expect(displayErrorSnackbar).toHaveBeenCalled();
  });
});
