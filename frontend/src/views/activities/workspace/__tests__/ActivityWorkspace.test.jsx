// frontend/src/views/activities/workspace/__tests__/ActivityWorkspace.test.jsx

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";
import { useRouter, useSearchParams, useParams } from "next/navigation";

// ==============================|| MOCKS ||============================== //

// Mock next/font/google — Public_Sans is not available in jsdom.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

// Mock API hooks — SWR hooks mocked at import level per convention.
vi.mock("api/accounts/activities", () => ({
  useGetActivity: vi.fn(),
  updateActivity: vi.fn(),
  ACTIVITY_TYPE_LABELS: { CALL: "Phone Call" },
  ACTIVITY_STATUS_LABELS: { PLANNED: "Planned" },
  ACTIVITY_STATUS_COLORS: { PLANNED: "default" },
  ACTIVITY_OUTCOME_LABELS: {},
  ACTIVITY_OUTCOME_COLORS: {},
}));

// Mock ActivityHeader hook — returns the shape consumed by WorkspaceLayout.
vi.mock("sections/activities/workspace/ActivityHeader", () => ({
  default: vi.fn(() => ({
    avatar: null,
    title: "Test Activity",
    onTitleSave: undefined,
    titleDisabled: false,
    headerActions: null,
    chips: [],
    infoItems: [],
    modals: null,
  })),
}));

// Mock WorkspaceBreadcrumb — avoid pulling its full dependency tree.
vi.mock("components/WorkspaceBreadcrumb", () => ({
  __esModule: true,
  default: () => null,
  buildActivityBreadcrumbs: () => [],
}));

// Mock displayError utils
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// Mock lastRun hook
vi.mock("api/aiPipelines/lastRun", () => ({
  useGetLastExtractionRun: vi.fn(() => ({
    lastRun: null,
    runsByPipeline: { TRANSCRIPT_SIGNALS: null, NEXT_STEPS: null },
    mutateLastRun: vi.fn(),
  })),
}));

// Mock signal counts hook
vi.mock("api/signals/signalCounts", () => ({
  useActivitySignalCounts: vi.fn(() => ({
    counts: null,
    countsLoading: false,
    countsError: null,
    mutateCounts: vi.fn(),
  })),
}));

// Mock usePipelineRunner
vi.mock("hooks/usePipelineRunner", () => ({
  default: vi.fn(() => ({
    run: vi.fn(),
    state: 'idle',
    result: null,
    error: null,
    reset: vi.fn(),
  })),
  PIPELINE_STATE: {
    IDLE: 'idle',
    RUNNING: 'running',
    SUCCESS: 'success',
    PARTIAL: 'partial',
    ERROR: 'error',
  },
}));

