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

import { describe, it, expect, vi, beforeEach, afterEach, onTestFinished } from "vitest";
// The legacy dialog renders a marker ONLY when opened, so a test can prove a
// type does NOT fall back to it.
vi.mock("components/signals/SignalEditDrawer", () => ({
  default: ({ open }) => (open ? <div data-testid="legacy-edit-dialog" /> : null),
}));
// Objection S2: EditObjectionContent renders for real; stub only its contact
// picker (AsyncContactSelect signature: onChange(event, contact)).
vi.mock("components/AsyncSelection/AsyncContactSelect", () => ({
  default: (props) => (
    <button
      type="button"
      onClick={(e) =>
        props.onChange(e, { id: "c-new", first_name: "Nina", last_name: "Newman", job_title: "COO" })
      }
    >
      pick contact
    </button>
  ),
}));
// SIG-5d: Objective edit goes to the new drawer content — stub it to assert routing.
vi.mock("sections/activities/workspace/EditObjectiveContent", () => ({
  default: () => <div data-testid="edit-objective-stub" />,
}));
// S3: Pain edit goes to the new chassis drawer content — stub it to assert routing.
vi.mock("sections/activities/workspace/EditPainContent", () => ({
  default: () => <div data-testid="edit-pain-stub" />,
}));
// S3: Impact edit goes to the new chassis drawer content — stub it to assert routing.
vi.mock("sections/activities/workspace/EditImpactContent", () => ({
  default: () => <div data-testid="edit-impact-stub" />,
}));
// S3: Constraint edit goes to the new chassis drawer content — stub it to assert routing.
vi.mock("sections/activities/workspace/EditConstraintContent", () => ({
  default: () => <div data-testid="edit-constraint-stub" />,
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
  updateSignal: vi.fn(() => Promise.resolve({ success: true })),
}));

// People S3: EditPeopleContent renders for real — stub its department choices.
vi.mock("api/businessData/contacts", () => ({
  useGetContactChoices: vi.fn(() => ({ standardDepartments: [] })),
}));

