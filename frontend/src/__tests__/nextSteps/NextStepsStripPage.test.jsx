// frontend/src/__tests__/nextSteps/NextStepsStripPage.test.jsx
//
// Sprint Next steps 5.2 — the Activity workspace PAGE as really rendered
// (views/activities/workspace/index.jsx): the band is "Next steps"; its part 1
// is the ONE next planned step (activity.next_planned_step, backend 5.1) shown
// with the existing ActivityMiniCard (click → the activity, status pill — ON_HOLD
// visible), "In decision cycle <name>" when the step comes from a DC born from
// the activity, an explicit empty state when there is none; no client re-sort
// (sequence_context.next_activities is not listed any more); "Start Decision
// Cycle" hidden once a DC was born. The band, ActivityNextStepsTab,
// UpcomingActivitiesSection and ActivityMiniCard are REAL; data hooks and the
// other bands are mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup } from "@testing-library/react";
import AphoriqTheme from "../_utils/aphoriqTheme";

const mockPush = vi.fn();
let mockActivity;

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
vi.mock("api/signals/aggregatedSignals", () => ({ default: () => ({ signals: [] }) }));
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
// The rest of the Next steps band (parts 2-4 come in 5.3).
vi.mock("hooks/useActivityAllSignals", () => ({
  default: () => ({ nextStepSignals: [], allSignals: [], loading: false, error: null, mutateAll: vi.fn() }),
}));
vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: () => ({ choices: {}, choicesLoading: false }),
  rejectSignal: vi.fn(),
}));
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: ({ open }) => (open ? <div data-testid="activity-modal" /> : null),
}));
vi.mock("components/signals/SignalEditDrawer", () => ({ default: () => null }));
vi.mock("sections/activities/nextSteps/NextStepSuggestionDrawer", () => ({ default: () => null }));

import ActivityWorkspacePage from "views/activities/workspace";

const render = (ui) => rtlRender(<AphoriqTheme>{ui}</AphoriqTheme>);

const planned = (over = {}) => ({
  id: "act-9", title: "Security review", activity_type: "MEETING", status: "PLANNED",
  is_overdue: false, outcome: null, scheduled_date: "2026-11-03", due_date: null,
  decision_step_name: "Technical Fit", ...over,
});

const dcActivity = (nextPlannedStep, over = {}) => ({
  id: "act-1", title: "Atelier", activity_type: "MEETING", status: "PLANNED",
  account: "acc-1", decision_cycle: "dc-1", campaign_detail: null,
  sequence_context: {
    position: 1, total: 3,
    // Would be re-sorted / listed by the old section: must NOT be rendered.
    next_activities: [planned({ id: "undated", title: "Undated task", scheduled_date: null }),
                      planned({ id: "other", title: "Other open activity" })],
  },
  next_planned_step: nextPlannedStep, ...over,
});

afterEach(() => { cleanup(); mockPush.mockReset(); });

describe("Next steps band — part 1, the next planned step (5.2)", () => {
  it("the band is called 'Next steps'", () => {
    mockActivity = dcActivity(null);
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("Next steps")).toBeInTheDocument();
    expect(screen.queryByText("Next step")).not.toBeInTheDocument();
  });

  it("shows ONLY the next planned step — no client re-sort / list — and opens it on click", () => {
    mockActivity = dcActivity({ source: "DECISION_CYCLE", decision_cycle: { id: "dc-1", name: "Deal Acme" },
                                activity: planned() });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("Next planned step")).toBeInTheDocument();
    expect(screen.getByText("Security review")).toBeInTheDocument();
    expect(screen.queryByText("Undated task")).not.toBeInTheDocument();
    expect(screen.queryByText("Other open activity")).not.toBeInTheDocument();
    expect(screen.queryByText(/In decision cycle/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Security review"));
    expect(mockPush).toHaveBeenCalledWith("/activities/act-9");
  });

  it("an ON_HOLD next step shows its status pill", () => {
    mockActivity = dcActivity({ source: "CAMPAIGN", decision_cycle: null,
                                activity: planned({ status: "ON_HOLD" }) });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("On hold")).toBeInTheDocument();
  });

  it("a step from a DC born from the activity says 'In decision cycle <name>' and hides Start Decision Cycle", () => {
    mockActivity = dcActivity(
      { source: "BORN_DECISION_CYCLE", decision_cycle: { id: "dc-7", name: "Deal Logistix" },
        activity: planned({ title: "Send pricing" }) },
      { decision_cycle: null, campaign_detail: { id: "camp-1" }, outcome: "SUCCESSFUL", status: "PLANNED" },
    );
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("In decision cycle Deal Logistix")).toBeInTheDocument();
    expect(screen.getByText("Send pricing")).toBeInTheDocument();
    expect(screen.queryByText("Start Decision Cycle")).not.toBeInTheDocument();
  });

  it("a born DC with nothing open: the DC is named, an explicit empty state, no Start Decision Cycle", () => {
    mockActivity = dcActivity(
      { source: "BORN_DECISION_CYCLE", decision_cycle: { id: "dc-7", name: "Deal Logistix" }, activity: null },
      { decision_cycle: null, campaign_detail: { id: "camp-1" }, outcome: "SUCCESSFUL", status: "PLANNED" },
    );
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("In decision cycle Deal Logistix")).toBeInTheDocument();
    expect(screen.getByText("No activity planned in this decision cycle yet.")).toBeInTheDocument();
    expect(screen.queryByText("Start Decision Cycle")).not.toBeInTheDocument();
  });

  it("a successful campaign call with no DC born keeps Start Decision Cycle", () => {
    mockActivity = dcActivity(null, {
      decision_cycle: null, campaign_detail: { id: "camp-1" }, outcome: "SUCCESSFUL", status: "PLANNED",
    });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("Start Decision Cycle")).toBeInTheDocument();
  });

  it("nothing planned: an explicit empty state", () => {
    mockActivity = dcActivity(null);
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("No next step planned yet.")).toBeInTheDocument();
    expect(screen.queryByText("Security review")).not.toBeInTheDocument();
  });
});