// Mock tab components — avoids pulling heavy dependency trees (MUI date
// pickers, async selects, decision cycle hooks) that cause ESM resolution
// errors in jsdom. Each mock renders a marker div so we can assert which
// tab content is active.
vi.mock("sections/activities/workspace/ActivityOverviewTab", () => ({
  default: () => <div data-testid="tab-overview">Overview Content</div>,
}));
vi.mock("sections/activities/workspace/ActivityPreparationTab", () => ({
  default: () => <div data-testid="tab-preparation">Preparation Content</div>,
}));
vi.mock("sections/activities/workspace/ActivityNotesTab", () => ({
  default: () => <div data-testid="tab-notes">Coming in Sprint F2</div>,
}));
vi.mock("sections/activities/workspace/ActivitySignalsTab", () => ({
  default: () => <div data-testid="tab-signals">Coming in Sprint F5</div>,
}));
vi.mock("sections/activities/workspace/ActivityNextStepsTab", () => ({
  default: () => <div data-testid="tab-next-steps">Coming in Sprint F6</div>,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { useGetActivity } from "api/accounts/activities";
import { useActivitySignalCounts } from "api/signals/signalCounts";
import usePipelineRunner from "hooks/usePipelineRunner";
import useActivityHeaderProps from "sections/activities/workspace/ActivityHeader";
import ActivityWorkspacePage from "views/activities/workspace";

// ==============================|| TEST DATA ||============================== //

const mockActivity = {
  id: "act-123",
  title: "Discovery Call",
  status: "PLANNED",
  activity_type: "CALL",
  account: "acc-456",
  account_detail: { id: "acc-456", company_name: "Acme Corp" },
  decision_cycle: null,
  decision_step: null,
  decision_cycle_detail: null,
  decision_step_detail: null,
  campaign_detail: null,
  transcript: null,
  description: null,
  call_to_action: null,
  outcome: null,
  outcome_notes: null,
  owner_detail: null,
  invited_users_detail: [],
  contacts_detail: [],
  sequence_context: null,
};

// The "Next Steps" tab is a DC-ONLY feature: it is only visible when the
// activity has a decision_cycle. Tests that assert the tab (or its badge)
// is present use this DC-bearing variant.
const mockActivityWithCycle = {
  ...mockActivity,
  decision_cycle: "dc-1",
  decision_cycle_detail: { id: "dc-1", name: "Test Cycle" },
};

// ==============================|| HELPERS ||============================== //

const mockPush = vi.fn();

function setupRouter(tabParam = "") {
  vi.mocked(useParams).mockReturnValue({ id: "act-123" });
  vi.mocked(useRouter).mockReturnValue({
    push: mockPush,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  });
  vi.mocked(useSearchParams).mockReturnValue(
    new URLSearchParams(tabParam ? `tab=${tabParam}` : ""),
  );
}

function setupActivity(overrides = {}) {
  vi.mocked(useGetActivity).mockReturnValue({
    activity: mockActivity,
    activityLoading: false,
    activityError: null,
    activityValidating: false,
    mutateActivity: vi.fn(),
    ...overrides,
  });
}

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("ActivityWorkspacePage", () => {
  // ------------------------------------------------------------------
  // 1. Render OK — all 5 tabs visible
  // ------------------------------------------------------------------
  it("renders all 5 tabs in happy path", () => {
    setupRouter("overview");
    // Next Steps is DC-only, so the all-5-tabs happy path is a DC context.
    setupActivity({ activity: mockActivityWithCycle });

    render(<ActivityWorkspacePage />);

    // MUI scrollable Tabs may duplicate tab DOM nodes for measurement.
    // Use getAllBy and verify at least one exists for each label.
    const tabLabels = ["Overview", "Preparation", "Notes", "Signals", "Next Steps"];
    tabLabels.forEach((label) => {
      expect(screen.getAllByText(label).length).toBeGreaterThanOrEqual(1);
    });
  });

  // ------------------------------------------------------------------
  // 2. Loading state
  // ------------------------------------------------------------------
  it("shows loading spinner when activity is loading", () => {
    setupRouter("overview");
    setupActivity({ activity: null, activityLoading: true });

    render(<ActivityWorkspacePage />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // 3. Error state — generic (500)
  // ------------------------------------------------------------------
  it("shows generic error with Retry button", () => {
    setupRouter("overview");
    setupActivity({
      activity: null,
      activityError: { response: { status: 500 } },
    });

    render(<ActivityWorkspacePage />);

    expect(screen.getAllByText("Failed to load activity").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Retry").length).toBeGreaterThanOrEqual(1);
  });

  // ------------------------------------------------------------------
  // 4. Error state — 404
  // ------------------------------------------------------------------
  it("shows 404 error with Activity not found message", () => {
    setupRouter("overview");
    setupActivity({
      activity: null,
      activityError: { response: { status: 404 } },
    });

    render(<ActivityWorkspacePage />);

    expect(screen.getAllByText("Activity not found").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Go Back").length).toBeGreaterThanOrEqual(1);
  });

  // ------------------------------------------------------------------
  // 5. Tab navigation — URL update on click
  // ------------------------------------------------------------------
  it("updates URL when a tab is clicked", () => {
    setupRouter("overview");
    setupActivity();

    render(<ActivityWorkspacePage />);

    // MUI scrollable Tabs may render duplicate tab nodes. Target via
    // the visible tablist to get the interactive tab.
    const tablist = screen.getAllByRole("tablist")[0];
    const notesTab = within(tablist).getAllByRole("tab").find(
      (tab) => tab.textContent.includes("Notes"),
    );
    fireEvent.click(notesTab);

    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("tab=notes"),
      expect.anything(),
    );
  });

  // ------------------------------------------------------------------
  // 6. Placeholder rendering — Notes
  // ------------------------------------------------------------------
  it("renders Notes placeholder when tab=notes", () => {
    setupRouter("notes");
    setupActivity();

    render(<ActivityWorkspacePage />);

    expect(screen.getByTestId("tab-notes")).toBeInTheDocument();
    expect(screen.getByTestId("tab-notes")).toHaveTextContent("Coming in Sprint F2");
  });

  // ------------------------------------------------------------------
  // 7. Placeholder rendering — Signals
  // ------------------------------------------------------------------
  it("renders Signals placeholder when tab=signals", () => {
    setupRouter("signals");
    setupActivity();

    render(<ActivityWorkspacePage />);

    expect(screen.getByTestId("tab-signals")).toBeInTheDocument();
    expect(screen.getByTestId("tab-signals")).toHaveTextContent("Coming in Sprint F5");
  });

  // ------------------------------------------------------------------
  // 8. Placeholder rendering — Next Steps
  // ------------------------------------------------------------------
  it("renders Next Steps placeholder when tab=next-steps", () => {
    setupRouter("next-steps");
    setupActivity();

    render(<ActivityWorkspacePage />);

    expect(screen.getByTestId("tab-next-steps")).toBeInTheDocument();
    expect(screen.getByTestId("tab-next-steps")).toHaveTextContent("Coming in Sprint F6");
  });

  // ------------------------------------------------------------------
  // 9. Default tab fallback — no tab param → overview
  // ------------------------------------------------------------------
  it("falls back to overview tab when no tab param in URL", () => {
    setupRouter("");
    setupActivity();

    render(<ActivityWorkspacePage />);

    // Verify overview is the selected tab via aria-selected on visible tabs
    const tablist = screen.getAllByRole("tablist")[0];
    const overviewTab = within(tablist).getAllByRole("tab").find(
      (tab) => tab.textContent.includes("Overview"),
    );
    expect(overviewTab).toHaveAttribute("aria-selected", "true");
    // And the overview content is rendered
    expect(screen.getByTestId("tab-overview")).toBeInTheDocument();
  });

  // ------------------------------------------------------------------
  // F4: Tab badges — pending counts appear on Signals and Next Steps
  // ------------------------------------------------------------------
  it("shows badge on Signals tab when pending signals exist", () => {
    setupRouter("overview");
    setupActivity();
    vi.mocked(useActivitySignalCounts).mockReturnValue({
      counts: {
        pending: 5,
        validated: 2,
        rejected: 1,
        by_type: {
          pain: { pending: 2, validated: 1, rejected: 0 },
          objective: { pending: 1, validated: 0, rejected: 0 },
          impact: { pending: 1, validated: 1, rejected: 0 },
          tech_stack: { pending: 0, validated: 0, rejected: 1 },
          blocker: { pending: 1, validated: 0, rejected: 0 },
          next_step: { pending: 0, validated: 0, rejected: 0 },
        },
      },
      countsLoading: false,
      countsError: null,
      mutateCounts: vi.fn(),
    });

    render(<ActivityWorkspacePage />);

    const tablist = screen.getAllByRole("tablist")[0];
    const signalsTab = within(tablist).getAllByRole("tab").find(
      (tab) => tab.textContent.includes("Signals"),
    );
    expect(signalsTab.textContent).toContain("5");
  });

  it("shows badge on Next Steps tab when pending next steps exist", () => {
    setupRouter("overview");
    // The Next Steps tab only shows in a DC context.
    setupActivity({ activity: mockActivityWithCycle });
    vi.mocked(useActivitySignalCounts).mockReturnValue({
      counts: {
        pending: 3,
        validated: 0,
        rejected: 0,
        by_type: {
          pain: { pending: 0, validated: 0, rejected: 0 },
          objective: { pending: 0, validated: 0, rejected: 0 },
          impact: { pending: 0, validated: 0, rejected: 0 },
          tech_stack: { pending: 0, validated: 0, rejected: 0 },
          blocker: { pending: 0, validated: 0, rejected: 0 },
          next_step: { pending: 3, validated: 0, rejected: 0 },
        },
      },
      countsLoading: false,
      countsError: null,
      mutateCounts: vi.fn(),
    });

    render(<ActivityWorkspacePage />);

    const tablist = screen.getAllByRole("tablist")[0];
    const nextStepsTab = within(tablist).getAllByRole("tab").find(
      (tab) => tab.textContent.includes("Next Steps"),
    );
    expect(nextStepsTab.textContent).toContain("3");
  });

  it("does not show badge when no pending signals", () => {
    setupRouter("overview");
    setupActivity();
    vi.mocked(useActivitySignalCounts).mockReturnValue({
      counts: {
        pending: 0,
        validated: 5,
        rejected: 2,
        by_type: {
          pain: { pending: 0, validated: 2, rejected: 0 },
          objective: { pending: 0, validated: 1, rejected: 0 },
          impact: { pending: 0, validated: 1, rejected: 1 },
          tech_stack: { pending: 0, validated: 1, rejected: 1 },
          blocker: { pending: 0, validated: 0, rejected: 0 },
          next_step: { pending: 0, validated: 0, rejected: 0 },
        },
      },
      countsLoading: false,
      countsError: null,
      mutateCounts: vi.fn(),
    });

    render(<ActivityWorkspacePage />);

    const tablist = screen.getAllByRole("tablist")[0];
    const signalsTab = within(tablist).getAllByRole("tab").find(
      (tab) => tab.textContent.includes("Signals"),
    );
    expect(signalsTab.textContent).toBe("Signals");
  });

  // ------------------------------------------------------------------
  // F4: Header props include pipelineState and counts
  // ------------------------------------------------------------------
  it("passes pipelineState and counts to header hook", () => {
    setupRouter("overview");
    setupActivity();
    vi.mocked(usePipelineRunner).mockReturnValue({
      run: vi.fn(),
      state: 'running',
      result: null,
      error: null,
      reset: vi.fn(),
    });
    vi.mocked(useActivitySignalCounts).mockReturnValue({
      counts: { pending: 2, validated: 0, rejected: 0, by_type: {} },
      countsLoading: false,
      countsError: null,
      mutateCounts: vi.fn(),
    });

    render(<ActivityWorkspacePage />);

    expect(vi.mocked(useActivityHeaderProps)).toHaveBeenCalledWith(
      expect.objectContaining({
        pipelineState: 'running',
        counts: expect.objectContaining({ pending: 2 }),
      }),
    );
  });

  // ------------------------------------------------------------------
  // F4: Pending click navigates to signals tab
  // ------------------------------------------------------------------
  it("passes onPendingClick that navigates to signals tab", () => {
    setupRouter("overview");
    setupActivity();

    render(<ActivityWorkspacePage />);

    const headerCall = vi.mocked(useActivityHeaderProps).mock.calls[0][0];
    expect(headerCall.onPendingClick).toBeInstanceOf(Function);

    headerCall.onPendingClick();
    expect(mockPush).toHaveBeenCalledWith(
      expect.stringContaining("tab=signals"),
      expect.anything(),
    );
  });
});
