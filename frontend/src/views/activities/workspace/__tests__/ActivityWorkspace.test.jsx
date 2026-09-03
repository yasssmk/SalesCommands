// frontend/src/views/activities/workspace/__tests__/ActivityWorkspace.test.jsx
//
// UX Activity S1 — the Activity workspace is a TAB-LESS stacked body:
//   [Context fixed] · Preparation? · Source · Signals · Next step
// The four lower sections are CollapsibleStrip bands (interim content = the
// former tab components). Preparation is conditional on activity_type; default
// open state is a SPOTLIGHT driven by analysis (Boolean(lastRun)).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { useRouter, useSearchParams, useParams } from "next/navigation";

// ==============================|| MOCKS ||============================== //

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

// emotionCache uses next/navigation's useServerInsertedHTML — stub to passthrough
// so the page can render under the REAL ThemeCustomization (needed for the
// aphoriQ tokens the CollapsibleStrip bands consume).
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

vi.mock("api/accounts/activities", () => ({
  useGetActivity: vi.fn(),
  updateActivity: vi.fn(),
  ACTIVITY_TYPE_LABELS: { CALL: "Phone Call" },
  ACTIVITY_STATUS_LABELS: { PLANNED: "Planned" },
  ACTIVITY_STATUS_COLORS: { PLANNED: "default" },
  ACTIVITY_OUTCOME_LABELS: {},
  ACTIVITY_OUTCOME_COLORS: {},
}));

// ActivityHeader hook — returns the shape consumed by WorkspaceLayout.
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

