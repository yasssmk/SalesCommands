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
// The band, ActivityNextStepsTab, SignalsValidationList, SignalLine and the next
// step drawer are REAL; data hooks, API calls and the other bands are mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import AphoriqTheme from "../_utils/aphoriqTheme";

const mockPush = vi.fn();
let mockActivity;
let mockNextSteps;

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: mockPush }),
}));
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
vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: () => ({ choices: {}, choicesLoading: false }),
  validateSignal: vi.fn(async () => ({ success: true })),
  rejectSignal: vi.fn(async () => ({ success: true })),
  reopenSignal: vi.fn(async () => ({ success: true })),
}));
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: ({ open }) => (open ? <div data-testid="activity-modal" /> : null),
}));
vi.mock("components/signals/SignalEditDrawer", () => ({ default: () => null }));

import ActivityWorkspacePage from "views/activities/workspace";
import SignalsValidationList from "components/signals/SignalsValidationList";
import { validateSignal, rejectSignal, reopenSignal } from "api/signals/signals";

const render = (ui) => rtlRender(<AphoriqTheme>{ui}</AphoriqTheme>);

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
  // PLANNED: a COMPLETED / CANCELLED activity is read-only (page isLocked).
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
    expect(await screen.findByText("AI Suggestion")).toBeInTheDocument();
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
    expect(screen.queryByText("AI Suggestion")).not.toBeInTheDocument();
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
    expect(await screen.findByText("AI Suggestion")).toBeInTheDocument();
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
