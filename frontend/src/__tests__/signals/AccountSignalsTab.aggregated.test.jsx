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

// Controlled department list for the drawer; useGetContacts feeds the
// AsyncContactSelect (empty options are fine for these tests).
vi.mock("sections/accounts/signals/QualificationGroupedView", () => ({
  default: () => <div data-testid="grouped-view" />,
}));

vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: vi.fn(() => ({
    standardDepartments: [
      { value: 7, label: "Marketing" },
      { value: 9, label: "Engineering" },
    ],
  })),
  useGetContacts: vi.fn(() => ({ contacts: [], contactsLoading: false })),
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

// Grouped is the default view; switch to Flat for the flat-list assertions.
function toFlat() {
  fireEvent.click(screen.getByRole("button", { name: /flat view/i }));
}

beforeEach(() => {
  vi.clearAllMocks();
  useAggregatedSignals.mockImplementation(() => aggReturn());
});

afterEach(() => cleanup());

describe("AccountSignalsTab — aggregated flat list", () => {
  it("renders SignalLine rows from the aggregated hook, each typed from signal_type", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();

    const rows = screen.getAllByTestId("signal-line");
    expect(rows).toHaveLength(2);
    expect(screen.getByText("Pain one")).toBeInTheDocument();
    expect(screen.getByText("Objective one")).toBeInTheDocument();
  });

  it("scopes to the account and all account types by default, pending+validated only", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();
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
    toFlat();
    expect(screen.getByLabelText("Open filters")).toBeInTheDocument();
    // The old inline status chip is gone.
    expect(screen.queryByRole("button", { name: "Validated" })).not.toBeInTheDocument();
  });

  it("filters by type via the drawer and resets to page 1", () => {
    useAggregatedSignals.mockImplementation(() => aggReturn({ pageCount: 3 }));
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();

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

  it("filters by department via the drawer (passes the StandardDepartment id) and resets to page 1", () => {
    useAggregatedSignals.mockImplementation(() => aggReturn({ pageCount: 3 }));
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();

    // No department by default.
    expect(lastHookArgs().department).toBeUndefined();

    // advance to page 2 first
    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    // open drawer, pick Marketing from the Department select, apply
    fireEvent.click(screen.getByLabelText("Open filters"));
    fireEvent.mouseDown(screen.getByLabelText("Department"));
    fireEvent.click(screen.getByRole("option", { name: "Marketing" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    const args = lastHookArgs();
    expect(args.department).toBe(7);
    expect(args.page).toBe(1);
  });

  it("filters by scope via the drawer (BUSINESS | DEPARTMENT)", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();
    expect(lastHookArgs().scope).toBeUndefined();

    fireEvent.click(screen.getByLabelText("Open filters"));
    fireEvent.mouseDown(screen.getByLabelText("Scope"));
    fireEvent.click(screen.getByRole("option", { name: "Department" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(lastHookArgs().scope).toBe("DEPARTMENT");
  });

  it("combines type + status + department into one aggregated call", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();
    fireEvent.click(screen.getByLabelText("Open filters"));
    fireEvent.click(screen.getByLabelText("Tech Stack"));
    fireEvent.click(screen.getByLabelText("Include rejected"));
    fireEvent.mouseDown(screen.getByLabelText("Department"));
    fireEvent.click(screen.getByRole("option", { name: "Engineering" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    const args = lastHookArgs();
    expect(args.signalTypes).toEqual(["tech-stack"]);
    expect(args.statuses).toContain("REJECTED");
    expect(args.department).toBe(9);
  });

  it("includes rejected only when opted in via the drawer", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();
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
    toFlat();

    expect(screen.getAllByTestId("signal-line")).toHaveLength(20);
    expect(lastHookArgs().page).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: /go to previous page/i }));
    expect(lastHookArgs().page).toBe(1);
  });

  it("opens the signal drawer when a row is clicked", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();
    expect(screen.queryByLabelText("Close drawer")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByTestId("signal-line")[0]);
    expect(screen.getByLabelText("Close drawer")).toBeInTheDocument();
  });

  it("opens the drawer on a rejected row and reopens from there", async () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({
        signals: [
          { id: "r1", status: "REJECTED", summary: "Rejected pain", _signalType: "pain" },
        ],
      }),
    );
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();

    // Row carries no action button — click it to open the drawer.
    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("signal-line"));

    // Reopen lives in the drawer.
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
    toFlat();
    expect(screen.getByText("Failed to load signals")).toBeInTheDocument();
    expect(screen.queryAllByTestId("signal-line")).toHaveLength(0);
  });

  it("keeps the list on a transient page-fetch error and snackbars it (no blank)", () => {
    useAggregatedSignals.mockImplementation(() =>
      aggReturn({ error: new Error("boom") }),
    );
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    toFlat();
    // Previous page still shown — not replaced by the red surface.
    expect(screen.queryByText("Failed to load signals")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line").length).toBeGreaterThan(0);
    // Transient failure surfaced through the standard snackbar.
    expect(displayErrorSnackbar).toHaveBeenCalled();
  });
});

describe("AccountSignalsTab — Flat/Grouped toggle", () => {
  it("defaults to Grouped (the qualification synthesis)", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    expect(screen.getByTestId("grouped-view")).toBeInTheDocument();
    expect(screen.queryAllByTestId("signal-line")).toHaveLength(0);
  });

  it("switching to Flat shows the SignalLine list; back to Grouped shows the synthesis", () => {
    render(<AccountSignalsTab accountId={ACCOUNT_ID} />);
    fireEvent.click(screen.getByRole("button", { name: /flat view/i }));
    expect(screen.getAllByTestId("signal-line").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("grouped-view")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /grouped view/i }));
    expect(screen.getByTestId("grouped-view")).toBeInTheDocument();
  });
});
