// frontend/src/__tests__/nextSteps/NextStepsBandParts.test.jsx
//
// Sprint Next steps 5.3 — parts 2 to 4 of the "Next steps" band, on the Activity
// workspace PAGE as really rendered (views/activities/workspace/index.jsx):
//   part 2 "To validate" — the generic SignalsValidationList filtered on
//     next-steps (useAggregatedSignals), SignalLine lines 1-2 IDENTICAL to the
//     other types; the row ✓ validates NOTHING (it opens the detail drawer until
//     the flow lands in 5.6); ✗ = the existing rejectSignal;
//   part 3 — Validated = RESOLVED next steps, with SignalLine's generic optional
//     3rd line `extra` (→ title · type · date · status pill of the activity
//     created OR linked; click → the activity); Rejected in the signal format,
//     Reopen offered except on a resolved next step (rule 2.1);
//   part 4 — "Set a next step manually" (was "Add manually") → ActivityModal;
//   outside a DC (DC-only guard) parts 2-3 are hidden, parts 1 and 4 stay.
// 5.4 — the next step DETAIL opens in the single workspace coque (as the 8 other
// types), on the standard chassis (NextStepDetailView, section B of 5.0):
// ① Proposal ② People ③ Purpose ④ Source (+ quote badge) ⑤ Activity when
// resolved; "Unknown" in full for an empty field; advice_rationale never shown;
// a resolved next step is read-only (rule 2.1).
// The band, ActivityNextStepsTab, SignalsValidationList, SignalLine, the coque
// and the detail are REAL; data hooks, API calls and the other bands are mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";

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
vi.mock("api/signals/aggregatedSignals", () => ({
  default: (args) => ({
    signals: (args?.signalTypes || []).includes("next-steps") ? mockNextSteps : [],
    loading: false, error: null, mutate: vi.fn(),
  }),
}));
// The former data source of the band (before 5.3) — same next steps, so a
// failure here is about behaviour, not about a missing fetch.
vi.mock("hooks/useActivityAllSignals", () => ({
  default: () => ({ nextStepSignals: mockNextSteps, allSignals: mockNextSteps, loading: false,
                    error: null, mutateAll: vi.fn() }),
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
}));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionStepsByCycle: vi.fn(() => ({
    steps: [
      { id: "step-4", name: "Technical Fit", order: 4 },
      { id: "step-5", name: "Business Case", order: 5 },
    ],
    stepsLoading: false,
  })),
}));
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: ({ open }) => (open ? <div data-testid="activity-modal" /> : null),
}));
vi.mock("components/signals/SignalEditDrawer", () => ({
  default: ({ open }) => (open ? <div data-testid="legacy-signal-edit-drawer" /> : null),
}));

import ActivityWorkspacePage from "views/activities/workspace";
import SignalsValidationList from "components/signals/SignalsValidationList";
import {
  validateSignal, rejectSignal, reopenSignal, updateSignal, useGetSignalsByAccount,
} from "api/signals/signals";
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

const rowOf = (title) => screen.getByText(title).closest('[data-testid="signal-line"]');
const expand = (section) => fireEvent.click(screen.getByText(section));

