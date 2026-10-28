// frontend/src/__tests__/nextSteps/NextStepsBandLayoutPage.test.jsx
//
// Sprint Next steps 5.12 B (PO) — the Next steps band, on the Activity
// workspace PAGE as really rendered (views/activities/workspace/index.jsx):
//   * order: the conversion block (when it applies) → the next steps sections
//     (SignalsValidationList: To validate / Validated / Rejected) → the
//     extraction → « + Add next step » (+ its type row);
//   * the "Next planned step" sub-block is gone (title, card, empty states) —
//     it lives in Context (5.12 A-bis);
//   * the extraction: the SHARED Run AI Analysis action (RunAIAnalysisButton,
//     extracted from the Source band), labelled « Run AI on transcript to
//     extract next steps », the page's pipelineRunner, ONLY « nextSteps »
//     pre-checked; same display conditions as in Source, AND DC-only
//     (hasSuggestedNextSteps);
//   * « + Add next step »: DC-only (hasSuggestedNextSteps) — absent on a
//     campaign activity;
//   * the conversion block (Successful outcome + Start Decision Cycle +
//     ActivityModal): same conditions, unchanged, moved to the top;
//   * an activity without DC and without the conversion block: the band is
//     HIDDEN, the Preparation model (index.jsx: rendered only when it applies).
// The page, the band, RunAIAnalysisButton and RunAIWizard are REAL; the data
// hooks, the pipeline runner and the other bands are mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within, act } from "@testing-library/react";
import AphoriqTheme from "../_utils/aphoriqTheme";

let mockActivity;
const mockRun = vi.fn();
let mockPipelineState = "idle";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@mui/x-date-pickers/DatePicker", () => ({ DatePicker: () => <input /> }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));
vi.mock("components/MainCard", () => ({
  default: ({ children }) => <div data-testid="main-card">{children}</div>,
}));

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
vi.mock("api/signals/aggregatedSignals", async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => ({ signals: [] }),
}));
vi.mock("hooks/usePipelineRunner", async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => ({
    run: mockRun, state: mockPipelineState, result: null, error: null, pollProgress: null, reset: vi.fn(),
  }),
}));
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
vi.mock("components/signals/SignalsHaloBox", () => ({
  default: ({ children, ...rest }) => <div data-testid={rest["data-testid"]}>{children}</div>,
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn(),
}));
vi.mock("api/signals/signals", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetSignalChoices: () => ({ choices: {}, choicesLoading: false }),
  rejectSignal: vi.fn(),
}));
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: ({ open }) => (open ? <div data-testid="activity-modal" /> : null),
}));
vi.mock("components/signals/SignalEditDrawer", () => ({ default: () => null }));

import ActivityWorkspacePage from "views/activities/workspace";

const render = (ui) => rtlRender(<AphoriqTheme>{ui}</AphoriqTheme>);

const TRANSCRIPT = "We agreed on a security review with the CISO next month. ".repeat(3);
const EXTRACT_LABEL = /Run AI on transcript to extract next steps/;

const base = {
  id: "act-1", title: "Atelier", activity_type: "MEETING", status: "PLANNED", outcome: null,
  account: "acc-1", transcript: TRANSCRIPT, outcome_notes: "",
  decision_cycle: null, campaign_detail: null, next_planned_step: null,
};
const dcActivity = (over = {}) => ({ ...base, decision_cycle: "dc-1", ...over });
const campaignActivity = (over = {}) => ({
  ...base, activity_type: "CALL", status: "COMPLETED", outcome: "SUCCESSFUL",
  campaign_detail: { id: "camp-1", name: "Q4 push" }, ...over,
});

const band = () => screen.getByTestId("next-steps-band");
const follows = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

afterEach(() => {
  cleanup();
  mockRun.mockReset();
  mockPipelineState = "idle";
});

describe("Next steps band — the layout (5.12 B)", () => {
  it("DC activity: the sections → the extraction → « + Add next step »", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    const sections = within(band()).getByTestId("suggested-next-steps-block");
    const extraction = within(band()).getByTestId("next-steps-extraction");
    const add = within(band()).getByTestId("add-next-step");
    expect(follows(sections, extraction)).toBe(true);
    expect(follows(extraction, add)).toBe(true);
  });

  it("the « Next planned step » sub-block is gone: no title, no card, no empty state", () => {
    mockActivity = dcActivity({
      next_planned_step: {
        source: "DECISION_CYCLE", decision_cycle: { id: "dc-1", name: "Deal" },
        activity: { id: "act-9", title: "Security review", activity_type: "MEETING", status: "PLANNED" },
      },
    });
    render(<ActivityWorkspacePage />);
    expect(within(band()).queryByText("Next planned step")).toBeNull();
    expect(within(band()).queryByTestId("next-planned-step-block")).toBeNull();
    expect(within(band()).queryByTestId("activity-mini-card")).toBeNull();
    expect(within(band()).queryByText("Security review")).toBeNull();
    expect(within(band()).queryByText(/No next step planned yet/)).toBeNull();
    expect(within(band()).queryByText(/No sequence linked/)).toBeNull();
  });

  it("« + Add next step » at the bottom: the pill, then its row of types", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    const add = within(band()).getByTestId("add-next-step");
    fireEvent.click(within(add).getByText("+ Add next step"));
    expect(within(add).getByTestId("add-next-step-types")).toBeInTheDocument();
  });
});

