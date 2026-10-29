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
import AphoriqTheme, { testTheme } from "../_utils/aphoriqTheme";

let mockActivity;
const mockRun = vi.fn();
let mockPipelineState = "idle";
let mockSignals = [];
let mockRunsByPipeline = {};

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
    lastRun: { id: "run-1" }, latestRun: null, runsByPipeline: mockRunsByPipeline, mutateLastRun: vi.fn(),
  }),
}));
vi.mock("api/signals/signalCounts", () => ({
  useActivitySignalCounts: () => ({ counts: {}, mutateCounts: vi.fn() }),
}));
vi.mock("api/signals/aggregatedSignals", async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => ({ signals: mockSignals }),
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
// 5.12c (3): a pill. 5.12e (3): labelled « Run AI Analysis », as in Source.
const EXTRACT_LABEL = "Run AI Analysis";
const nextStep = (over = {}) => ({
  id: "ns-p", _signalType: "next-steps", signal_type: "next-steps", status: "PENDING",
  suggested_title: "Send the DPA", suggested_activity_type: "EMAIL",
  suggested_due_date: "2026-11-03", created_at: "2026-10-20T10:00:00Z",
  source_context: { contacts: [] }, linked_activity: null, attached_activity: null, ...over,
});
const NEXT_STEPS_RAN = {
  NEXT_STEPS: { last_run_at: "2026-11-03T14:32:00Z", status: "SUCCESS", pipeline_type: "NEXT_STEPS" },
};

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
  mockSignals = [];
  mockRunsByPipeline = {};
});

describe("Next steps band — the layout (5.12 B)", () => {
  // 5.12e (3): the AI action sits INSIDE the list's empty state (the shared
  // EmptyState's `action`), centred, right under its text, aligned on its icon.
  it("DC activity: the AI action is in the empty state, right under its text, centred", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    const sections = within(band()).getByTestId("suggested-next-steps-block");
    const empty = within(sections).getByTestId("empty-state");
    const text = within(empty).getByText("No next-step suggestions for this activity");
    const extraction = within(empty).getByTestId("next-steps-extraction");
    expect(follows(text, extraction)).toBe(true);
    // The EmptyState column: the icon, the text, then the action — centred.
    const column = text.parentElement;
    expect(column.contains(empty.querySelector(".anticon"))).toBe(true);
    expect(column.contains(extraction)).toBe(true);
    expect(column).toHaveStyle({ alignItems: "center" });
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

  // 5.12e (4) — « + Add next step » on the right of the BAND's title (the
  // CollapsibleStrip `meta` slot, as in 5.8e); never at the bottom any more.
  const header = () => screen.getByText("Next steps").closest("[aria-expanded]");
  const addPill = () => within(header()).getByRole("button", { name: "+ Add next step" });

  it("« + Add next step » sits in the band header, right of its title", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    expect(addPill()).toHaveAttribute("data-testid", "status-pill");
    expect(follows(screen.getByText("Next steps"), addPill())).toBe(true);
    expect(within(band()).queryByRole("button", { name: "+ Add next step" })).toBeNull();
    expect(within(band()).queryByTestId("add-next-step")).toBeNull();
  });

  it("a click: the band does not fold; the type row appears at the TOP of the band body", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    expect(header()).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(addPill());
    expect(header()).toHaveAttribute("aria-expanded", "true");
    const types = within(band()).getByTestId("add-next-step-types");
    expect(band().firstElementChild).toBe(types);
    fireEvent.keyDown(addPill(), { key: "Enter" });
    expect(header()).toHaveAttribute("aria-expanded", "true");
    expect(within(band()).queryByTestId("add-next-step-types")).toBeNull();
  });

  it("a FOLDED band: the pill unfolds it and shows the type row", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByText("Next steps"));
    expect(header()).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(addPill());
    expect(header()).toHaveAttribute("aria-expanded", "true");
    expect(within(band()).getByTestId("add-next-step-types")).toBeInTheDocument();
  });

  it("a type pill → the creation with that type; the type row closes", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(addPill());
    fireEvent.click(within(within(band()).getByTestId("add-next-step-types")).getByRole("button", { name: "Meeting" }));
    expect(within(band()).queryByTestId("add-next-step-types")).toBeNull();
  });

  it("DC-only, hidden on CANCELLED: no pill on a campaign activity nor a CANCELLED one", () => {
    mockActivity = campaignActivity();
    render(<ActivityWorkspacePage />);
    expect(within(header()).queryByRole("button", { name: "+ Add next step" })).toBeNull();
    cleanup();
    mockActivity = dcActivity({ status: "CANCELLED" });
    render(<ActivityWorkspacePage />);
    expect(within(header()).queryByRole("button", { name: "+ Add next step" })).toBeNull();
    cleanup();
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    expect(addPill()).toBeInTheDocument();
  });
});