const renderPage = (activity = dcActivity(), nextSteps = NEXT_STEPS) => {
  mockActivity = activity;
  mockNextSteps = nextSteps;
  return render(<ActivityWorkspacePage />);
};

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("Next steps band — part 2, to validate (5.3)", () => {
  it("lists the pending next steps in the generic validation list", () => {
    renderPage();
    expect(screen.getByText("To validate")).toBeInTheDocument();
    expect(rowOf("Send the DPA")).toBeInTheDocument();
    // AISuggestionCard / NextStepsFilterBar are gone from the band.
    expect(screen.queryByText("Convert to Activity")).not.toBeInTheDocument();
    expect(screen.queryByText("AI Suggestions")).not.toBeInTheDocument();
  });

  it("lines 1-2 are IDENTICAL to another type's row in the validation list", () => {
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
    expect(nextStepRow.outerHTML).toBe(painRow.outerHTML);
  });

  it("the row ✓ never validates: it opens the detail drawer", async () => {
    renderPage();
    fireEvent.click(within(rowOf("Send the DPA")).getByLabelText("Validate signal"));
    expect(await screen.findByTestId(DETAIL)).toBeInTheDocument();
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
  it("'Set a next step manually' (renamed) opens the ActivityModal", () => {
    renderPage();
    expect(screen.queryByText("Add manually")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Set a next step manually/ }));
    expect(screen.getByTestId("activity-modal")).toBeInTheDocument();
  });

  it("outside a DC: parts 2-3 hidden, parts 1 and 4 stay", () => {
    renderPage(dcActivity({ decision_cycle: null, campaign_detail: { id: "camp-1" } }));
    expect(screen.queryByText("To validate")).not.toBeInTheDocument();
    expect(screen.queryByText("Send the DPA")).not.toBeInTheDocument();
    expect(screen.getByText("Next planned step")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Set a next step manually/ })).toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: /Set a next step manually/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Meeting/ })).toBeInTheDocument();
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
    expect(screen.queryByRole("button", { name: /Set a next step manually/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Meeting/ })).not.toBeInTheDocument();
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

  it("② People: the People (contact or name), the names not linked, the internal names", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    const people = section("next-step-people");
    expect(within(people).getByText("Thomas Lefèvre")).toBeInTheDocument();
    expect(within(people).getByText(/Karim Benali/)).toBeInTheDocument();
    expect(within(people).getByText(/Laurent/)).toBeInTheDocument();
    expect(within(people).getByText("Sophie")).toBeInTheDocument();
  });

  it("③ Purpose: objective, success criterion, topics", async () => {
    await openDetail([richPending()], "Send the DPA and SOC 2 report");
    const purpose = section("next-step-purpose");
    expect(within(purpose).getByText("Unblock the security review")).toBeInTheDocument();
    expect(within(purpose).getByText("The DSI signs off the DPA")).toBeInTheDocument();
    expect(within(purpose).getByText("DPA, SOC 2 scope")).toBeInTheDocument();
  });

  it("④ Source: quote, the 'quote not found' badge, participants, origin link", async () => {
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
    expect(within(section("next-step-people")).getAllByText("Unknown")).toHaveLength(2); // prospect, internal
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
    // Until the validation flow (5.6): the existing Create path, ActivityModal.
    expect(screen.getByTestId("activity-modal")).toBeInTheDocument();
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
      "Seller", "Thomas Lefèvre", "Karim Benali", "Laurent", "Sophie",
      "Unblock the security review", "The DSI signs off the DPA", "DPA, SOC 2 scope"]) {
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

  it("carried by the prospect", async () => {
    await openEdit();
    pick("carried_by_prospect", "Prospect");
    await save();
    expect(payload()).toEqual({ carried_by_prospect: true });
  });

  it("People: picked among the DC People that are not rejected", async () => {
    await openEdit();
    expect(useGetSignalsByAccount).toHaveBeenCalledWith("acc-1", "people",
      expect.objectContaining({ filters: { decision_cycle_id: "dc-1" } }));
    fireEvent.click(screen.getByTestId("add-suggested_people"));
    fireEvent.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.queryByRole("option", { name: "Rejected Person" })).toBeNull();
    expect(screen.queryByRole("option", { name: "Thomas Lefèvre" })).toBeNull(); // already chosen
    fireEvent.click(screen.getByRole("option", { name: "Laurent Dubois" }));
    fireEvent.click(screen.getByTestId("confirm-add-suggested_people"));
    fireEvent.click(screen.getByTestId("remove-suggested_people-p-2"));
    await save();
    expect(payload()).toEqual({ suggested_people: ["p-1", "p-3"] });
  });

  it("names not linked / internal names are pills", async () => {
    await openEdit();
    fireEvent.click(screen.getByTestId("remove-suggested_people_names-Laurent"));
    fireEvent.click(screen.getByTestId("add-suggested_internal_names"));
    fireEvent.change(screen.getByTestId("input-add-suggested_internal_names"),
      { target: { value: "Marc" } });
    fireEvent.click(screen.getByTestId("confirm-add-suggested_internal_names"));
    await save();
    expect(payload()).toEqual({ suggested_people_names: [], suggested_internal_names: ["Sophie", "Marc"] });
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
