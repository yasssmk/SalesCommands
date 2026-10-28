// frontend/src/__tests__/nextSteps/NextStepsStripPage.test.jsx
//
// Sprint Next steps 5.2 — the Activity workspace PAGE as really rendered
// (views/activities/workspace/index.jsx): the band is "Next steps"; "Start
// Decision Cycle" hidden once a DC was born. 5.12 B: the next planned step
// (activity.next_planned_step) left the band for Context (5.12 A-bis) — the
// band shows no title, card or empty state for it any more. The shared
// ActivityMiniCard's row layout (5.9b) is tested on the card itself. The
// band and ActivityNextStepsTab are REAL; data hooks and the other bands are
// mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within } from "@testing-library/react";
import AphoriqTheme, { testTheme } from "../_utils/aphoriqTheme";

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
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));

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
vi.mock("api/signals/signals", () => ({
  useGetSignalChoices: () => ({ choices: {}, choicesLoading: false }),
  rejectSignal: vi.fn(),
}));
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: ({ open }) => (open ? <div data-testid="activity-modal" /> : null),
}));
vi.mock("components/signals/SignalEditDrawer", () => ({ default: () => null }));

// The extraction (the shared Run AI action, 5.12 B) is out of scope here —
// covered by NextStepsBandLayoutPage.
vi.mock("sections/activities/workspace/RunAIAnalysisButton", () => ({ default: () => null }));

import ActivityWorkspacePage from "views/activities/workspace";
import ActivityMiniCard from "components/cards/activities/ActivityMiniCard";

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

  // 5.12 B (PO) — the next planned step left the band for Context (A-bis):
  // no title, no card, no empty state, no « In decision cycle » here.
  it("5.12 B: the band shows no next planned step any more (it is in Context)", () => {
    mockActivity = dcActivity({ source: "DECISION_CYCLE", decision_cycle: { id: "dc-1", name: "Deal Acme" },
                                activity: planned() });
    render(<ActivityWorkspacePage />);
    expect(screen.queryByText("Next planned step")).not.toBeInTheDocument();
    expect(screen.queryByText("Security review")).not.toBeInTheDocument();
    expect(screen.queryByTestId("activity-mini-card")).not.toBeInTheDocument();
    expect(screen.queryByText("No next step planned yet.")).not.toBeInTheDocument();
  });

  it("a campaign activity whose DC was born: no Start Decision Cycle (no band at all, 5.12 B)", () => {
    mockActivity = dcActivity(
      { source: "BORN_DECISION_CYCLE", decision_cycle: { id: "dc-7", name: "Deal Logistix" },
        activity: planned({ title: "Send pricing" }) },
      { decision_cycle: null, campaign_detail: { id: "camp-1" }, outcome: "SUCCESSFUL", status: "PLANNED" },
    );
    render(<ActivityWorkspacePage />);
    expect(screen.queryByText("Start Decision Cycle")).not.toBeInTheDocument();
    expect(screen.queryByText(/In decision cycle/)).not.toBeInTheDocument();
  });

  it("a successful campaign call with no DC born keeps Start Decision Cycle", () => {
    mockActivity = dcActivity(null, {
      decision_cycle: null, campaign_detail: { id: "camp-1" }, outcome: "SUCCESSFUL", status: "PLANNED",
    });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("Start Decision Cycle")).toBeInTheDocument();
  });
});

// ==============================|| 5.9b (3) — THE SHARED CARD ||============================== //
//
// PO: the shared ActivityMiniCard (components/cards/activities) — the type
// ICON (getActivityTypeIcon, ACTIVITY_TYPE_ICON_COLOR) replaces the type chip;
// the icon + title, then step · date · status pill (the shared StatusPill).
// 5.12 B: the band no longer shows it — the card is rendered directly.
// 5.12c (6): the one-line "row" layout is removed (no consumer left) — the
// card is the "drawer" layout only (its rows: NextStepsBandParts, Link step).

const styleText = () => Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
const classesOf = (el) => (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));

describe("The shared activity card — the type icon (5.9b), drawer layout only (5.12c)", () => {
  const renderCard = (over = {}) => {
    render(<ActivityMiniCard activity={planned({ activity_type: "CALL", ...over })} onNavigate={mockPush} />);
    return screen.getByTestId("activity-mini-card");
  };

  it("the type icon replaces the type chip", () => {
    const card = renderCard();
    expect(card.querySelector(".anticon-phone")).not.toBeNull();
    expect(within(card).queryByText("Phone Call")).toBeNull();
    expect(card.querySelector(".MuiChip-root")).toBeNull();
  });

  it("left: icon + title; right: step · date · status pill", () => {
    const card = renderCard();
    const left = within(card).getByTestId("activity-mini-card-main");
    const right = within(card).getByTestId("activity-mini-card-meta");
    expect(left.querySelector(".anticon-phone")).not.toBeNull();
    expect(left).toHaveTextContent("Security review");
    expect(right.textContent).toBe("Technical Fit · 3 Nov 2026Planned");
    expect(within(right).getByTestId("status-pill")).toHaveTextContent("Planned");
  });

  // 5.12c (6) — no "row" layout any more: two rows whatever the screen width
  // (no md breakpoint turning it into one line), the full title (no noWrap).
  it("no one-line layout: always two rows, the full title", () => {
    const card = renderCard();
    const row = within(card).getByTestId("activity-mini-card-row");
    const css = styleText();
    classesOf(row).forEach((c) => {
      expect(css).not.toMatch(new RegExp(`@media \\(min-width:900px\\)\\{\\.${c}\\{[^}]*flex-direction:row`));
    });
    expect(row).toHaveStyle({ flexDirection: "column" });
    expect(within(card).getByText("Security review")).not.toHaveClass("MuiTypography-noWrap");
  });

  it("an overdue activity: the 'Overdue' pill", () => {
    const card = renderCard({ is_overdue: true });
    expect(within(within(card).getByTestId("activity-mini-card-meta")).getByTestId("status-pill"))
      .toHaveTextContent("Overdue");
  });

  it("no step, no date: the status pill alone on the right", () => {
    const card = renderCard({ decision_step_name: null, scheduled_date: null });
    expect(within(card).getByTestId("activity-mini-card-meta").textContent).toBe("Planned");
  });

  // 5.10b (4) — PO: the « from AI » chip is REMOVED (the provenance lives in
  // Context, « From next step »).
  it("an activity born from a next step: no « from AI » chip", () => {
    const card = renderCard({ next_step_signal: "ns-1" });
    expect(within(card).queryByText(/from AI/i)).toBeNull();
    expect(card.querySelector(".MuiChip-root")).toBeNull();
    expect(card.querySelector(".anticon-robot")).toBeNull();
  });

  it("a click → onNavigate with the activity id", () => {
    fireEvent.click(renderCard());
    expect(mockPush).toHaveBeenCalledWith("act-9");
  });

  it("an ON_HOLD activity shows its status pill", () => {
    const card = renderCard({ status: "ON_HOLD" });
    expect(within(card).getByTestId("status-pill")).toHaveTextContent("On hold");
  });

  it("the type icon carries the type colour token", () => {
    const card = renderCard();
    const icon = within(card).getByTestId("activity-mini-card-type-icon");
    expect(icon).toHaveStyle({ color: testTheme.palette.primary.main });
  });
});