describe("Next steps band — the extraction (5.12 B)", () => {
  it("the shared Run AI action, with its own label", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    const extraction = within(band()).getByTestId("next-steps-extraction");
    expect(within(extraction).getByRole("button", { name: EXTRACT_LABEL })).toBeEnabled();
  });

  it("the wizard opens with ONLY « nextSteps » pre-checked", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByRole("button", { name: EXTRACT_LABEL }));
    const box = (text) => screen.getByText(text).closest("label").querySelector('input[type="checkbox"]');
    expect(box(/Qualification signals/)).not.toBeChecked();
    expect(box(/Next-step suggestions/)).toBeChecked();
  });

  it("confirming runs the page's pipelineRunner for the next steps only", async () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByRole("button", { name: EXTRACT_LABEL }));
    await act(async () => { fireEvent.click(screen.getByText("Continue")); });
    await act(async () => { fireEvent.click(screen.getByText("Run analysis")); });
    expect(mockRun).toHaveBeenCalledWith("act-1", TRANSCRIPT.trim(), {
      run_qualification: false, run_next_steps: true,
    });
  });

  it("same display conditions as in Source: disabled without transcript", () => {
    mockActivity = dcActivity({ transcript: "" });
    render(<ActivityWorkspacePage />);
    expect(screen.getByRole("button", { name: EXTRACT_LABEL })).toBeDisabled();
  });

  it("same display conditions as in Source: « Analyzing… » while the pipeline runs", () => {
    mockPipelineState = "running";
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    const extraction = within(band()).getByTestId("next-steps-extraction");
    expect(within(extraction).getByRole("button", { name: /Analyzing/ })).toBeDisabled();
  });

  // 5.12c (5) — the AI action's lock: CANCELLED only (RunAILockPage).
  it("same lock as in Source: available on COMPLETED, locked on CANCELLED", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    expect(screen.getByRole("button", { name: EXTRACT_LABEL })).toBeEnabled();
    cleanup();
    mockActivity = dcActivity({ status: "CANCELLED" });
    render(<ActivityWorkspacePage />);
    expect(screen.getByRole("button", { name: EXTRACT_LABEL })).toBeDisabled();
  });
});

describe("Next steps band — campaign activity, free activity (5.12 B)", () => {
  it("a campaign activity SUCCESSFUL: the conversion block, at the top of the band", () => {
    mockActivity = campaignActivity();
    render(<ActivityWorkspacePage />);
    const conversion = within(band()).getByTestId("campaign-conversion");
    expect(within(conversion).getByText("Successful outcome — ready to convert")).toBeInTheDocument();
    fireEvent.click(within(conversion).getByRole("button", { name: /Start Decision Cycle/ }));
    expect(screen.getByTestId("activity-modal")).toBeInTheDocument();
    expect(band().firstElementChild.contains(conversion)).toBe(true);
  });

  it("a campaign activity: no « + Add next step », no extraction, no sections", () => {
    mockActivity = campaignActivity();
    render(<ActivityWorkspacePage />);
    expect(within(band()).queryByText("+ Add next step")).toBeNull();
    expect(within(band()).queryByTestId("add-next-step")).toBeNull();
    expect(within(band()).queryByTestId("next-steps-extraction")).toBeNull();
    expect(within(band()).queryByTestId("suggested-next-steps-block")).toBeNull();
  });

  it("MEETING_SCHEDULED converts too (same conditions)", () => {
    mockActivity = campaignActivity({ outcome: "MEETING_SCHEDULED" });
    render(<ActivityWorkspacePage />);
    expect(within(band()).getByTestId("campaign-conversion")).toBeInTheDocument();
  });

  it("a campaign activity whose DC was born: no conversion → no band", () => {
    mockActivity = campaignActivity({
      next_planned_step: { source: "BORN_DECISION_CYCLE", decision_cycle: { id: "dc-7", name: "Deal" }, activity: null },
    });
    render(<ActivityWorkspacePage />);
    expect(screen.queryByText("Next steps")).toBeNull();
    expect(screen.queryByTestId("next-steps-halo")).toBeNull();
  });

  it("a CANCELLED campaign activity: no conversion (the band lock, as before) → no band", () => {
    mockActivity = campaignActivity({ status: "CANCELLED" });
    render(<ActivityWorkspacePage />);
    expect(screen.queryByText("Start Decision Cycle")).toBeNull();
    expect(screen.queryByText("Next steps")).toBeNull();
  });

  it("a campaign activity without a converting outcome: no band", () => {
    mockActivity = campaignActivity({ outcome: "NO_ANSWER" });
    render(<ActivityWorkspacePage />);
    expect(screen.queryByText("Next steps")).toBeNull();
  });

  it("a free activity (no DC, no conversion): the band is HIDDEN, with its halo", () => {
    mockActivity = { ...base };
    render(<ActivityWorkspacePage />);
    expect(screen.queryByText("Next steps")).toBeNull();
    expect(screen.queryByTestId("next-steps-halo")).toBeNull();
    expect(screen.queryByTestId("next-steps-band")).toBeNull();
  });

  it("a DC activity: the band is there", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("Next steps")).toBeInTheDocument();
  });
});