// x-date-pickers — stubbed in tests (jsdom can't resolve its ESM), same as
// OutcomeDrawerContent.test: a "pick" button fires onChange with a dayjs date.
vi.mock("@mui/x-date-pickers/DatePicker", async () => {
  const { default: dayjs } = await import("dayjs");
  return {
    DatePicker: (props) => (
      <button
        type="button"
        data-testid={`pick-${props.label}`}
        onClick={() => props.onChange(dayjs("2026-12-31"))}
      >
        pick {props.label}
      </button>
    ),
  };
});
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import ActivitySignalsTab from "sections/activities/workspace/ActivitySignalsTab";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import {
  reopenSignal,
  validateSignal,
  rejectSignal,
  updateSignal,
  useGetSignalChoices,
} from "api/signals/signals";
import { useSyncExternalStore } from "react";
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

  it("edits an Impact via the new EditImpactContent drawer (S3), not the legacy dialog", async () => {
    // A PENDING impact row → in the open "To validate" section.
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          { id: "i1", status: "PENDING", summary: "Impact signal flat", _signalType: "impact" },
        ],
        count: 1,
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Impact signal flat"));
    // Edit in the detail routes Impact to the new chassis drawer content.
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(screen.getByTestId("edit-impact-stub")).toBeInTheDocument();
  });

  it("edits a Constraint via the new EditConstraintContent drawer (S3), not the legacy dialog", async () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          { id: "cn1", status: "PENDING", summary: "Constraint signal flat", _signalType: "constraints" },
        ],
        count: 1,
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Constraint signal flat"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(screen.getByTestId("edit-constraint-stub")).toBeInTheDocument();
  });

  it("Objection S2 (E1): Edit from the Objection detail → EditObjectionContent in the coque, NOT the legacy dialog", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Budget frozen flat"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Edit objection");
    expect(screen.getByText("What's the objection?")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("inline-read-contact")); // click-to-edit contact
    expect(screen.getByRole("button", { name: "pick contact" })).toBeInTheDocument();
    expect(screen.queryByTestId("legacy-edit-dialog")).not.toBeInTheDocument();
  });

  it("Objection S2 (E6): pick a contact → Save → back to the Objection detail, 'Raised by' shows that contact", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Budget frozen flat"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    fireEvent.click(screen.getByTestId("inline-read-contact")); // click-to-edit contact
    fireEvent.click(screen.getByRole("button", { name: "pick contact" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledWith("blockers", "b1", expect.objectContaining({ contact: "c-new" }));
    expect(screen.getByTestId("objection-detail-body")).toBeInTheDocument();
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Objection");
    expect(within(screen.getByTestId("objection-raised-by")).getByText("Nina Newman")).toBeInTheDocument();
  });

  it("Objection S2 (E7): Cancel → back to the Objection detail unchanged, no API call", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Budget frozen flat"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    fireEvent.click(screen.getByTestId("inline-read-contact")); // click-to-edit contact
    fireEvent.click(screen.getByRole("button", { name: "pick contact" }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(updateSignal).not.toHaveBeenCalled();
    expect(screen.getByTestId("objection-detail-body")).toBeInTheDocument();
    expect(screen.getByTestId("objection-raised-by")).toHaveTextContent("No contact attributed");
    expect(screen.getByTestId("objection-summary-text")).toHaveTextContent("Budget frozen flat");
  });

  // Competitor C2 — a pending competitor row for the edit routing tests.
  const COMPETITOR_ROW = {
    id: "cmp-edit", status: "PENDING", _signalType: "competitors",
    competitor_name: "Intercom",
    summary: "The prospect is also evaluating Intercom instead of us.",
    source_quote: "We're also looking at Intercom.",
    source_context: { contacts: [] },
  };
  const openCompetitorEdit = async () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ signals: [COMPETITOR_ROW] }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Intercom"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
  };

  it("Competitor C2: Edit from the Competitor detail → EditCompetitorContent in the coque, NOT the legacy dialog", async () => {
    await openCompetitorEdit();
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Edit competitor");
    expect(screen.getByTestId("inline-read-competitor_name")).toHaveTextContent("Intercom");
    expect(screen.queryByTestId("legacy-edit-dialog")).not.toBeInTheDocument();
  });

  it("Competitor C2: rename → Save → PATCH then back to the Competitor detail showing the new name", async () => {
    await openCompetitorEdit();
    fireEvent.click(screen.getByTestId("inline-read-competitor_name"));
    fireEvent.change(screen.getByTestId("inline-input-competitor_name"), {
      target: { value: "HubSpot" },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledWith("competitors", "cmp-edit", {
      competitor_name: "HubSpot",
      summary: COMPETITOR_ROW.summary,
      source_quote: COMPETITOR_ROW.source_quote,
    });
    expect(screen.getByTestId("competitor-detail-body")).toBeInTheDocument();
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Competitor");
    expect(screen.getByTestId("competitor-summary-text")).toHaveTextContent("HubSpot");
  });

  it("Competitor C2: Cancel → back to the Competitor detail unchanged, no API call", async () => {
    await openCompetitorEdit();
    fireEvent.click(screen.getByTestId("inline-read-competitor_name"));
    fireEvent.change(screen.getByTestId("inline-input-competitor_name"), {
      target: { value: "HubSpot" },
    });
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(updateSignal).not.toHaveBeenCalled();
    expect(screen.getByTestId("competitor-detail-body")).toBeInTheDocument();
    expect(screen.getByTestId("competitor-summary-text")).toHaveTextContent("Intercom");
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

  it("Objection S1 (R4): opening a blocker shows the coque header 'Objection' + status pill on the chassis", async () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Budget frozen flat"));
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Objection");
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Pending");
    expect(screen.getByTestId("objection-detail-body")).toBeInTheDocument();
    // Header owned by the coque: no in-content header, a single close (coque ×).
    expect(screen.queryByTestId("objection-detail-header")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /close drawer/i })).toHaveLength(1);
  });

  it("People S2 (P4): opening a people signal shows the coque header 'People' + status pill on the chassis", async () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          {
            id: "pe1", status: "PENDING", _signalType: "people",
            full_name: "Marc Dubois", role: "ECONOMIC_BUYER", role_display: "Economic Buyer",
            target_contact: null, target_department: null, source_context: { contacts: [] },
          },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Marc Dubois"));
    expect(screen.getByTestId("coque-title")).toHaveTextContent("People");
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Pending");
    expect(screen.getByTestId("people-detail-body")).toBeInTheDocument();
    // Header owned by the coque: no in-content header, a single close (coque ×).
    expect(screen.queryByTestId("people-detail-header")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /close drawer/i })).toHaveLength(1);
  });

  it("TechStack T1: opening a tech-stack signal shows the coque header 'Tech Stack' + status pill on the chassis", async () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          {
            id: "ts1", status: "PENDING", _signalType: "tech-stack",
            tech_name: "HubSpot", usage_scope: "UNKNOWN", usage_departments: [],
            source_context: { contacts: [] },
          },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("HubSpot"));
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Tech Stack");
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Pending");
    expect(screen.getByTestId("techstack-detail-body")).toBeInTheDocument();
    // Header owned by the coque: no in-content header, a single close (coque ×).
    expect(screen.queryByTestId("techstack-detail-header")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /close drawer/i })).toHaveLength(1);
  });

  it("Competitor C1: opening a competitor shows the coque header 'Competitor' + status pill on the chassis", async () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          {
            id: "cmp1", status: "PENDING", _signalType: "competitors",
            competitor_name: "Intercom",
            summary: "The prospect is also evaluating Intercom instead of us.",
            source_quote: "We're also looking at Intercom.",
            source_context: { contacts: [] },
          },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Intercom"));
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Competitor");
    expect(screen.getByTestId("status-pill")).toHaveTextContent("Pending");
    expect(screen.getByTestId("competitor-detail-body")).toBeInTheDocument();
    expect(screen.getByTestId("competitor-summary-text")).toHaveTextContent("Intercom");
    expect(screen.getByTestId("competitor-summary")).toHaveTextContent(
      "The prospect is also evaluating Intercom instead of us.",
    );
    expect(screen.getByTestId("competitor-source")).toHaveTextContent("We're also looking at Intercom.");
    // Header owned by the coque: no in-content header, a single close (coque ×).
    expect(screen.queryByTestId("competitor-detail-header")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /close drawer/i })).toHaveLength(1);
  });

  it("TechStack T2a: choices arriving AFTER the drawer opened reach the open detail (no reopen)", async () => {
    // A tiny SWR-like store: the choices arrive asynchronously and every hook
    // consumer re-renders on its own (no parent re-render, no reopen).
    let current = { choices: null, choicesLoading: true };
    const listeners = new Set();
    const choicesStore = {
      subscribe: (fn) => {
        listeners.add(fn);
        return () => listeners.delete(fn);
      },
      get: () => current,
      load: (choices) => {
        current = { choices, choicesLoading: false };
        listeners.forEach((fn) => fn());
      },
    };
    vi.mocked(useGetSignalChoices).mockImplementation(() =>
      useSyncExternalStore(choicesStore.subscribe, choicesStore.get),
    );
    // vi.clearAllMocks (beforeEach) keeps implementations — restore the module
    // default after this test so the store never leaks into later tests.
    onTestFinished(() =>
      vi.mocked(useGetSignalChoices).mockImplementation(() => ({ choices: {}, choicesLoading: false })),
    );
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          {
            id: "ts2", status: "PENDING", _signalType: "tech-stack",
            tech_name: "Datadog", usage_scope: "UNKNOWN", usage_departments: [],
            source_context: { contacts: [] },
          },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);

    // Drawer opened BEFORE the choices are loaded → no label yet.
    fireEvent.click(await screen.findByText("Datadog"));
    expect(screen.getByTestId("techstack-usage")).not.toHaveTextContent("Unknown");

    // The choices arrive → the open detail shows "Unknown" without a reopen.
    act(() =>
      choicesStore.load({
        usage_scopes: [
          { value: "DEPARTMENT", label: "Department" },
          { value: "COMPANY", label: "Company" },
          { value: "UNKNOWN", label: "Unknown" },
        ],
      }),
    );
    expect(screen.getByTestId("techstack-usage")).toHaveTextContent("Unknown");
  });

  const TECH_ROW = {
    id: "ts-edit", status: "PENDING", _signalType: "tech-stack",
    tech_name: "HubSpot", is_to_replace: false,
    usage_scope: "COMPANY", usage_departments: [],
    usage_start_year: null, renewal_date: null, cost_description: "",
    is_discontinued: false, discontinued_date: null,
    notes: "", source_quote: "We run on HubSpot.",
    source_context: { contacts: [] },
  };

  const PEOPLE_ROW = {
    id: "pe2", status: "PENDING", _signalType: "people",
    full_name: "Marc Dubois", role: "ECONOMIC_BUYER", role_display: "Economic Buyer",
    target_contact: null, target_department: null, notes: "", source_quote: "Marc decides.",
    source_context: { contacts: [] },
  };

  it("TechStack T2b (a): Edit from the TechStack detail → EditTechStackContent in the coque, NOT the legacy dialog", async () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ signals: [TECH_ROW] }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("HubSpot"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Edit tech stack");
    expect(screen.getByTestId("techstack-edit")).toBeInTheDocument();
    expect(screen.queryByTestId("legacy-edit-dialog")).not.toBeInTheDocument();
  });

  it("TechStack T2b (a): edit notes → Save → back to the TechStack detail showing them", async () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ signals: [TECH_ROW] }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("HubSpot"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    fireEvent.click(screen.getByTestId("inline-read-notes"));
    fireEvent.change(screen.getByTestId("inline-input-notes"), {
      target: { value: "Unhappy with support." },
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledWith(
      "tech-stack", "ts-edit", expect.not.objectContaining({ is_to_replace: expect.anything() }),
    );
    expect(screen.getByTestId("techstack-detail-body")).toBeInTheDocument();
    expect(screen.getByTestId("techstack-notes")).toHaveTextContent("Unhappy with support.");
  });

  it("People S3 (E1): Edit from the People detail → EditPeopleContent in the coque, NOT the legacy dialog", async () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ signals: [PEOPLE_ROW] }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Marc Dubois"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    expect(screen.getByTestId("coque-title")).toHaveTextContent("Edit people");
    expect(screen.getByText("Who is this person?")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("inline-read-contact")); // click-to-edit contact
    expect(screen.getByRole("button", { name: "pick contact" })).toBeInTheDocument();
    expect(screen.queryByTestId("legacy-edit-dialog")).not.toBeInTheDocument();
  });

  it("People S3 (E7): pick a contact → Save → back to the People detail showing that contact", async () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ signals: [PEOPLE_ROW] }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Marc Dubois"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    fireEvent.click(screen.getByTestId("inline-read-contact")); // click-to-edit contact
    fireEvent.click(screen.getByRole("button", { name: "pick contact" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /save/i }));
    });
    expect(updateSignal).toHaveBeenCalledWith("people", "pe2", expect.objectContaining({ target_contact: "c-new" }));
    expect(screen.getByTestId("people-detail-body")).toBeInTheDocument();
    expect(screen.getByTestId("coque-title")).toHaveTextContent("People");
    expect(within(screen.getByTestId("people-contact")).getByText("Nina Newman")).toBeInTheDocument();
  });

  it("People S3 (E7b): Cancel → back to the People detail unchanged, no API call", async () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ signals: [PEOPLE_ROW] }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    fireEvent.click(await screen.findByText("Marc Dubois"));
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    fireEvent.click(screen.getByTestId("inline-read-contact")); // click-to-edit contact
    fireEvent.click(screen.getByRole("button", { name: "pick contact" }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(updateSignal).not.toHaveBeenCalled();
    expect(screen.getByTestId("people-detail-body")).toBeInTheDocument();
    expect(screen.getByTestId("people-contact")).toHaveTextContent("No contact linked");
  });

  // People S4 — the Activity list renders a People line 1 as an identity:
  // **First Last** · Department · Role (contact first, then full_name, then
  // "Unnamed person"); line 2 (date + source participant) is unchanged.
  const PEOPLE_LINE = {
    id: "pl1", status: "PENDING", _signalType: "people",
    full_name: "Sophie M.",
    target_contact: { id: "c-s", first_name: "Sophie", last_name: "Martin", job_title: "CFO" },
    target_department: { id: "1", name: "Finance" },
    role: "ECONOMIC_BUYER", role_display: "Economic Buyer",
    source_context: { contacts: [{ id: "p1", first_name: "Paula", last_name: "Participant" }] },
  };
  const renderPeopleLine = (overrides = {}) => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({ signals: [{ ...PEOPLE_LINE, ...overrides }] }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    return screen.getByTestId("people-identity-line");
  };

  it("People S4 (R1): line 1 = **Sophie Martin** · Finance · Economic Buyer (contact first, name bold)", () => {
    const identity = renderPeopleLine();
    expect(identity).toHaveTextContent(/^Sophie Martin · Finance · Economic Buyer$/);
    expect(getComputedStyle(within(identity).getByText("Sophie Martin")).fontWeight).toBe("600");
    expect(screen.queryByText("Sophie M.")).not.toBeInTheDocument();
  });

  it("People S4 (R2): no contact and no name → 'Unnamed person' leads line 1", () => {
    const identity = renderPeopleLine({ target_contact: null, full_name: "" });
    expect(identity).toHaveTextContent(/^Unnamed person · Finance · Economic Buyer$/);
  });

  it("People S4 (R3): no department → no orphan separator", () => {
    const identity = renderPeopleLine({
      target_contact: null, full_name: "Karim", target_department: null,
      role: "END_USER", role_display: "End User",
    });
    expect(identity).toHaveTextContent(/^Karim · End User$/);
  });

  it("People S4 (R4): line 2 still shows the source participant", () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ signals: [PEOPLE_LINE] }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    const line = screen.getByTestId("signal-line");
    expect(within(line).getByText("Paula Participant")).toBeInTheDocument();
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

