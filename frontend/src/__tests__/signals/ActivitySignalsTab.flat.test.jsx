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
// SIG-5d: Objective edit goes to the new drawer content — stub it to assert routing.
vi.mock("sections/activities/workspace/EditObjectiveContent", () => ({
  default: () => <div data-testid="edit-objective-stub" />,
}));
// S3: Pain edit goes to the new chassis drawer content — stub it to assert routing.
vi.mock("sections/activities/workspace/EditPainContent", () => ({
  default: () => <div data-testid="edit-pain-stub" />,
}));
import { render as rtlRender, screen, fireEvent, cleanup, act, within } from "@testing-library/react";
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
import { reopenSignal, validateSignal, rejectSignal } from "api/signals/signals";
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

  it("renders the pending rows straight from the aggregated hook (validated collapsed)", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    // Default: "To validate" open → the 2 pending rows show; "Validated" is
    // collapsed → its objective row is not mounted.
    expect(screen.getAllByTestId("signal-line")).toHaveLength(2);
    expect(screen.getByText("Pain signal flat")).toBeInTheDocument();
    expect(screen.getByText("Budget frozen flat")).toBeInTheDocument();
    expect(screen.queryByText("Objective signal flat")).not.toBeInTheDocument();
  });

  it("renders the 3 status section headers when all statuses are present", () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          { id: "p1", status: "PENDING", summary: "Pending pain", _signalType: "pain" },
          { id: "o1", status: "VALIDATED", summary: "Validated objective", _signalType: "objective" },
          { id: "r1", status: "REJECTED", summary: "Rejected blocker", _signalType: "blockers" },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    // Section headers render even when collapsed.
    expect(screen.getByText("To validate")).toBeInTheDocument();
    expect(screen.getByText("Validated")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("scopes the call to this activity + flat types, fetches ALL 3 statuses, pageSize 100", () => {
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
    // The validation worklist always loads all 3 statuses (Rejected is part of it).
    expect(args.statuses).toEqual(["PENDING", "VALIDATED", "REJECTED"]);
    expect(args.pageSize).toBe(100);
  });

  it("has NO filter button and NO sort select (the validation list has neither)", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByLabelText("Open filters")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Sort")).not.toBeInTheDocument();
  });

  it("validating a pending row inline calls validateSignal(type, id) and revalidates", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    // The two pending rows expose a ✓ Validate button; click the pain one.
    const validateBtns = screen.getAllByRole("button", { name: /validate signal/i });
    expect(validateBtns.length).toBeGreaterThan(0);
    await act(async () => {
      fireEvent.click(validateBtns[0]);
    });
    expect(validateSignal).toHaveBeenCalledWith("pain", "p1");
  });

  it("rejecting a pending row inline calls rejectSignal(type, id)", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    const rejectBtns = screen.getAllByRole("button", { name: /reject signal/i });
    await act(async () => {
      fireEvent.click(rejectBtns[0]);
    });
    expect(rejectSignal).toHaveBeenCalledWith("pain", "p1");
  });

  it("a failed inline validate surfaces a snackbar (business error)", async () => {
    validateSignal.mockResolvedValueOnce({ success: false, error: "Complete missing fields" });
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: /validate signal/i })[0]);
    });
    expect(displayErrorSnackbar).toHaveBeenCalled();
  });

  it("edits an Objective via the new EditObjectiveContent drawer (SIG-5d), not the legacy dialog", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    // The objective row lives in the collapsed Validated section — expand it.
    fireEvent.click(screen.getByText("Validated"));
    fireEvent.click(await screen.findByText("Objective signal flat"));
    // Edit in the detail routes objectives to the new drawer content.
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(screen.getByTestId("edit-objective-stub")).toBeInTheDocument();
  });

  it("edits a Pain via the new EditPainContent drawer (S3), not the legacy dialog", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    // The pain row is PENDING → in the open "To validate" section. Open its detail.
    fireEvent.click(await screen.findByText("Pain signal flat"));
    // Edit in the detail routes Pain to the new chassis drawer content.
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(screen.getByTestId("edit-pain-stub")).toBeInTheDocument();
  });

  it("UI-1: opening an Objective shows the coque header title 'Objective'", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(screen.getByText("Validated"));
    fireEvent.click(await screen.findByText("Objective signal flat"));
    // The header (title + status pill) is owned by the coque now.
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Objective");
    expect(screen.queryByTestId("objective-detail-title")).not.toBeInTheDocument();
  });

  it("SIG-5e-fix4: validating from the objective drawer refreshes it to the Validated detail (stays open)", async () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          {
            id: "op1",
            status: "PENDING",
            summary: "Pending objective",
            _signalType: "objective",
            what: "OPS",
            dimension: "TIME",
            scope_level: "COMPANY",
            source_context: { contacts: [] },
          },
        ],
      }),
    );
    // The drawer's Validate action's accessible name ends in "Validate"
    // (icon + label); the row button is "Validate signal" and the section
    // toggle is "…To validate 1" — anchoring on the ending targets the drawer.
    const drawerValidate = { name: /Validate$/ };
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Pending objective"));
    // The objective detail opens with a Pending pill and a Validate action.
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Pending");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", drawerValidate));
    });
    expect(validateSignal).toHaveBeenCalledWith("objective", "op1");
    // Drawer stays open and RETURNS to the detail, now Validated — the coque
    // header title stays and the coque status pill flips, the drawer's Validate
    // action is gone (not stale Pending content).
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Objective");
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Validated");
    expect(screen.queryByRole("button", drawerValidate)).not.toBeInTheDocument();
  });

  it("UI-1: objective drawer header (title + pill + ×) is owned by the coque, no in-content header", async () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          {
            id: "op2", status: "VALIDATED", summary: "Validated objective",
            _signalType: "objective", what: "OPS", dimension: "TIME",
            scope_level: "COMPANY", source_context: { contacts: [] },
          },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(screen.getByText("Validated"));
    fireEvent.click(await screen.findByText("Validated objective"));
    // Header lives in the coque: title + status pill + a single close (coque ×).
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Objective");
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Validated");
    expect(screen.getAllByRole("button", { name: /close drawer/i })).toHaveLength(1);
    // The in-content objective header is gone (suppressed by headerInCoque).
    expect(screen.queryByTestId("objective-detail-header")).not.toBeInTheDocument();
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
    // The Rejected section is collapsed by default — expand it to reach the row.
    fireEvent.click(screen.getByText("Rejected"));
    fireEvent.click(await screen.findByTestId("signal-line"));

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