vi.mock("components/WorkspaceBreadcrumb", () => ({
  __esModule: true,
  default: () => null,
  buildActivityBreadcrumbs: () => [],
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

vi.mock("api/aiPipelines/lastRun", () => ({
  useGetLastExtractionRun: vi.fn(() => ({
    lastRun: null,
    latestRun: null,
    runsByPipeline: { TRANSCRIPT_SIGNALS: null, NEXT_STEPS: null },
    mutateLastRun: vi.fn(),
  })),
}));

vi.mock("api/signals/signalCounts", () => ({
  useActivitySignalCounts: vi.fn(() => ({
    counts: null,
    countsLoading: false,
    countsError: null,
    mutateCounts: vi.fn(),
  })),
}));

vi.mock("hooks/usePipelineRunner", () => ({
  default: vi.fn(() => ({
    run: vi.fn(),
    state: "idle",
    result: null,
    error: null,
    reset: vi.fn(),
  })),
  PIPELINE_STATE: {
    IDLE: "idle",
    RUNNING: "running",
    SUCCESS: "success",
    PARTIAL: "partial",
    ERROR: "error",
  },
}));

// Interim section components — marker divs so we can assert which band body is
// mounted (a CollapsibleStrip unmounts its body while collapsed).
vi.mock("sections/activities/workspace/ActivityOverviewTab", () => ({
  default: () => <div data-testid="body-context">Context Content</div>,
}));
vi.mock("sections/activities/workspace/ActivityPreparationTab", () => ({
  default: () => <div data-testid="body-preparation">Preparation Content</div>,
}));
vi.mock("sections/activities/workspace/ActivityNotesTab", () => ({
  default: () => <div data-testid="body-source">Source Content</div>,
}));
vi.mock("sections/activities/workspace/ActivitySignalsTab", () => ({
  default: () => <div data-testid="body-signals">Signals Content</div>,
}));
vi.mock("sections/activities/workspace/ActivityNextStepsTab", () => ({
  default: () => <div data-testid="body-next-steps">Next Steps Content</div>,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { useGetActivity } from "api/accounts/activities";
import { useGetLastExtractionRun } from "api/aiPipelines/lastRun";
import ThemeCustomization from "themes/index";
import ActivityWorkspacePage from "views/activities/workspace";

// The page consumes theme.aphoriQ (via CollapsibleStrip) → render under the
// real theme provider.
function renderPage() {
  return render(
    <ThemeCustomization>
      <ActivityWorkspacePage />
    </ThemeCustomization>,
  );
}

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

// ==============================|| HELPERS ||============================== //

const mockPush = vi.fn();

function setupRouter() {
  vi.mocked(useParams).mockReturnValue({ id: "act-123" });
  vi.mocked(useRouter).mockReturnValue({
    push: mockPush,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  });
  vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams(""));
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

function setActivityType(activity_type) {
  setupActivity({ activity: { ...mockActivity, activity_type } });
}

function setAnalyzed(isAnalyzed) {
  vi.mocked(useGetLastExtractionRun).mockReturnValue({
    lastRun: isAnalyzed
      ? { last_run_at: "2026-06-03T14:32:00Z", status: "SUCCESS" }
      : null,
    latestRun: null,
    runsByPipeline: { TRANSCRIPT_SIGNALS: null, NEXT_STEPS: null },
    mutateLastRun: vi.fn(),
  });
}

// Ordered list of the visible band header titles (the strip headers are the
// only role="button" nodes once the tab bar is gone and the header is stubbed).
function bandTitlesInOrder() {
  return screen
    .getAllByRole("button")
    .map((b) => b.textContent.trim())
    .filter((t) => ["Preparation", "Source", "Signals", "Next step"].includes(t));
}

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("ActivityWorkspacePage — tab-less stacked body", () => {
  it("renders NO tab bar", () => {
    setupRouter();
    setupActivity();
    renderPage();
    expect(screen.queryAllByRole("tablist")).toHaveLength(0);
  });

  it("always renders the fixed Context block", () => {
    setupRouter();
    setupActivity();
    renderPage();
    expect(screen.getByTestId("body-context")).toBeInTheDocument();
  });

  it("renders the four bands in fixed order for an eligible type (CALL)", () => {
    setupRouter();
    setActivityType("CALL");
    renderPage();
    expect(bandTitlesInOrder()).toEqual([
      "Preparation",
      "Source",
      "Signals",
      "Next step",
    ]);
  });

  it("omits the Preparation band when type is not CALL/MEETING/DEMO (EMAIL)", () => {
    setupRouter();
    setActivityType("EMAIL");
    renderPage();
    expect(bandTitlesInOrder()).toEqual(["Source", "Signals", "Next step"]);
    expect(screen.queryByText("Preparation")).not.toBeInTheDocument();
  });

  it("keeps the Preparation band for MEETING and DEMO", () => {
    setupRouter();
    setActivityType("MEETING");
    const { unmount } = renderPage();
    expect(screen.getByText("Preparation")).toBeInTheDocument();
    unmount();

    setActivityType("DEMO");
    renderPage();
    expect(screen.getByText("Preparation")).toBeInTheDocument();
  });

  it("NOT analysed (no lastRun): Preparation open; Source/Signals/Next step closed", () => {
    setupRouter();
    setActivityType("CALL");
    setAnalyzed(false);
    renderPage();

    expect(screen.getByTestId("body-preparation")).toBeInTheDocument();
    expect(screen.queryByTestId("body-source")).not.toBeInTheDocument();
    expect(screen.queryByTestId("body-signals")).not.toBeInTheDocument();
    expect(screen.queryByTestId("body-next-steps")).not.toBeInTheDocument();
  });

  it("analysed (lastRun present): Signals + Next step open; Preparation/Source closed", () => {
    setupRouter();
    setActivityType("CALL");
    setAnalyzed(true);
    renderPage();

    expect(screen.getByTestId("body-signals")).toBeInTheDocument();
    expect(screen.getByTestId("body-next-steps")).toBeInTheDocument();
    expect(screen.queryByTestId("body-preparation")).not.toBeInTheDocument();
    expect(screen.queryByTestId("body-source")).not.toBeInTheDocument();
  });

  // --- states unrelated to tabs, preserved ---

  it("shows loading spinner when activity is loading", () => {
    setupRouter();
    setupActivity({ activity: null, activityLoading: true });
    renderPage();
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
  });

  it("shows 404 error with Activity not found message", () => {
    setupRouter();
    setupActivity({ activity: null, activityError: { response: { status: 404 } } });
    renderPage();
    expect(screen.getAllByText("Activity not found").length).toBeGreaterThanOrEqual(1);
  });
});