// ==============================|| T5b — AI REVIEW NOTICE ||============================== //

const AI_NOTICE =
  "Transcript analysis can make mistakes. Please check each signal's details before validating it.";

describe("ActivitySignalsTab — AI review notice in 'To validate' (T5b)", () => {
  it("shows the notice at the head of the 'To validate' section, before its rows", () => {
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    const notice = screen.getByText(AI_NOTICE);
    const header = screen.getByText("To validate");
    const firstRow = screen.getAllByTestId("signal-line")[0];
    // Header → notice → first pending row, in document order.
    expect(header.compareDocumentPosition(notice) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(notice.compareDocumentPosition(firstRow) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getAllByText(AI_NOTICE)).toHaveLength(1);
  });

  it("is absent when nothing is left to validate (only Validated / Rejected)", () => {
    useAggregatedSignals.mockImplementation(() =>
      flatReturn({
        signals: [
          { id: "o1", status: "VALIDATED", summary: "Validated objective", _signalType: "objective" },
          { id: "r1", status: "REJECTED", summary: "Rejected blocker", _signalType: "blockers" },
        ],
      }),
    );
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    // Open both sections: the notice must not live in them either.
    fireEvent.click(screen.getByText("Validated"));
    fireEvent.click(screen.getByText("Rejected"));
    expect(screen.queryByText("To validate")).not.toBeInTheDocument();
    expect(screen.queryByText(AI_NOTICE)).not.toBeInTheDocument();
  });

  it("is absent when the activity has no signal at all", () => {
    useAggregatedSignals.mockImplementation(() => flatReturn({ signals: [], count: 0 }));
    render(<ActivitySignalsTab activity={MOCK_ACTIVITY} />);
    expect(screen.queryByText(AI_NOTICE)).not.toBeInTheDocument();
  });
});