describe("Next steps band — the AI action (5.12 B, 5.12c (3))", () => {
  const pill = () => within(band()).getByRole("button", { name: EXTRACT_LABEL });

  // Homogeneity (PO): no MUI button action in the band — pills, as
  // « + Add next step ».
  it("a ClickablePill « Run AI Analysis » (the Source's label) — the « + Add next step » pill, no MUI button", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    expect(pill()).toHaveAttribute("data-testid", "status-pill");
    expect(pill()).toHaveTextContent(/^Run AI Analysis$/);
    expect(pill().className).toBe(screen.getByRole("button", { name: "+ Add next step" }).className);
    expect(band().querySelector(".MuiButton-root")).toBeNull();
  });

  it("no next step and NEXT STEPS never ran → the pill", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    expect(pill()).toBeInTheDocument();
    expect(within(band()).queryByText(/AI already ran/)).toBeNull();
  });

  it("no next step and NEXT STEPS already ran → « AI already ran · <short date> », no action, in the empty state", () => {
    mockRunsByPipeline = NEXT_STEPS_RAN;
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    const extraction = within(within(band()).getByTestId("empty-state")).getByTestId("next-steps-extraction");
    expect(extraction.textContent).toBe("AI already ran · 3 Nov 2026");
    expect(within(extraction).queryByRole("button")).toBeNull();
    expect(within(extraction).getByText(/AI already ran/)).toHaveStyle({ color: testTheme.palette.text.secondary });
  });

  it("only the QUALIFICATION ran (not NEXT STEPS) → still the pill", () => {
    mockRunsByPipeline = { TRANSCRIPT_SIGNALS: { last_run_at: "2026-11-03T14:32:00Z", status: "SUCCESS" }, NEXT_STEPS: null };
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    expect(pill()).toBeInTheDocument();
  });

  it.each([["PENDING"], ["VALIDATED"], ["REJECTED"]])(
    "at least one next step (%s) → no AI action",
    (status) => {
      mockSignals = [nextStep({ status })];
      mockActivity = dcActivity();
      render(<ActivityWorkspacePage />);
      expect(within(band()).queryByTestId("next-steps-extraction")).toBeNull();
      expect(within(band()).queryByRole("button", { name: EXTRACT_LABEL })).toBeNull();
    },
  );

  it("the wizard opens with ONLY « nextSteps » pre-checked", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(pill());
    const box = (text) => screen.getByText(text).closest("label").querySelector('input[type="checkbox"]');
    expect(box(/Qualification signals/)).not.toBeChecked();
    expect(box(/Next-step suggestions/)).toBeChecked();
  });

  it("keyboard: Enter on the pill opens the wizard", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    fireEvent.keyDown(pill(), { key: "Enter" });
    expect(screen.getByText(/Next-step suggestions/)).toBeInTheDocument();
  });

  it("confirming runs the page's pipelineRunner for the next steps only", async () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(pill());
    await act(async () => { fireEvent.click(screen.getByText("Continue")); });
    await act(async () => { fireEvent.click(screen.getByText("Run analysis")); });
    expect(mockRun).toHaveBeenCalledWith("act-1", TRANSCRIPT.trim(), {
      run_qualification: false, run_next_steps: true,
    });
  });

  it("same conditions as in Source: disabled without transcript (no wizard on click)", () => {
    mockActivity = dcActivity({ transcript: "" });
    render(<ActivityWorkspacePage />);
    expect(pill()).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(pill());
    expect(screen.queryByText(/Next-step suggestions/)).toBeNull();
  });

  it("same conditions as in Source: « Analyzing… » while the pipeline runs", () => {
    mockPipelineState = "running";
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    const extraction = within(band()).getByTestId("next-steps-extraction");
    const analyzing = within(extraction).getByRole("button", { name: "Analyzing…" });
    expect(analyzing).toHaveAttribute("data-testid", "status-pill");
    expect(analyzing).toHaveAttribute("aria-disabled", "true");
  });

  // 5.12c (5) — the AI action's lock: CANCELLED only (RunAILockPage).
  it("same lock as in Source: available on COMPLETED, locked on CANCELLED", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    expect(pill()).not.toHaveAttribute("aria-disabled", "true");
    cleanup();
    mockActivity = dcActivity({ status: "CANCELLED" });
    render(<ActivityWorkspacePage />);
    expect(pill()).toHaveAttribute("aria-disabled", "true");
  });
});

describe("Next steps band — campaign activity, free activity (5.12 B)", () => {
  it("a campaign activity SUCCESSFUL: the conversion block, at the top of the band", () => {
    mockActivity = campaignActivity();
    render(<ActivityWorkspacePage />);
    const conversion = within(band()).getByTestId("campaign-conversion");
    expect(within(conversion).getByText("Successful outcome — ready to convert")).toBeInTheDocument();
    // 5.13: a pill (it opens the creation drawer — StartDecisionCyclePage);
    // no ActivityModal any more.
    expect(within(conversion).getByRole("button", { name: "Start Decision Cycle" }))
      .toHaveAttribute("data-testid", "status-pill");
    expect(screen.queryByTestId("activity-modal")).toBeNull();
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
