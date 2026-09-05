// frontend/src/__tests__/signals/ActivitySignalsTab.flat.test.jsx
//
// SIG-2 — the Activity "Signals" tab is FLAT-FORCED: the Grouped/Flat toggle is
// gone (the grouped synthesis stays only in ActivityQualificationTab / DC /
// Account). The tab renders the SignalsValidationList — one flat list split into
// 3 status sections (To validate / Validated / Rejected), each grouped by type —
// fed by the aggregated endpoint (all matching signals, pageSize 100, no pager).
//
// Proves:
//   - no Grouped/Flat toggle (flat forced),
//   - renders the validation list straight from the aggregated hook,
//   - scopes the aggregated call to this activity + the flat types + pageSize 100,
//   - drives the status / type filters server-side,
//   - opens the signal drawer on row click and reopens a rejected signal there.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
vi.mock("components/signals/SignalEditDrawer", () => ({ default: () => null }));
import { render as rtlRender, screen, fireEvent, cleanup, act } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";

// The signal detail lives in the single workspace drawer coque (openDrawer);
// render the tab inside that coque so a row click shows its detail as in the app.
const render = (ui, opts) => rtlRender(ui, { wrapper: WorkspaceCoque, ...opts });

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

describe("ActivitySignalsTab — flat forced (SIG-2)", () => {
  it("has NO Grouped/Flat toggle", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByRole("button", { name: /grouped view/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /flat view/i })).not.toBeInTheDocument();
  });

  it("renders the validation list rows straight from the aggregated hook", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.getAllByTestId("signal-line")).toHaveLength(3);
    expect(screen.getByText("Pain signal flat")).toBeInTheDocument();
    expect(screen.getByText("Objective signal flat")).toBeInTheDocument();
    expect(screen.getByText("Budget frozen flat")).toBeInTheDocument();
  });

  it("renders the 3 status sections", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    const titles = screen
      .getAllByTestId("signal-section-title")
      .map((el) => el.textContent);
    // Rejected is empty by default (not fetched) → its section is hidden.
    expect(titles).toEqual(["To validate", "Validated"]);
  });

  it("scopes the aggregated call to this activity, the flat types, and fetches all (pageSize 100)", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    const args = lastHookArgs();
    expect(args.activityId).toBe("act-flat");
    expect(args.signalTypes).toEqual([
      "pain",
      "objective",
      "impact",
      "tech-stack",
      "blockers",
      "constraints",
      "competitors",
      "people",
    ]);
    // Rejected excluded by default (structural sections still cover it when opted in).
    expect(args.statuses).toEqual(["PENDING", "VALIDATED"]);
    expect(args.pageSize).toBe(100);
  });

  it("shows the filter icon and the sort select", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByLabelText("Open filters")).toBeInTheDocument();
    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
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

  it("opens the drawer on a rejected row and reopens from there", async () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          { id: "r1", status: "REJECTED", summary: "Rejected flat", _signalType: "pain" },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    expect(screen.queryByRole("button", { name: /reopen/i })).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("signal-line"));

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /reopen/i }));
    });
    expect(reopenSignal).toHaveBeenCalledWith("pain", "r1");
  });

  it("blanks to the red error surface only when the list is empty", () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({ signals: [], count: 0, error: new Error("boom") }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.getByText("Failed to load signals")).toBeInTheDocument();
    expect(screen.queryAllByTestId("signal-line")).toHaveLength(0);
  });

  it("keeps the list on a transient error and snackbars it", () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({ error: new Error("boom") }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByText("Failed to load signals")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("signal-line").length).toBeGreaterThan(0);
    expect(displayErrorSnackbar).toHaveBeenCalled();
  });
});
