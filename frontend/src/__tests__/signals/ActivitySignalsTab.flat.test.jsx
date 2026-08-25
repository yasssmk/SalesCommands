// frontend/src/__tests__/signals/ActivitySignalsTab.flat.test.jsx
//
// Flat view of the Activity Signals tab, after the B2-FE rewire: the flat
// branch is fed by the aggregated endpoint via useAggregatedSignals (one
// server-paginated mixed list) instead of the per-type client fan-out. The
// grouped branch still uses useActivityAllSignals.
//
// Proves the flat branch:
//   - renders SignalLine rows straight from the aggregated hook, each typed
//     from its own signal_type,
//   - drives the aggregated hook's status filter server-side (statuses arg),
//   - opens the signal drawer on row click,
//   - shows Reopen on a rejected row and calls reopenSignal,
//   - advances / rewinds the server page (page arg) via the pager.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

// Grouped view still consumes this; give it a minimal payload so the tab
// mounts in grouped mode without crashing before we toggle to flat.
vi.mock("hooks/useActivityAllSignals", () => ({
  default: vi.fn(() => ({
    qualificationSignals: [],
    techStackSignals: [],
    blockerSignals: [],
    nextStepSignals: [],
    allSignals: [],
    loading: false,
    error: null,
    mutateAll: vi.fn(),
  })),
}));

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

function switchToFlat() {
  fireEvent.click(screen.getByRole("button", { name: /flat/i }));
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
    switchToFlat();

    expect(screen.getAllByTestId("signal-line")).toHaveLength(3);
    expect(screen.getByText("Pain signal flat")).toBeInTheDocument();
    expect(screen.getByText("Objective signal flat")).toBeInTheDocument();
    expect(screen.getByText("Budget frozen flat")).toBeInTheDocument();
  });

  it("scopes the aggregated call to this activity and the qualification+blocker types", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    const args = lastHookArgs();
    expect(args.activityId).toBe("act-flat");
    expect(args.signalTypes).toEqual([
      "pain",
      "objective",
      "impact",
      "tech-stack",
      "blockers",
    ]);
    expect(args.pageSize).toBe(20);
  });

  it("drives status filtering server-side (Validated → statuses arg)", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    // hideCounts is on in flat mode → plain "Validated" chip label. The
    // filter chip is a button; the row status chip is not, so scope by role.
    fireEvent.click(screen.getByRole("button", { name: "Validated" }));
    expect(lastHookArgs().statuses).toEqual(["VALIDATED"]);
  });

  it("adds REJECTED to the statuses arg when 'Include rejected' is checked", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    fireEvent.click(screen.getByRole("checkbox"));
    expect(lastHookArgs().statuses).toContain("REJECTED");
  });

  it("opens the signal drawer when a row is clicked", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

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
    switchToFlat();

    const reopenBtn = screen.getByRole("button", { name: /reopen/i });
    await act(async () => {
      fireEvent.click(reopenBtn);
    });
    expect(reopenSignal).toHaveBeenCalledWith("pain", "r1");
  });

  it("advances and rewinds the server page via the pager", () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ pageCount: 3 }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    switchToFlat();

    expect(lastHookArgs().page).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /go to next page/i }));
    expect(lastHookArgs().page).toBe(2);

    fireEvent.click(screen.getByRole("button", { name: /go to previous page/i }));
    expect(lastHookArgs().page).toBe(1);
  });

  it("shows the sort select only in flat view", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByLabelText("Sort")).not.toBeInTheDocument();
    switchToFlat();
    expect(screen.getByLabelText("Sort")).toBeInTheDocument();
  });
});
