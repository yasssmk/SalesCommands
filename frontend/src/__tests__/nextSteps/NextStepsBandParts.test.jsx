// frontend/src/__tests__/nextSteps/NextStepsBandParts.test.jsx
//
// Sprint Next steps 5.3 — parts 2 to 4 of the "Next steps" band, on the Activity
// workspace PAGE as really rendered (views/activities/workspace/index.jsx):
//   part 2 "To validate" — the generic SignalsValidationList filtered on
//     next-steps (useAggregatedSignals), SignalLine line 1 IDENTICAL to the
//     other types (line 2: the 5.8f PO exception); the row ✓ validates NOTHING (it opens the detail drawer until
//     the flow lands in 5.6); ✗ = the existing rejectSignal;
//   part 3 — Validated = RESOLVED next steps, with SignalLine's generic optional
//     3rd line `extra` (→ title · type · date · status pill of the activity
//     created OR linked; click → the activity); Rejected in the signal format,
//     Reopen offered except on a resolved next step (rule 2.1);
//   part 4 — (5.8e) the "+ Add next step" pill of part 1's header → a row of
//     the 7 ActivityType pills → the creation in the coque with that type;
//   outside a DC (DC-only guard) parts 2-3 are hidden, parts 1 and 4 stay.
// 5.4 — the next step DETAIL opens in the single workspace coque (as the 8 other
// types), on the standard chassis (NextStepDetailView, section B of 5.0):
// ① Proposal ② Purpose ③ Source (+ quote badge) ④ Activity when (5.8g: no
// People section — the names cited are not shown)
// resolved; "Unknown" in full for an empty field; advice_rationale never shown;
// a resolved next step is read-only (rule 2.1).
// The band, ActivityNextStepsTab, SignalsValidationList, SignalLine, the coque
// and the detail are REAL; data hooks, API calls and the other bands are mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";
import { testTheme } from "../_utils/aphoriqTheme";

const mockPush = vi.fn();
let mockActivity;
let mockNextSteps;

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/activities/act-1",
  useSearchParams: () => new URLSearchParams(),
}));
// The coque in push mode (large screen), as in workspaceDrawer tests.
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
vi.mock("@mui/x-date-pickers/DatePicker", () => ({ DatePicker: () => <input /> }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));

vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetActivity: () => ({
    activity: mockActivity, activityLoading: false, activityError: null, mutateActivity: vi.fn(),
  }),
  updateActivity: vi.fn(),
  // 5.8d — the creation in the coque.
  createActivity: vi.fn(async () => mockCreateActivityResult),
  createActivityWithEntities: vi.fn(async () => mockCreateActivityResult),
}));
let mockCreateActivityResult = { success: true, data: { id: "act-new" } };
// useAuth().user in its REAL shape: the auth payload of the backend
// (core.auth_service.auth_user_payload — login / current user / refresh,
// pinned by tests/integration/end_users/test_auth_user_payload_names.py).
const AUTH_USER = {
  id: "u-1", name: "Yasmine Kawi", first_name: "Yasmine", last_name: "Kawi",
  email: "yasmine@acme.test", role: "Individual", role_tier: "individual", avatar: null,
  client_id: "t-1", client_name: "Tenant A",
};
let mockAuthUser = AUTH_USER;
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ user: mockAuthUser, tenantId: "t-1" }),
  default: () => ({ user: mockAuthUser, tenantId: "t-1" }),
}));
// The inline contact sub-form → a one-click save (as in the ActivityModal tests).
vi.mock("sections/accounts/activities/components", async (importOriginal) => ({
  ...(await importOriginal()),
  InlineContactForm: ({ onSave }) => (
    <button type="button" onClick={() => onSave({ first_name: "Isabelle", last_name: "Roux" })}>
      save inline contact
    </button>
  ),
}));
vi.mock("api/aiPipelines/lastRun", () => ({
  useGetLastExtractionRun: () => ({
    lastRun: { id: "run-1" }, latestRun: null, runsByPipeline: {}, mutateLastRun: vi.fn(),
  }),
}));
vi.mock("api/signals/signalCounts", () => ({
  useActivitySignalCounts: () => ({ counts: {}, mutateCounts: vi.fn() }),
}));
// The aggregated endpoint: the next steps for a next-steps query; nothing for
// the Signals band halo (the other types).
const mockMutateList = vi.fn();
vi.mock("api/signals/aggregatedSignals", () => ({
  default: (args) => ({
    signals: (args?.signalTypes || []).includes("next-steps") ? mockNextSteps : [],
    loading: false, error: null, mutate: mockMutateList,
  }),
}));
vi.mock("hooks/usePipelineRunner", () => ({ default: () => ({ state: {} }) }));
vi.mock("contexts/BreadcrumbContext", () => ({ useBreadcrumb: () => ({ setCrumbs: vi.fn() }) }));
vi.mock("components/WorkspaceHeader", () => ({ default: () => <div data-testid="header" /> }));
vi.mock("sections/activities/workspace/ActivityHeader", () => ({ default: () => ({ modals: null }) }));
vi.mock("sections/activities/workspace/ActivityContextSection", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityPreparationTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityNotesTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivitySignalsTab", () => ({
  default: () => null,
  ACTIVITY_FLAT_TYPES: ["pain"],
}));
vi.mock("components/signals/SignalsHaloBox", () => ({ default: ({ children }) => <>{children}</> }));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn(),
}));
let mockDcPeople = [];
let mockPatchResponse = null;
vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: () => ({ choices: {}, choicesLoading: false }),
  validateSignal: vi.fn(async () => ({ success: true })),
  rejectSignal: vi.fn(async () => ({ success: true })),
  reopenSignal: vi.fn(async () => ({ success: true })),
  // 5.5 — the DC People (the People picker) and the PATCH.
  useGetSignalsByAccount: vi.fn(() => ({ signals: mockDcPeople, signalsLoading: false })),
  updateSignal: vi.fn(async (_type, id, payload) => ({
    success: true, data: mockPatchResponse ?? { id, ...payload },
  })),
  // 5.6 — the link candidates and the next step read back from the server.
  useNextStepLinkCandidates: vi.fn(() => ({ candidates: mockCandidates, candidatesLoading: false })),
  getSignal: vi.fn(async () => ({ success: true, data: mockServerNextStep })),
  // 5.7 — the link.
  attachNextStepToActivity: vi.fn(async () => mockAttachResult),
  // 5.8d — the names cited with their account contact (server, TD-279 rule).
  // mockCitedDelayMs > 0: the response arrives that long after the mount.
  useNextStepCitedContacts: vi.fn(() => mockUseCited()),
}));
let mockCited = [];
let mockCitedDelayMs = 0;
function mockUseCited() {
  const { useState, useEffect } = require("react");
  const [ready, setReady] = useState(mockCitedDelayMs === 0);
  useEffect(() => {
    if (ready) return undefined;
    const t = setTimeout(() => setReady(true), mockCitedDelayMs);
    return () => clearTimeout(t);
  }, [ready]);
  return ready
    ? { citedContacts: mockCited, citedLoading: false }
    : { citedContacts: [], citedLoading: true };
}
let mockAttachResult = { success: true, data: {} };
let mockCandidates = [];
let mockServerNextStep = null;
// The real module's constants (the inline cycle form's steps, 5.13).
vi.mock("api/accounts/decisionCycles", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetDecisionCyclesByAccount: vi.fn(() => ({
    cycles: [{ id: "dc-1", name: "Deal Acme", is_active: true },
             { id: "dc-2", name: "Deal Other", is_active: true }],
    cyclesLoading: false,
  })),
  useGetDecisionStepsByCycle: vi.fn(() => ({
    steps: [
      { id: "step-4", name: "Technical Fit", order: 4 },
      { id: "step-5", name: "Business Case", order: 5 },
    ],
    stepsLoading: false,
  })),
}));
// The real ActivityModal is out of scope; this stand-in exposes what the flow
// relies on: the next step it is pre-filled from, onSuccess then onClose (the
// real modal's order on a successful create), or onClose alone (cancel).
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: ({ open, nextStepSignal, onSuccess, onClose }) =>
    open ? (
      <div data-testid="activity-modal">
        <span data-testid="modal-prefill">{nextStepSignal?.suggested_title ?? ""}</span>
        <button type="button" onClick={() => { onSuccess?.({ id: "act-new" }); onClose(); }}>
          modal-create
        </button>
        <button type="button" onClick={() => onClose()}>modal-cancel</button>
      </div>
    ) : null,
}));
vi.mock("components/signals/SignalEditDrawer", () => ({
  default: ({ open }) => (open ? <div data-testid="legacy-signal-edit-drawer" /> : null),
}));

// The extraction (the shared Run AI action, 5.12 B) is out of scope here —
// covered by NextStepsBandLayoutPage.
vi.mock("sections/activities/workspace/RunAIAnalysisButton", () => ({
  default: () => null,
  RUN_AI_TRIGGER_VARIANTS: { BUTTON: "button", PILL: "pill" },
}));

import ActivityWorkspacePage from "views/activities/workspace";
import SignalsValidationList from "components/signals/SignalsValidationList";
import {
  validateSignal, rejectSignal, reopenSignal, updateSignal, useGetSignalsByAccount, getSignal,
  useNextStepLinkCandidates, attachNextStepToActivity,
} from "api/signals/signals";
import { displayErrorSnackbar } from "utils/displayError";
import { createActivity, createActivityWithEntities } from "api/accounts/activities";
import { useGetDecisionStepsByCycle } from "api/accounts/decisionCycles";

const render = (ui) => rtlRender(<WorkspaceCoque>{ui}</WorkspaceCoque>);
const DETAIL = "next-step-detail-body";

const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", job_title: "CTO" };

const nextStep = (over = {}) => ({
  id: "ns-p", _signalType: "next-steps", signal_type: "next-steps", status: "PENDING",
  suggested_title: "Send the DPA", suggested_activity_type: "EMAIL",
  created_at: "2026-10-20T10:00:00Z", source_context: { contacts: [THOMAS] },
  linked_activity: null, attached_activity: null, ...over,
});

const compactActivity = (over = {}) => ({
  id: "act-20", title: "Security review", activity_type: "MEETING",
  activity_type_display: "Meeting", status: "PLANNED", status_display: "Planned",
  scheduled_date: "2026-11-03", due_date: null, ...over,
});

const NEXT_STEPS = [
  nextStep(),
  nextStep({ id: "ns-v", status: "VALIDATED", suggested_title: "Book the security review",
             linked_activity: compactActivity() }),
  nextStep({ id: "ns-l", status: "VALIDATED", suggested_title: "Call about pricing",
             attached_activity: compactActivity({ id: "act-21", title: "Pricing call",
               activity_type: "CALL", activity_type_display: "Call", status: "ON_HOLD",
               status_display: "On hold", scheduled_date: "2026-11-10" }) }),
  nextStep({ id: "ns-r", status: "REJECTED", suggested_title: "Train Karim" }),
];

const dcActivity = (over = {}) => ({
  // PLANNED by default; the lock of a COMPLETED / CANCELLED activity is tested below.
  id: "act-1", title: "Atelier", activity_type: "MEETING", status: "PLANNED",
  account: "acc-1", decision_cycle: "dc-1", campaign_detail: null,
  sequence_context: { position: 1, total: 1, next_activities: [] },
  next_planned_step: null, ...over,
});

// 5.8e — "+ Add next step" → a type pill → the creation drawer with that type.
const addNextStep = (typeLabel) => {
  fireEvent.click(screen.getByRole("button", { name: "+ Add next step" }));
  fireEvent.click(within(screen.getByTestId("add-next-step-types"))
    .getByRole("button", { name: typeLabel }));
};

const rowOf = (title) => screen.getByText(title).closest('[data-testid="signal-line"]');
const expand = (section) => fireEvent.click(screen.getByText(section));

const renderPage = (activity = dcActivity(), nextSteps = NEXT_STEPS) => {
  mockActivity = activity;
  mockNextSteps = nextSteps;
  return render(<ActivityWorkspacePage />);
};

afterEach(() => { cleanup(); vi.clearAllMocks(); mockCitedDelayMs = 0; });

describe("Next steps band — part 2, to validate (5.3)", () => {
  it("lists the pending next steps in the generic validation list", () => {
    renderPage();
    expect(screen.getByText("To validate")).toBeInTheDocument();
    expect(rowOf("Send the DPA")).toBeInTheDocument();
    // The former AI suggestion cards and filter bar are gone from the band.
    expect(screen.queryByText("Convert to Activity")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Suggestions")).not.toBeInTheDocument();
  });

  // 5.8f — line 1 stays IDENTICAL to another type's row; line 2 is the PO
  // exception (type · action date · names cited, NextStepsBandReadability).
  it("line 1 is IDENTICAL to another type's row in the validation list", () => {
    renderPage();
    const nextStepRow = rowOf("Send the DPA");
    const { container } = render(
      <SignalsValidationList
        signals={[{ id: "p-1", _signalType: "pain", status: "PENDING", summary: "Send the DPA",
                    created_at: "2026-10-20T10:00:00Z", source_context: { contacts: [THOMAS] } }]}
        onSelect={vi.fn()} onValidate={vi.fn()} onReject={vi.fn()}
      />,
    );
    const painRow = container.querySelector('[data-testid="signal-line"]');
    const line1 = (row) => row.firstElementChild.firstElementChild.outerHTML;
    expect(line1(nextStepRow)).toBe(line1(painRow));
    expect(within(nextStepRow).getByTestId("next-step-line-meta")).toBeInTheDocument();
  });

  it("the row ✓ never validates: it opens the validation flow (5.6)", async () => {
    renderPage();
    fireEvent.click(within(rowOf("Send the DPA")).getByLabelText("Validate signal"));
    expect(await screen.findByTestId("next-step-validate-flow")).toBeInTheDocument();
    expect(validateSignal).not.toHaveBeenCalled();
  });

  it("the row ✗ rejects with the existing rejectSignal", async () => {
    renderPage();
    fireEvent.click(within(rowOf("Send the DPA")).getByLabelText("Reject signal"));
    await waitFor(() => expect(rejectSignal).toHaveBeenCalledWith("next-steps", "ns-p"));
  });
});

describe("Next steps band — part 3, validated / rejected (5.3)", () => {
  it("a resolved next step carries the 3rd line of its activity (created or linked)", () => {
    renderPage();
    expand("Validated");
    const created = within(rowOf("Book the security review")).getByTestId("signal-line-extra");
    expect(created.textContent).toContain("Security review · Meeting · 3 Nov 2026");
    expect(within(created).getByText("Planned")).toBeInTheDocument();
    const linked = within(rowOf("Call about pricing")).getByTestId("signal-line-extra");
    expect(linked.textContent).toContain("Pricing call · Phone Call · 10 Nov 2026");
    expect(within(linked).getByText("On hold")).toBeInTheDocument();
  });

  it("`extra` only on a resolved next step", () => {
    renderPage();
    expand("Validated");
    expand("Rejected");
    expect(screen.getAllByTestId("signal-line-extra")).toHaveLength(2);
    expect(within(rowOf("Send the DPA")).queryByTestId("signal-line-extra")).toBeNull();
    expect(within(rowOf("Train Karim")).queryByTestId("signal-line-extra")).toBeNull();
  });

  it("clicking the 3rd line opens the activity, not the drawer", () => {
    renderPage();
    expand("Validated");
    fireEvent.click(within(rowOf("Book the security review"))
      .getByRole("link", { name: "Open activity Security review" }));
    expect(mockPush).toHaveBeenCalledWith("/activities/act-20");
    expect(screen.queryByTestId(DETAIL)).not.toBeInTheDocument();
  });

  it("a rejected next step can be reopened", async () => {
    renderPage();
    expand("Rejected");
    fireEvent.click(rowOf("Train Karim"));
    fireEvent.click(await screen.findByRole("button", { name: /Reopen/ }));
    await waitFor(() => expect(reopenSignal).toHaveBeenCalledWith("next-steps", "ns-r"));
  });

  it("no Reopen (nor Edit) on a resolved next step (rule 2.1)", async () => {
    renderPage();
    expand("Validated");
    fireEvent.click(rowOf("Book the security review"));
    expect(await screen.findByTestId(DETAIL)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reopen/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /\bEdit\b/ })).not.toBeInTheDocument();
  });
});

describe("Next steps band — part 4 and the DC-only guard (5.3)", () => {
  it("no 'Set a next step manually' any more (5.8e): '+ Add next step' replaces it", () => {
    renderPage();
    expect(screen.queryByText("Add manually")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Set a next step manually/ })).toBeNull();
    addNextStep("Meeting");
    expect(screen.getByTestId("activity-create")).toBeInTheDocument();
  });

  // 5.14b (PO): a SUCCESSFUL campaign activity has its next steps; 5.16: ONE
  // pill, part 4 (« + Add next step », it converts) — no « Start Decision Cycle ».
  it("a SUCCESSFUL campaign activity, no DC born: the next steps and part 4, no conversion block", () => {
    renderPage(dcActivity({ decision_cycle: null, campaign_detail: { id: "camp-1" }, outcome: "SUCCESSFUL" }));
    expect(screen.getByText("To validate")).toBeInTheDocument();
    expect(screen.getByText("Send the DPA")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "+ Add next step" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Start Decision Cycle/ })).toBeNull();
  });
});

// PO decision (after 5.3): the Next steps band IGNORES the lock of a COMPLETED
// activity — the conversation is over, its next steps are handled now (part 4,
// row actions, Edit, Reject, Convert, Reopen); a CANCELLED activity stays
// locked. One predicate, at the band's central point.
describe("Next steps band — the lock of the activity (PO decision)", () => {
  const openRow = async (title, section) => {
    if (section) expand(section);
    fireEvent.click(rowOf(title));
    return screen.findByTestId(DETAIL);
  };

  it("COMPLETED: part 4, quick-create and the row actions are available", () => {
    renderPage(dcActivity({ status: "COMPLETED" }));
    expect(screen.getByRole("button", { name: "+ Add next step" })).toBeInTheDocument();
    expect(within(rowOf("Send the DPA")).getByLabelText("Validate signal")).toBeInTheDocument();
    expect(within(rowOf("Send the DPA")).getByLabelText("Reject signal")).toBeInTheDocument();
  });

  it("COMPLETED: the drawer offers Edit, Reject and Validate on a pending next step", async () => {
    renderPage(dcActivity({ status: "COMPLETED" }));
    await openRow("Send the DPA");
    expect(screen.getByRole("button", { name: /\bEdit\b/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /close-circle Reject/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /check-circle Validate/ })).toBeInTheDocument();
  });

  it("COMPLETED: a rejected next step can be reopened", async () => {
    renderPage(dcActivity({ status: "COMPLETED" }));
    await openRow("Train Karim", "Rejected");
    expect(screen.getByRole("button", { name: /Reopen/ })).toBeInTheDocument();
  });

  it("CANCELLED: read-only — no part 4, no quick-create, no row action", () => {
    renderPage(dcActivity({ status: "CANCELLED" }));
    expect(screen.queryByRole("button", { name: "+ Add next step" })).not.toBeInTheDocument();
    expect(within(rowOf("Send the DPA")).queryByLabelText("Validate signal")).toBeNull();
    expect(within(rowOf("Send the DPA")).queryByLabelText("Reject signal")).toBeNull();
  });

  it("CANCELLED: the drawer offers no action, no Reopen", async () => {
    renderPage(dcActivity({ status: "CANCELLED" }));
    await openRow("Send the DPA");
    expect(screen.queryByRole("button", { name: /\bEdit\b/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /close-circle Reject/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /check-circle Validate/ })).not.toBeInTheDocument();
    cleanup();
    renderPage(dcActivity({ status: "CANCELLED" }));
    await openRow("Train Karim", "Rejected");
    expect(screen.queryByRole("button", { name: /Reopen/ })).not.toBeInTheDocument();
  });
});

// ==============================|| 5.4 — THE DETAIL VIEW ||============================== //

const ISABELLE = { id: "c-2", first_name: "Isabelle", last_name: "Roux", job_title: "CFO" };

const richPending = (over = {}) => nextStep({
  id: "ns-rich", suggested_title: "Send the DPA and SOC 2 report",
  suggested_activity_type: "EMAIL", suggested_activity_type_display: "Email",
  suggested_due_date: "2026-10-23", suggested_date_text: "before Friday",
  suggested_decision_step: "step-4",
  suggested_decision_step_detail: { id: "step-4", name: "Technical Fit", order: 4 },
  carried_by_prospect: false,
  suggested_people: [
    { id: "p-1", full_name: "Thomas Lefèvre", role: "CHAMPION", target_contact: THOMAS },
    { id: "p-2", full_name: "Karim Benali", role: "UNKNOWN", target_contact: null },
  ],
  suggested_people_names: ["Laurent"],
  suggested_internal_names: ["Sophie"],
  suggested_objective: "Unblock the security review",
  suggested_success_criterion: "The DSI signs off the DPA",
  suggested_topics: "DPA, SOC 2 scope",
  source_quote: "Envoyez-les avant vendredi.",
  metadata: { evidence_check: { status: "quote_not_found", detail: { parts: 1, parts_found: 0 } } },
  advice_rationale: "ADVICE-RATIONALE-NEVER-SHOWN",
  source_context: { activity: { id: "act-0" }, contacts: [THOMAS, ISABELLE] },
  ...over,
});

const bare = (over = {}) => nextStep({
  id: "ns-bare", suggested_title: "Follow up", suggested_activity_type: "TASK",
  suggested_due_date: null, suggested_date_text: "", suggested_decision_step: null,
  suggested_decision_step_detail: null, carried_by_prospect: false,
  suggested_people: [], suggested_people_names: [], suggested_internal_names: [],
  suggested_objective: "", suggested_success_criterion: "", suggested_topics: "",
  source_quote: "", metadata: {}, ...over,
});

const section = (testId) => screen.getByTestId(testId);

describe("Next steps band — the detail view (5.4)", () => {
  const openDetail = async (nextSteps, title, sectionName) => {
    renderPage(dcActivity(), nextSteps);
    if (sectionName) expand(sectionName);
    fireEvent.click(rowOf(title));
    return screen.findByTestId(DETAIL);
  };

  it("opens in the workspace coque, titled with the type, with its status pill", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    const coque = screen.getByTestId("coque-panel");
    expect(within(coque).getByTestId(DETAIL)).toBeInTheDocument();
    expect(within(coque).getByTestId("coque-title")).toHaveTextContent("Next step");
    expect(within(coque).getByText("Pending")).toBeInTheDocument();
  });

  it("① Proposal: title, type, date + the date as said, DC step, carried by", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    const proposal = section("next-step-proposal");
    expect(within(screen.getByTestId(DETAIL)).getByText("Send the DPA and SOC 2 report")).toBeInTheDocument();
    expect(within(proposal).getByText("Email")).toBeInTheDocument();
    expect(within(proposal).getByText("23 Oct 2026 · “before Friday”")).toBeInTheDocument();
    expect(within(proposal).getByText("Technical Fit")).toBeInTheDocument();
    expect(within(proposal).getByText("Seller")).toBeInTheDocument();
  });

  it("② Purpose: objective, success criterion, topics", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    const purpose = section("next-step-purpose");
    expect(within(purpose).getByText("Unblock the security review")).toBeInTheDocument();
    expect(within(purpose).getByText("The DSI signs off the DPA")).toBeInTheDocument();
    expect(within(purpose).getByText("DPA, SOC 2 scope")).toBeInTheDocument();
  });

  it("③ Source: quote, the 'quote not found' badge, participants, origin link", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    const source = section("next-step-source");
    expect(within(source).getByText(/Envoyez-les avant vendredi/)).toBeInTheDocument();
    expect(within(source).getByText("Quote not found in the transcript")).toBeInTheDocument();
    expect(within(source).getByText(/Isabelle/)).toBeInTheDocument();
    fireEvent.click(within(source).getByRole("button", { name: /View origin activity/ }));
    expect(mockPush).toHaveBeenCalledWith("/activities/act-0");
  });

  it("no badge for a faithful quote; no origin link when the origin is this activity", async () => {
    await openDetail([richPending({ metadata: {}, source_context: { activity: { id: "act-1" },
      contacts: [THOMAS] } })], "Send the DPA and SOC 2 report");
    const source = section("next-step-source");
    expect(within(source).queryByText("Quote not found in the transcript")).toBeNull();
    expect(within(source).queryByRole("button", { name: /View origin activity/ })).toBeNull();
  });

  it("'Unknown' in full for each empty field", async () => {
    await openDetail([bare()], "Follow up");
    expect(within(section("next-step-proposal")).getAllByText("Unknown")).toHaveLength(2); // date, step
    expect(within(section("next-step-purpose")).getAllByText("Unknown")).toHaveLength(3);
  });

  it("advice_rationale never appears", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    expect(screen.queryByText(/ADVICE-RATIONALE-NEVER-SHOWN/)).toBeNull();
  });

  it("a pending next step: Edit / Reject / Validate; Validate never calls validateSignal", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    expect(screen.getByRole("button", { name: /\bEdit\b/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /check-circle Validate/ }));
    expect(validateSignal).not.toHaveBeenCalled();
    // 5.6: the validation flow, step 1.
    expect(await screen.findByTestId("next-step-validate-flow")).toBeInTheDocument();
  });

  it("Reject from the detail calls rejectSignal", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    fireEvent.click(screen.getByRole("button", { name: /close-circle Reject/ }));
    await waitFor(() => expect(rejectSignal).toHaveBeenCalledWith("next-steps", "ns-rich"));
  });

  it("a resolved next step: ⑤ Activity links to it; no action at all (rule 2.1)", async () => {
    await openDetail([richPending({ status: "VALIDATED", linked_activity: compactActivity() })],
      "Send the DPA and SOC 2 report", "Validated");
    const activitySection = section("next-step-activity");
    fireEvent.click(within(activitySection)
      .getByRole("link", { name: "Open activity Security review" }));
    expect(mockPush).toHaveBeenCalledWith("/activities/act-20");
  });

  it("a resolved next step shows no Edit / Reject / Validate / Reopen", async () => {
    await openDetail([richPending({ status: "VALIDATED", attached_activity: compactActivity() })],
      "Send the DPA and SOC 2 report", "Validated");
    for (const name of [/\bEdit\b/, /close-circle Reject/, /check-circle Validate/, /Reopen/]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("a rejected next step: Reopen from the detail calls reopenSignal", async () => {
    await openDetail([richPending({ status: "REJECTED" })], "Send the DPA and SOC 2 report",
      "Rejected");
    fireEvent.click(screen.getByRole("button", { name: /Reopen/ }));
    await waitFor(() => expect(reopenSignal).toHaveBeenCalledWith("next-steps", "ns-rich"));
  });
});

// ==============================|| 5.5 — THE EDIT VIEW ||============================== //

const DC_PEOPLE = [
  { id: "p-1", full_name: "Thomas Lefèvre", status: "VALIDATED", target_contact: THOMAS },
  { id: "p-2", full_name: "Karim Benali", status: "PENDING", target_contact: null },
  { id: "p-3", full_name: "Laurent Dubois", status: "PENDING", target_contact: null },
  { id: "p-9", full_name: "Rejected Person", status: "REJECTED", target_contact: null },
];

describe("Next steps band — the edit view (5.5)", () => {
  const openEdit = async (ns = richPending()) => {
    mockDcPeople = DC_PEOPLE;
    mockPatchResponse = null;
    renderPage(dcActivity(), [ns]);
    fireEvent.click(rowOf(ns.suggested_title));
    await screen.findByTestId(DETAIL);
    fireEvent.click(screen.getByRole("button", { name: /\bEdit\b/ }));
    return screen.findByTestId("next-step-edit");
  };
  const save = async () => {
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(updateSignal).toHaveBeenCalled());
  };
  const payload = () => updateSignal.mock.calls[0][2];
  const editText = (name, text) => {
    fireEvent.click(screen.getByTestId(`inline-read-${name}`));
    fireEvent.change(screen.getByTestId(`inline-input-${name}`), { target: { value: text } });
  };
  const pick = (name, optionLabel) => {
    fireEvent.click(screen.getByTestId(`inline-read-${name}`));
    fireEvent.click(screen.getByRole("option", { name: optionLabel }));
  };

  it("Edit opens EditNextStepContent in the coque — not the legacy dialog", async () => {
    await openEdit();
    expect(within(screen.getByTestId("coque-panel")).getByTestId("coque-title"))
      .toHaveTextContent("Edit next step");
    expect(screen.queryByTestId("legacy-signal-edit-drawer")).not.toBeInTheDocument();
  });

  it("is pre-filled with the next step, in the detail's sections", async () => {
    const edit = await openEdit();
    for (const text of ["Send the DPA and SOC 2 report", "Email", "before Friday", "Technical Fit",
      "Seller", "Unblock the security review", "The DSI signs off the DPA", "DPA, SOC 2 scope"]) {
      expect(within(edit).getAllByText(text, { exact: false }).length).toBeGreaterThan(0);
    }
    expect(within(edit).queryByText(/ADVICE-RATIONALE/)).toBeNull();
  });

  it("Save is disabled while nothing changed", async () => {
    await openEdit();
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  it("PATCHes ONLY the changed field", async () => {
    await openEdit();
    editText("suggested_title", "Send the signed DPA");
    await save();
    expect(updateSignal).toHaveBeenCalledWith("next-steps", "ns-rich",
      { suggested_title: "Send the signed DPA" });
  });

  it("a required title cannot be emptied", async () => {
    await openEdit();
    editText("suggested_title", "  ");
    // Formik validates asynchronously.
    await waitFor(() => expect(screen.getByRole("button", { name: /save/i })).toBeDisabled());
    expect(updateSignal).not.toHaveBeenCalled();
  });

  it("the DC step is chosen among the steps of the cycle", async () => {
    await openEdit();
    expect(useGetDecisionStepsByCycle).toHaveBeenCalledWith("dc-1");
    pick("suggested_decision_step", "Business Case");
    await save();
    expect(payload()).toEqual({ suggested_decision_step: "step-5" });
  });

  // 5.8g (a) — the DC step: the cycle's steps only, never an "Unknown" choice.
  it("the DC step choices: the steps of the cycle only, in order, no 'Unknown'", async () => {
    // The cycle's steps as the server may send them (unordered).
    const original = useGetDecisionStepsByCycle.getMockImplementation();
    useGetDecisionStepsByCycle.mockImplementation(() => ({
      steps: [{ id: "step-5", name: "Business Case", order: 5 },
              { id: "step-4", name: "Technical Fit", order: 4 }],
      stepsLoading: false,
    }));
    try {
      await openEdit();
      fireEvent.click(screen.getByTestId("inline-read-suggested_decision_step"));
      expect(screen.getAllByRole("option").map((o) => o.textContent))
        .toEqual(["Technical Fit", "Business Case"]);
    } finally {
      useGetDecisionStepsByCycle.mockImplementation(original);
    }
  });

  it("carried by the prospect", async () => {
    await openEdit();
    pick("carried_by_prospect", "Prospect");
    await save();
    expect(payload()).toEqual({ carried_by_prospect: true });
  });

  it("no People picker, no 'Internal' in the edit", async () => {
    const edit = await openEdit();
    expect(useGetSignalsByAccount).not.toHaveBeenCalled();
    expect(within(edit).queryByTestId("pills-field-suggested_people")).toBeNull();
    expect(within(edit).queryByText("Internal")).toBeNull();
    expect(within(edit).queryByText("Sophie")).toBeNull();
  });

  it("long texts: objective, success criterion, topics", async () => {
    await openEdit();
    editText("suggested_success_criterion", "The DSI signs the DPA by Friday");
    await save();
    expect(payload()).toEqual({ suggested_success_criterion: "The DSI signs the DPA by Friday" });
  });

  it("after Save, back to the detail, updated", async () => {
    await openEdit();
    editText("suggested_title", "Send the signed DPA");
    await save();
    const detail = await screen.findByTestId(DETAIL);
    expect(within(detail).getByText("Send the signed DPA")).toBeInTheDocument();
  });

  it("Cancel returns to the detail without saving", async () => {
    await openEdit();
    editText("suggested_title", "Something else");
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    const detail = await screen.findByTestId(DETAIL);
    expect(within(detail).getByText("Send the DPA and SOC 2 report")).toBeInTheDocument();
    expect(updateSignal).not.toHaveBeenCalled();
  });
});

// ==============================|| 5.6 — THE VALIDATION FLOW, STEP 1 + CREATE ||============================== //

const CANDIDATE = { ...compactActivity({ id: "act-30", title: "Security review" }),
  decision_step: null, shared_people_count: 1, same_step: true, same_type: true,
  date_distance_days: 0, differences: {} };

describe("Next steps band — the validation flow, step 1 + Create (5.6)", () => {
  const FLOW = "next-step-validate-flow";
  const openFlowFromRow = async ({ candidates = [], activity = dcActivity() } = {}) => {
    mockCandidates = candidates;
    mockServerNextStep = richPending({ status: "VALIDATED",
      linked_activity: compactActivity({ id: "act-new", title: "Send the DPA" }) });
    renderPage(activity, [richPending()]);
    fireEvent.click(within(rowOf("Send the DPA and SOC 2 report")).getByLabelText("Validate signal"));
    return screen.findByTestId(FLOW);
  };
  const choose = (label) => fireEvent.click(screen.getByRole("radio", { name: label }));
  const next = () => fireEvent.click(screen.getByRole("button", { name: "Next" }));

  it("the row ✓ opens step 1 in the coque: stepper, Create or Link, Back / Next", async () => {
    const flow = await openFlowFromRow({ candidates: [CANDIDATE] });
    expect(within(screen.getByTestId("coque-panel")).getByTestId("coque-title"))
      .toHaveTextContent("Validate next step");
    expect(within(flow).getByText("How do you resolve this next step?")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Create the activity" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Link to an existing activity" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Back" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled(); // nothing chosen
    expect(useNextStepLinkCandidates).toHaveBeenCalledWith("ns-rich");
    expect(validateSignal).not.toHaveBeenCalled();
  });

  it("the detail's Validate opens step 1 too", async () => {
    mockCandidates = [];
    renderPage(dcActivity(), [richPending()]);
    fireEvent.click(rowOf("Send the DPA and SOC 2 report"));
    await screen.findByTestId(DETAIL);
    fireEvent.click(screen.getByRole("button", { name: /check-circle Validate/ }));
    expect(await screen.findByTestId(FLOW)).toBeInTheDocument();
  });

  it("Link is disabled, with a message, when there is no candidate", async () => {
    await openFlowFromRow({ candidates: [] });
    expect(screen.getByRole("radio", { name: "Link to an existing activity" })).toBeDisabled();
    expect(screen.getByText("No open activity in this cycle")).toBeInTheDocument();
  });

  it("Create → Next opens the creation IN THE COQUE, pre-filled from the next step (5.8d)", async () => {
    await openFlowFromRow();
    choose("Create the activity");
    next();
    const create = await screen.findByTestId("activity-create");
    expect(screen.queryByTestId("activity-modal")).not.toBeInTheDocument();
    expect(within(create).getByText("Send the DPA and SOC 2 report")).toBeInTheDocument();
  });

  it("on success, the detail re-opens VALIDATED and resolved, read back from the server", async () => {
    await openFlowFromRow();
    choose("Create the activity");
    next();
    await screen.findByTestId("activity-create");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    const detail = await screen.findByTestId(DETAIL);
    expect(getSignal).toHaveBeenCalledWith("next-steps", "ns-rich");
    expect(within(screen.getByTestId("coque-panel")).getByText("Validated")).toBeInTheDocument();
    expect(within(detail).getByTestId("next-step-activity")).toBeInTheDocument();
    expect(mockMutateList).toHaveBeenCalled(); // the list (and its 3rd line) is refreshed
    expect(validateSignal).not.toHaveBeenCalled();
  });

  it("cancelling the creation returns to step 1, nothing written", async () => {
    await openFlowFromRow();
    choose("Create the activity");
    next();
    await screen.findByTestId("activity-create");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await screen.findByTestId(FLOW)).toBeInTheDocument();
    expect(createActivity).not.toHaveBeenCalled();
    expect(getSignal).not.toHaveBeenCalled();
    expect(updateSignal).not.toHaveBeenCalled();
    expect(validateSignal).not.toHaveBeenCalled();
  });

  it("Back returns to the detail", async () => {
    await openFlowFromRow();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByTestId(DETAIL)).toBeInTheDocument();
  });

  it("Link can be chosen when there are candidates", async () => {
    await openFlowFromRow({ candidates: [CANDIDATE] });
    choose("Link to an existing activity");
    expect(screen.getByRole("radio", { name: "Link to an existing activity" })).toBeChecked();
    expect(screen.queryByTestId("activity-modal")).not.toBeInTheDocument();
  });

  it("COMPLETED: the flow is available; CANCELLED: no way in", async () => {
    await openFlowFromRow({ activity: dcActivity({ status: "COMPLETED" }) });
    cleanup();
    renderPage(dcActivity({ status: "CANCELLED" }), [richPending()]);
    expect(within(rowOf("Send the DPA and SOC 2 report")).queryByLabelText("Validate signal")).toBeNull();
    fireEvent.click(rowOf("Send the DPA and SOC 2 report"));
    await screen.findByTestId(DETAIL);
    expect(screen.queryByRole("button", { name: /check-circle Validate/ })).not.toBeInTheDocument();
  });
});

// ==============================|| 5.7 — THE LINK FLOW, STEPS 2 AND 3 ||============================== //

const FULL_DIFF = {
  activity_type: { current: "CALL", proposed: "MEETING" },
  date: { current: { field: "scheduled_date", value: "2026-10-28" },
          proposed: { field: "scheduled_date", value: "2026-11-03" } },
  decision_step: { current: { id: "step-4", name: "Technical Fit" },
                   proposed: { id: "step-5", name: "Business Case" } },
  call_to_action: { current: "Check the SSO", proposed: "Unblock the security review" },
  description: { current: "", proposed: "DPA, SOC 2 scope" },
  contacts: { to_add: [{ id: "c-9", first_name: "Laurent", last_name: "Dubois" }] },
};

const linkCandidate = (over = {}) => ({
  id: "act-31", title: "Call Thomas", activity_type: "CALL", activity_type_display: "Call",
  status: "PLANNED", status_display: "Planned", scheduled_date: "2026-10-28", due_date: null,
  decision_step: { id: "step-4", name: "Technical Fit" },
  shared_people_count: 2, same_step: true, same_type: true, date_distance_days: 0,
  differences: FULL_DIFF, ...over,
});

const CANDIDATES = [
  linkCandidate(),
  linkCandidate({ id: "act-32", title: "Pricing review", activity_type: "MEETING",
    decision_step: null, shared_people_count: 0, same_step: false, same_type: false,
    date_distance_days: 5, differences: {} }),
];

describe("Next steps band — the link flow, steps 2 and 3 (5.7)", () => {
  const FLOW = "next-step-validate-flow";
  const openStep2 = async (candidates = CANDIDATES) => {
    mockCandidates = candidates;
    mockAttachResult = { success: true, data: {} };
    mockServerNextStep = richPending({ status: "VALIDATED",
      attached_activity: compactActivity({ id: "act-31", title: "Call Thomas" }) });
    renderPage(dcActivity(), [richPending()]);
    fireEvent.click(within(rowOf("Send the DPA and SOC 2 report")).getByLabelText("Validate signal"));
    await screen.findByTestId(FLOW);
    fireEvent.click(screen.getByRole("radio", { name: "Link to an existing activity" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    return screen.findByTestId("link-candidates");
  };
  const openStep3 = async (candidates) => {
    await openStep2(candidates);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    return screen.findByTestId("link-differences");
  };
  const confirm = async () => {
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(attachNextStepToActivity).toHaveBeenCalled());
  };
  const sentUpdates = () => attachNextStepToActivity.mock.calls[0][2];

  it("step 2: the candidates in the SERVER order, the first 'Proposed' and pre-selected", async () => {
    const list = await openStep2();
    const rows = within(list).getAllByTestId(/^link-candidate-/);
    expect(rows.map((r) => r.dataset.testid)).toEqual(["link-candidate-act-31", "link-candidate-act-32"]);
    expect(within(rows[0]).getByText("Proposed")).toBeInTheDocument();
    expect(within(rows[1]).queryByText("Proposed")).toBeNull();
    expect(within(rows[0]).getByRole("radio")).toBeChecked();
    expect(within(rows[1]).getByRole("radio")).not.toBeChecked();
  });

  it("step 2: each candidate is the existing ActivityMiniCard + a readable 'Why'", async () => {
    const list = await openStep2();
    const [first, second] = within(list).getAllByTestId(/^link-candidate-/);
    expect(within(first).getByText("Call Thomas")).toBeInTheDocument();
    // The card's meta (5.9b: step · date, one line).
    expect(within(first).getByTestId("activity-mini-card-meta")).toHaveTextContent(/^Technical Fit · /);
    // 5.10b (3): only the criteria that match, then the date gap.
    expect(within(first).getByText(
      "Why: 2 people in common · Same step · Same type · Same day")).toBeInTheDocument();
    expect(within(second).getByText("Why: 5 days apart")).toBeInTheDocument();
  });

  // 5.10b (2) — the card in the drawer: the "drawer" layout of the SAME
  // ActivityMiniCard (forced by the Link step) — row 1 the type icon + the
  // FULL title (wraps, 2 lines max then ellipsis), row 2 step · date | the
  // status pill. The screen is wide: the screen-width breakpoint must not
  // put it back on one line (the title was cut to ~8 characters).
  const LONG_TITLE = "New tech stack evaluation with the security and procurement teams";
  const cssOf = () => Array.from(document.querySelectorAll("style")).map((x) => x.textContent || "").join("");
  const rulesOf = (el) => {
    const css = cssOf();
    return (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"))
      .map((c) => (css.match(new RegExp(`\\.${c}\\{[^}]*\\}`, "g")) || []).join("")).join("");
  };
  const mediaRulesOf = (el) => {
    const css = cssOf();
    return (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"))
      .map((c) => (css.match(new RegExp(`@media[^{]*\\{\\.${c}\\{[^}]*\\}`, "g")) || []).join("")).join("");
  };

  it("the Link step card: the FULL title on row 1, the meta on row 2", async () => {
    const list = await openStep2([{ ...CANDIDATES[0], title: LONG_TITLE }, CANDIDATES[1]]);
    const card = within(within(list).getAllByTestId(/^link-candidate-/)[0]).getByTestId("activity-mini-card");
    const title = within(card).getByText(LONG_TITLE);
    // The full title: wraps on 2 lines max, then ellipsis — never one cut line.
    const titleRules = rulesOf(title);
    expect(titleRules).toMatch(/-webkit-line-clamp:2/);
    expect(titleRules).not.toMatch(/white-space:nowrap/);
    // Two distinct rows, whatever the screen width.
    const row = within(card).getByTestId("activity-mini-card-row");
    expect(rulesOf(row)).toMatch(/flex-direction:column/);
    expect(mediaRulesOf(row)).not.toMatch(/flex-direction:row/);
    const main = within(card).getByTestId("activity-mini-card-main");
    const meta = within(card).getByTestId("activity-mini-card-meta");
    expect(main).toContainElement(title);
    expect(main.querySelector(".anticon")).not.toBeNull();
    expect(meta).not.toContainElement(title);
    expect(main.compareDocumentPosition(meta) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("the Link step card, row 2: step · date on the left, the status pill on the right", async () => {
    const list = await openStep2();
    const card = within(within(list).getAllByTestId(/^link-candidate-/)[0]).getByTestId("activity-mini-card");
    const meta = within(card).getByTestId("activity-mini-card-meta");
    expect(rulesOf(meta)).toMatch(/justify-content:space-between/);
    expect(meta.firstElementChild).toHaveTextContent(/^Technical Fit · /);
    expect(meta.lastElementChild).toHaveAttribute("data-testid", "status-pill");
  });

  it("the Link step card, row 2 without step nor date: the pill stays on the right", async () => {
    const list = await openStep2([{ ...CANDIDATES[0], decision_step: null, scheduled_date: null,
                                    due_date: null }, CANDIDATES[1]]);
    const card = within(within(list).getAllByTestId(/^link-candidate-/)[0]).getByTestId("activity-mini-card");
    const pill = within(within(card).getByTestId("activity-mini-card-meta")).getByTestId("status-pill");
    expect(rulesOf(pill)).toMatch(/margin-left:auto/);
  });

  // 5.10b (3) — PO decision A: the "Why" line shows ONLY the criteria that
  // match (« N people in common » when N > 0, « Same step », « Same type »),
  // then always the date gap (« 29 days apart », « Same day », nothing without
  // a date). No negative criterion any more.
  const whyCase = (id, over) => linkCandidate({ id, title: `Candidate ${id}`, shared_people_count: 0,
    same_step: false, same_type: false, date_distance_days: null, differences: {}, ...over });
  const whyOf = (list, id) => within(list).getByTestId(`link-candidate-${id}`);

  it("Why: only the matching criteria, then the date gap", async () => {
    const list = await openStep2([
      whyCase("w-neg", { date_distance_days: 8 }),
      whyCase("w-part", { same_step: true, date_distance_days: 29 }),
      whyCase("w-pos", { shared_people_count: 2, same_step: true, same_type: true, date_distance_days: 0 }),
      whyCase("w-one", { shared_people_count: 1, same_type: true, date_distance_days: 1 }),
    ]);
    expect(within(whyOf(list, "w-neg")).getByText("Why: 8 days apart")).toBeInTheDocument();
    expect(within(whyOf(list, "w-part")).getByText("Why: Same step · 29 days apart")).toBeInTheDocument();
    expect(within(whyOf(list, "w-pos")).getByText(
      "Why: 2 people in common · Same step · Same type · Same day")).toBeInTheDocument();
    expect(within(whyOf(list, "w-one")).getByText(
      "Why: 1 person in common · Same type · 1 day apart")).toBeInTheDocument();
  });

  it("Why: never a negative criterion", async () => {
    const list = await openStep2([whyCase("w-neg", { date_distance_days: 8 }), whyCase("w-pos2",
      { shared_people_count: 3, date_distance_days: 2 })]);
    expect(within(list).queryByText(/no people in common|other step|other type|no date/i)).toBeNull();
  });

  it("Why without a date: the matching criteria only; nothing matches → no Why line", async () => {
    const list = await openStep2([
      whyCase("w-nodate", { same_step: true, same_type: true }),
      whyCase("w-empty", {}),
    ]);
    expect(within(whyOf(list, "w-nodate")).getByText("Why: Same step · Same type")).toBeInTheDocument();
    expect(within(whyOf(list, "w-empty")).queryByText(/^Why:/)).toBeNull();
  });

  it("step 3: one section per difference", async () => {
    const diff = await openStep3();
    for (const key of ["activity_type", "date", "decision_step", "call_to_action", "description", "contacts"]) {
      expect(within(diff).getByTestId(`link-diff-${key}`)).toBeInTheDocument();
    }
    expect(within(diff).getByRole("radio", { name: "Keep: Phone Call" })).toBeChecked();
    expect(within(diff).getByRole("radio", { name: "Use proposed: Meeting" })).not.toBeChecked();
    expect(within(diff).getByRole("radio", { name: "Keep: 28 Oct 2026" })).toBeChecked();
    expect(within(diff).getByRole("radio", { name: "Keep: Technical Fit" })).toBeChecked();
    expect(within(diff).getByRole("checkbox", { name: "Append to the current objective" })).not.toBeChecked();
    expect(within(diff).getByRole("checkbox", { name: "Add Laurent Dubois" })).not.toBeChecked();
  });

  it("step 3: a section without difference is ABSENT", async () => {
    const diff = await openStep3([linkCandidate({ differences: {
      activity_type: { current: "CALL", proposed: "MEETING" } } })]);
    expect(within(diff).getByTestId("link-diff-activity_type")).toBeInTheDocument();
    for (const key of ["date", "decision_step", "call_to_action", "description", "contacts"]) {
      expect(within(diff).queryByTestId(`link-diff-${key}`)).toBeNull();
    }
  });

  it("updates EXACT — nothing changed: {}", async () => {
    await openStep3();
    await confirm();
    expect(attachNextStepToActivity).toHaveBeenCalledWith("ns-rich", "act-31", {});
  });

  it("updates EXACT — the proposed type taken", async () => {
    await openStep3();
    fireEvent.click(screen.getByRole("radio", { name: "Use proposed: Meeting" }));
    await confirm();
    expect(sentUpdates()).toEqual({ activity_type: "MEETING" });
  });

  it("updates EXACT — the proposed date and step taken", async () => {
    await openStep3();
    fireEvent.click(screen.getByRole("radio", { name: "Use proposed: 3 Nov 2026" }));
    fireEvent.click(screen.getByRole("radio", { name: "Use proposed: Business Case" }));
    await confirm();
    expect(sentUpdates()).toEqual({ scheduled_date: "2026-11-03", decision_step_id: "step-5" });
  });

  it("updates EXACT — a proposed DUE date goes to due_date (its own field)", async () => {
    await openStep3([linkCandidate({ activity_type: "TASK", differences: {
      date: { current: null, proposed: { field: "due_date", value: "2026-11-03" } } } })]);
    expect(screen.getByRole("radio", { name: "Keep: No date" })).toBeChecked();
    fireEvent.click(screen.getByRole("radio", { name: "Use proposed: 3 Nov 2026" }));
    await confirm();
    expect(sentUpdates()).toEqual({ due_date: "2026-11-03" });
  });

  it("updates EXACT — a text appended (edited) to the current one", async () => {
    await openStep3();
    fireEvent.change(screen.getByTestId("link-text-call_to_action"),
      { target: { value: "Unblock the security review with the DSI" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Append to the current objective" }));
    await confirm();
    expect(sentUpdates()).toEqual({
      call_to_action: "Check the SSO\n\nUnblock the security review with the DSI",
    });
  });

  it("updates EXACT — one contact checked", async () => {
    await openStep3();
    fireEvent.click(screen.getByRole("checkbox", { name: "Add Laurent Dubois" }));
    await confirm();
    expect(sentUpdates()).toEqual({ add_contact_ids: ["c-9"] });
  });

  it("a candidate without difference: Confirm directly from step 2", async () => {
    await openStep2();
    fireEvent.click(within(screen.getByTestId("link-candidate-act-32")).getByRole("radio"));
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
    await confirm();
    expect(attachNextStepToActivity).toHaveBeenCalledWith("ns-rich", "act-32", {});
  });

  it("after Confirm, the detail is read back VALIDATED, resolved by the LINKED activity", async () => {
    await openStep3();
    await confirm();
    const detail = await screen.findByTestId(DETAIL);
    expect(getSignal).toHaveBeenCalledWith("next-steps", "ns-rich");
    expect(within(screen.getByTestId("coque-panel")).getByText("Validated")).toBeInTheDocument();
    expect(within(detail).getByTestId("next-step-activity")).toHaveTextContent("Call Thomas");
    expect(mockMutateList).toHaveBeenCalled();
    expect(validateSignal).not.toHaveBeenCalled();
  });

  it("a server refusal: the standard error, we stay on the step, nothing lost", async () => {
    await openStep3();
    mockAttachResult = { success: false, status: 400, error: "COND-1" };
    fireEvent.click(screen.getByRole("radio", { name: "Use proposed: Meeting" }));
    await confirm();
    expect(displayErrorSnackbar).toHaveBeenCalledWith(mockAttachResult);
    expect(screen.getByTestId("link-differences")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Use proposed: Meeting" })).toBeChecked();
    expect(getSignal).not.toHaveBeenCalled();
  });

  it("Back from step 3 to step 2, then Next: nothing lost", async () => {
    await openStep3();
    fireEvent.click(screen.getByRole("radio", { name: "Use proposed: Meeting" }));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByTestId("link-candidates")).toBeInTheDocument();
    expect(within(screen.getByTestId("link-candidate-act-31")).getByRole("radio")).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("radio", { name: "Use proposed: Meeting" })).toBeChecked();
  });

  it("Back from step 2 returns to step 1", async () => {
    await openStep2();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByText("How do you resolve this next step?")).toBeInTheDocument();
  });
});

// ==============================|| 5.8g (c) — THE NAMES CITED, NOT SHOWN ||============================== //
//
// PO decision (5.8g, replaces the 5.8c display): the names a next step cites
// (its suggested_people + suggested_people_names) are NOT shown anywhere in
// the next step UI — no People section in the detail nor in the edit; line 2
// = type · date. The data stays in base (never sent by the edit); the contacts
// pre-fill of the creation (cited-contacts, 5.8d) is kept.

describe("Next steps band — the names cited are not shown (5.8g)", () => {
  const openRich = async (over = {}) => {
    renderPage(dcActivity(), [richPending(over)]);
    fireEvent.click(rowOf("Send the DPA and SOC 2 report"));
    return screen.findByTestId(DETAIL);
  };
  const badgeOf = (container, title) =>
    within(container).getByText(title).previousSibling?.textContent;

  it("the detail: no People section, no name cited", async () => {
    const detail = await openRich();
    expect(within(detail).queryByTestId("next-step-people")).toBeNull();
    expect(within(detail).queryByText("People")).toBeNull();
    for (const name of [/Karim Benali/, /^Laurent$/, /Thomas Lefèvre · Karim/]) {
      expect(within(detail).queryByText(name)).toBeNull();
    }
    expect(within(detail).queryByText("Internal")).toBeNull();
  });

  it("the detail sections: ① Proposal ② Purpose ③ Source", async () => {
    const detail = await openRich();
    expect(badgeOf(detail, "Proposal")).toBe("1");
    expect(badgeOf(detail, "Purpose")).toBe("2");
    expect(badgeOf(detail, "Source")).toBe("3");
  });

  it("the edit: no People section, no 'Names cited'; sections ① ② ③", async () => {
    await openRich();
    fireEvent.click(screen.getByRole("button", { name: /\bEdit\b/ }));
    const edit = await screen.findByTestId("next-step-edit");
    expect(within(edit).queryByTestId("pills-field-cited_names")).toBeNull();
    expect(within(edit).queryByText("People")).toBeNull();
    expect(within(edit).queryByText("Names cited")).toBeNull();
    expect(within(edit).queryByText("Karim Benali")).toBeNull();
    expect(badgeOf(edit, "Proposal")).toBe("1");
    expect(badgeOf(edit, "Purpose")).toBe("2");
    expect(badgeOf(edit, "Source")).toBe("3");
  });

  it("the data stays: the edit never sends suggested_people / suggested_people_names", async () => {
    await openRich();
    fireEvent.click(screen.getByRole("button", { name: /\bEdit\b/ }));
    await screen.findByTestId("next-step-edit");
    fireEvent.click(screen.getByTestId("inline-read-suggested_title"));
    fireEvent.change(screen.getByTestId("inline-input-suggested_title"), { target: { value: "Send the DPA" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(updateSignal).toHaveBeenCalled());
    expect(updateSignal.mock.calls[0][2]).toEqual({ suggested_title: "Send the DPA" });
  });
});


// ==============================|| 5.8d (3/3) — CREATION IN THE COQUE ||============================== //

const LAURENT_CONTACT = { id: "c-9", first_name: "Laurent", last_name: "Dubois", full_name: "Laurent Dubois" };

describe("Next steps band — the activity creation in the coque (5.8d)", () => {
  const CREATE = "activity-create";
  const DEFAULT_CITED = [
    { name: "Karim Benali", contact: null },
    { name: "Thomas Lefèvre", contact: THOMAS },
    { name: "Laurent", contact: LAURENT_CONTACT },
  ];
  const openCreateFromFlow = async (ns = richPending(), activity = dcActivity(), cited = DEFAULT_CITED) => {
    mockCandidates = [];
    mockCreateActivityResult = { success: true, data: { id: "act-new" } };
    mockServerNextStep = richPending({ status: "VALIDATED", linked_activity: compactActivity() });
    mockCited = cited;
    renderPage(activity, [ns]);
    fireEvent.click(within(rowOf(ns.suggested_title)).getByLabelText("Validate signal"));
    await screen.findByTestId("next-step-validate-flow");
    fireEvent.click(screen.getByRole("radio", { name: "Create the activity" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    return screen.findByTestId(CREATE);
  };
  const saveButton = () => screen.getByRole("button", { name: "Save" });

  it("titled 'New activity' in the coque; no ActivityModal", async () => {
    await openCreateFromFlow();
    expect(within(screen.getByTestId("coque-panel")).getByTestId("coque-title"))
      .toHaveTextContent("New activity");
    expect(screen.queryByTestId("activity-modal")).not.toBeInTheDocument();
  });

  it("pre-filled by activityDefaultsFromNextStep (+ the cited names' contacts, 'Mentioned')", async () => {
    const create = await openCreateFromFlow();
    expect(within(create).getByText("Send the DPA and SOC 2 report")).toBeInTheDocument();
    expect(within(create).getByText("Thomas Lefèvre")).toBeInTheDocument();
    expect(within(create).getByText("Laurent Dubois")).toBeInTheDocument();
    expect(within(create).getByTestId("mentioned-names")).toHaveTextContent("Mentioned: Karim Benali");
  });

  it("the DC is pre-filled from the context and modifiable; the step = the proposed one", async () => {
    const create = await openCreateFromFlow();
    expect(within(create).getByTestId("inline-read-decision_cycle")).toHaveTextContent("Deal Acme");
    expect(within(create).getByTestId("inline-read-decision_step")).toHaveTextContent("Technical Fit");
    fireEvent.click(within(create).getByTestId("inline-read-decision_cycle"));
    expect(screen.getByRole("option", { name: "Deal Other" })).toBeInTheDocument();
  });

  it("the owner = the user's NAME, read-only", async () => {
    const create = await openCreateFromFlow();
    expect(within(create).getByText("Yasmine Kawi")).toBeInTheDocument();
    expect(within(create).queryByTestId("remove-owner")).toBeNull();
    expect(within(create).queryByTestId("add-owner")).toBeNull();
  });

  // 5.8g (b) — the owner: « First Last » (bold, a name) + « · email » in the
  // muted suffix style; the word "owner" is gone (the caption says it).
  // 5.8h (2) — a REJECTED People is never used by the pre-fill: neither its
  // contact (target_contact) nor its name (the server's cited-contacts
  // already leaves it out).
  const REJECTED_THOMAS = { id: "p-1", full_name: "Thomas Lefèvre", role: "CHAMPION",
                            status: "REJECTED", target_contact: THOMAS };
  const KARIM = { id: "p-2", full_name: "Karim Benali", role: "UNKNOWN", status: "PENDING",
                  target_contact: null };
  const CITED_WITHOUT_REJECTED = [
    { name: "Karim Benali", contact: null },
    { name: "Laurent", contact: LAURENT_CONTACT },
  ];

  it("a REJECTED People: its contact is never pre-selected", async () => {
    const create = await openCreateFromFlow(
      richPending({ suggested_people: [REJECTED_THOMAS, KARIM] }), dcActivity(), CITED_WITHOUT_REJECTED,
    );
    expect(within(create).queryByText("Thomas Lefèvre")).toBeNull();
    expect(within(create).getByText("Laurent Dubois")).toBeInTheDocument();
  });

  it("a REJECTED People: its name never reaches the description", async () => {
    const create = await openCreateFromFlow(
      richPending({ suggested_activity_type: "TASK", suggested_people: [REJECTED_THOMAS, KARIM] }),
      dcActivity(), CITED_WITHOUT_REJECTED,
    );
    const description = within(create).getByTestId("inline-read-description");
    expect(description).toHaveTextContent("Mentioned: Karim Benali, Laurent");
    expect(description.textContent).not.toMatch(/Thomas/);
  });

  // 5.8h (3) — the PO rule, symmetric: contacts — from a People's
  // target_contact or from a name — ONLY for MEETING / CALL / EMAIL; the other
  // types get the names in the description, no contact.
  it("another type (TASK): no contact pre-selected, even a People's target_contact", async () => {
    const create = await openCreateFromFlow(richPending({ suggested_activity_type: "TASK" }));
    const people = within(create).getByTestId("people-section");
    expect(within(people).queryByText("Thomas Lefèvre")).toBeNull();
    expect(within(people).queryByText("Laurent Dubois")).toBeNull();
    expect(within(create).getByTestId("inline-read-description"))
      .toHaveTextContent("Mentioned: Thomas Lefèvre, Karim Benali, Laurent");
  });

  it("MEETING / CALL / EMAIL: the People's contact and the matched names, as before", async () => {
    // Isabelle: a People's target_contact the server's cited-contacts does
    // NOT return — only the People link brings her.
    const create = await openCreateFromFlow(richPending({
      suggested_activity_type: "CALL",
      suggested_people: [{ id: "p-4", full_name: "Isabelle Roux", role: "CHAMPION",
                           status: "PENDING", target_contact: ISABELLE }],
    }));
    const people = within(create).getByTestId("people-section");
    expect(within(people).getByText("Isabelle Roux")).toBeInTheDocument();
    expect(within(people).getByText("Laurent Dubois")).toBeInTheDocument();
  });

  it("the owner reads 'First Last · email', never '· owner'", async () => {
    const create = await openCreateFromFlow();
    const owner = within(create).getByTestId("activity-owner");
    expect(owner).toHaveTextContent("Activity ownerYasmine Kawi · yasmine@acme.test");
    expect(owner.textContent).not.toMatch(/· owner/);
    const name = within(owner).getByText("Yasmine Kawi");
    // PersonRow's name: bold (sx "bold" → the theme's bold weight).
    expect(name.closest("p")).toHaveStyle({ fontWeight: testTheme.typography.fontWeightBold });
    const suffix = within(owner).getByText(/yasmine@acme\.test/);
    expect(suffix).toHaveStyle({ color: testTheme.aphoriQ.text.muted });
  });

  // 5.9b (2) — the owner label, from the REAL auth user shape: « First Last ·
  // email »; the email ONCE when the name is truly missing.
  it("the real auth user: « First Last · email », never the email twice", async () => {
    const create = await openCreateFromFlow();
    const owner = within(create).getByTestId("activity-owner");
    expect(within(owner).getByText("Yasmine Kawi").closest("p").textContent)
      .toBe("Yasmine Kawi · yasmine@acme.test");
  });

  it("a user truly without a name: the email once", async () => {
    mockAuthUser = { ...AUTH_USER, name: "", first_name: "", last_name: "" };
    try {
      const create = await openCreateFromFlow();
      const owner = within(create).getByTestId("activity-owner");
      expect(within(owner).getByText(/yasmine@acme\.test/).closest("p").textContent)
        .toBe("yasmine@acme.test");
    } finally {
      mockAuthUser = AUTH_USER;
    }
  });

  // 5.8g (b) — "+ Add contact" / "+ New contact": the standard gap between
  // actions (the drawer's actions: theme spacing 1), never stuck together.
  it("'+ Add contact' and '+ New contact' sit apart with the standard gap", async () => {
    const create = await openCreateFromFlow();
    const add = within(create).getByTestId("add-contact");
    const inline = within(create).getByTestId("add-inline-contact");
    const row = within(create).getByTestId("contact-add-actions");
    expect(row).toContainElement(add);
    expect(row).toContainElement(inline);
    expect(row).toHaveStyle({ display: "flex", gap: testTheme.spacing(1) });
  });

  it("Save is enabled at once (a valid pre-fill) and creates with the EXACT payload", async () => {
    await openCreateFromFlow();
    expect(saveButton()).toBeEnabled();
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivity).toHaveBeenCalledTimes(1));
    expect(createActivity.mock.calls[0][0]).toEqual({
      title: "Send the DPA and SOC 2 report",
      activity_type: "EMAIL",
      status: "PLANNED",
      description: "DPA, SOC 2 scope\n\nInternal: Sophie",
      call_to_action: "Unblock the security review\n\nSuccess criterion: The DSI signs off the DPA",
      scheduled_date: null,
      scheduled_time: null,
      due_date: "2026-10-23",
      contact_ids: ["c-1", "c-9"],
      invited_user_ids: [],
      account_id: "acc-1",
      decision_cycle_id: "dc-1",
      decision_step_id: "step-4",
      next_step_signal_id: "ns-rich",
    });
    expect(createActivityWithEntities).not.toHaveBeenCalled();
  });

  it("a contact created on the fly goes through create-with-entities", async () => {
    const create = await openCreateFromFlow();
    fireEvent.click(within(create).getByTestId("add-inline-contact"));
    fireEvent.click(screen.getByRole("button", { name: "save inline contact" }));
    fireEvent.click(saveButton());
    await waitFor(() => expect(createActivityWithEntities).toHaveBeenCalledTimes(1));
    const body = createActivityWithEntities.mock.calls[0][0];
    expect(body.inline_contact).toEqual({ first_name: "Isabelle", last_name: "Roux" });
    expect(body.inline_cycle).toBeNull();
    expect(body.activity.next_step_signal_id).toBe("ns-rich");
    expect(createActivity).not.toHaveBeenCalled();
  });

  it("Save is disabled only by an invalid form (title emptied)", async () => {
    const create = await openCreateFromFlow();
    fireEvent.click(within(create).getByTestId("inline-read-title"));
    fireEvent.change(within(create).getByTestId("inline-input-title"), { target: { value: " " } });
    await waitFor(() => expect(saveButton()).toBeDisabled());
  });

  it("a server refusal: the standard error, the form stays", async () => {
    await openCreateFromFlow();
    mockCreateActivityResult = { success: false, status: 400, error: "nope" };
    fireEvent.click(saveButton());
    await waitFor(() => expect(displayErrorSnackbar).toHaveBeenCalledWith(mockCreateActivityResult));
    expect(screen.getByTestId(CREATE)).toBeInTheDocument();
    expect(getSignal).not.toHaveBeenCalled();
  });

  // 5.13 (PO): no modal any more — the creation in the coque, conversion
  // mode (a NEW cycle only; end to end: StartDecisionCyclePage). 5.16: from
  // « + Add next step »'s type row.
  it("'+ Add next step' → a type, no DC born: the creation in the coque, conversion mode; no ActivityModal", () => {
    renderPage(dcActivity({ decision_cycle: null, campaign_detail: { id: "camp-1" },
      outcome: "SUCCESSFUL" }));
    fireEvent.click(screen.getByRole("button", { name: "+ Add next step" }));
    fireEvent.click(within(screen.getByTestId("add-next-step-types")).getByRole("button", { name: "Meeting" }));
    expect(screen.queryByTestId("activity-modal")).not.toBeInTheDocument();
    const create = screen.getByTestId("activity-create");
    expect(within(create).getByTestId("conversion-cycle")).toBeInTheDocument();
  });

});


// ==============================|| 5.8e (1) — NO RE-INITIALISATION AFTER MOUNT ||============================== //
//
// The creation drawer shows its form only once its default values are ready
// (the cited-contacts read included) — the existing drawer loading indicator
// meanwhile — and never re-initialises after the mount: a typing is never lost.

describe("Next steps band — the creation form waits for its defaults (5.8e)", () => {
  const openCreateDelayed = async () => {
    mockCandidates = [];
    mockCitedDelayMs = 150;
    mockCited = [{ name: "Laurent", contact: LAURENT_CONTACT }];
    renderPage(dcActivity(), [richPending()]);
    fireEvent.click(within(rowOf("Send the DPA and SOC 2 report")).getByLabelText("Validate signal"));
    await screen.findByTestId("next-step-validate-flow");
    fireEvent.click(screen.getByRole("radio", { name: "Create the activity" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
  };

  it("while cited-contacts is pending: the loading indicator, no form", async () => {
    await openCreateDelayed();
    expect(screen.getByTestId("activity-create-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("activity-create")).toBeNull();
    const create = await screen.findByTestId("activity-create", {}, { timeout: 1000 });
    expect(within(create).getByText("Laurent Dubois")).toBeInTheDocument();
  });

  it("a typing is never overwritten by the late response", async () => {
    await openCreateDelayed();
    // Type as soon as a title field exists.
    fireEvent.click(await screen.findByTestId("inline-read-title", {}, { timeout: 1000 }));
    fireEvent.change(screen.getByTestId("inline-input-title"), { target: { value: "My own title" } });
    // Well past the response.
    await new Promise((r) => setTimeout(r, 300));
    expect(screen.getByTestId("inline-input-title")).toHaveValue("My own title");
  });
});


// ==============================|| 5.8e — "+ ADD NEXT STEP" ||============================== //

describe("Next steps band — '+ Add next step' (5.8e)", () => {
  const TYPES = ["Phone Call", "Email", "Meeting", "Demo", "Task", "LinkedIn", "Other"];

  // 5.12e (4) (PO): on the right of the BAND's title (its header).
  it("a pill in the band header, right of the 'Next steps' title", () => {
    renderPage();
    const pill = screen.getByRole("button", { name: "+ Add next step" });
    expect(pill).toHaveAttribute("data-testid", "status-pill");
    expect(pill.closest("[aria-expanded]")).toBe(screen.getByText("Next steps").closest("[aria-expanded]"));
  });

  it("no quick-create chips any more", () => {
    renderPage();
    // (the chips' accessible name carries their icon: "plus Meeting")
    for (const label of ["Meeting", "Call", "Email", "Task"]) {
      expect(screen.queryByRole("button", { name: new RegExp(label) })).toBeNull();
    }
  });

  it("a click: a row of the 7 ActivityType pills, in the constant's order", () => {
    renderPage();
    expect(screen.queryByTestId("add-next-step-types")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "+ Add next step" }));
    const row = screen.getByTestId("add-next-step-types");
    const pills = within(row).getAllByRole("button");
    expect(pills.map((p) => p.textContent)).toEqual(TYPES);
    pills.forEach((p) => expect(p).toHaveAttribute("data-testid", "status-pill"));
  });

  it("a type pill → the creation drawer with that type", async () => {
    renderPage();
    addNextStep("Demo");
    const create = await screen.findByTestId("activity-create");
    expect(within(create).getByTestId("inline-read-type")).toHaveTextContent("Demo");
    expect(within(screen.getByTestId("coque-panel")).getByTestId("coque-title"))
      .toHaveTextContent("New activity");
  });

  it("the same clickable pill as the scope pills of the surface", () => {
    renderPage();
    const pill = screen.getByRole("button", { name: "+ Add next step" });
    expect(pill).toHaveAttribute("tabindex", "0");
    expect(pill).toHaveAttribute("data-testid", "status-pill");
  });

  it("the scope pills' colours: '+ Add next step' active, the type pills inactive", () => {
    renderPage();
    const add = screen.getByRole("button", { name: "+ Add next step" });
    expect(add).toHaveStyle({ color: testTheme.palette.primary.main });
    fireEvent.click(add);
    within(screen.getByTestId("add-next-step-types")).getAllByRole("button")
      .forEach((p) => expect(p).toHaveStyle({ color: testTheme.palette.text.secondary }));
  });

  it("keyboard: Enter opens the type row, Space on a type opens the creation", async () => {
    renderPage();
    fireEvent.keyDown(screen.getByRole("button", { name: "+ Add next step" }), { key: "Enter" });
    fireEvent.keyDown(within(screen.getByTestId("add-next-step-types"))
      .getByRole("button", { name: "Task" }), { key: " " });
    const create = await screen.findByTestId("activity-create");
    expect(within(create).getByTestId("inline-read-type")).toHaveTextContent("Task");
  });

  it("a type pick closes the type row", async () => {
    renderPage();
    addNextStep("Email");
    await screen.findByTestId("activity-create");
    expect(screen.queryByTestId("add-next-step-types")).toBeNull();
  });

  it("5.16: a campaign activity still in sequence: absent; a CANCELLED activity: hidden", () => {
    renderPage(dcActivity({ decision_cycle: null, campaign_detail: { id: "camp-1" }, outcome: "NO_ANSWER" }));
    expect(screen.queryByRole("button", { name: "+ Add next step" })).toBeNull();
    cleanup();
    renderPage(dcActivity({ status: "CANCELLED" }));
    expect(screen.queryByRole("button", { name: "+ Add next step" })).toBeNull();
  });
});
