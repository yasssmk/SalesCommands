// frontend/src/__tests__/nextSteps/RunAILockPage.test.jsx
//
// Sprint Next steps 5.12c (5) — PO decision: the AI action (Run AI) is locked
// ONLY on a CANCELLED activity — ONE predicate, isActivitySignalsLocked
// (utils/activitySignalsLock), for the Source band AND the Next steps band.
// The backend accepts a run on a COMPLETED activity (activity_extraction_view:
// no status guard; its endpoint tests run on a COMPLETED activity).
// 5.12d (1) — the TRANSCRIPT follows the same lock (CANCELLED only), so a
// transcript can be added after the call (COMPLETED, campaign activities
// included); the other Source fields keep the page lock (COMPLETED or
// CANCELLED — the notes stay read-only on a COMPLETED activity).
// On the workspace PAGE as really rendered: the page, the Source band
// (ActivityNotesTab, EditableTextBlock), the Next steps band and the shared
// RunAIAnalysisButton are REAL; the data hooks and the other bands are mocked.

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
import { updateActivity } from "api/accounts/activities";

const render = (ui) => rtlRender(<AphoriqTheme>{ui}</AphoriqTheme>);

const TRANSCRIPT = "We agreed on a security review with the CISO next month. ".repeat(3);
const dcActivity = (over = {}) => ({
  id: "act-1", title: "Atelier", activity_type: "MEETING", status: "PLANNED", outcome: null,
  account: "acc-1", transcript: TRANSCRIPT, outcome_notes: "",
  decision_cycle: "dc-1", campaign_detail: null, next_planned_step: null, ...over,
});

// The Source band is folded by default: unfold it.
const openSource = () => fireEvent.click(screen.getByText("Source"));
const sourceRunAI = () => screen.getByRole("button", { name: /Run AI Analysis/ });
const bandRunAI = () => within(screen.getByTestId("next-steps-extraction")).getByRole("button", { name: /Run AI on transcript/ });

afterEach(() => cleanup());

describe("Run AI — locked ONLY on CANCELLED, both bands (5.12c (5))", () => {
  it("COMPLETED: the Source's Run AI is available", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    openSource();
    expect(sourceRunAI()).toBeEnabled();
    // 5.12c (3): the Source keeps its MUI button (no visible change there).
    expect(sourceRunAI()).toHaveClass("MuiButton-root");
  });

  it("COMPLETED: the Next steps band's Run AI is available", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    expect(bandRunAI()).not.toHaveAttribute("aria-disabled", "true");
    expect(bandRunAI()).toBeEnabled();
  });

  it("CANCELLED: both are locked", () => {
    mockActivity = dcActivity({ status: "CANCELLED" });
    render(<ActivityWorkspacePage />);
    openSource();
    expect(sourceRunAI()).toBeDisabled();
    const band = bandRunAI();
    expect(band.disabled || band.getAttribute("aria-disabled") === "true").toBe(true);
  });


  it("PLANNED: the transcript is editable (the rule, unchanged)", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    openSource();
    fireEvent.click(screen.getByText(/We agreed on a security review/));
    expect(screen.getAllByRole("textbox").length).toBeGreaterThan(0);
  });
});

// ==============================|| 5.12d (1) — THE TRANSCRIPT ||============================== //

const NOTES_PLACEHOLDER = /Capture key takeaways/;
const editTranscriptAndSave = async (text) => {
  fireEvent.click(screen.getByText(/We agreed on a security review/));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
  await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Save/ })); });
};

describe("The transcript — locked ONLY on CANCELLED (5.12d (1))", () => {
  afterEach(() => vi.mocked(updateActivity).mockReset());

  it("COMPLETED: the transcript is editable and saved", async () => {
    vi.mocked(updateActivity).mockResolvedValue({ success: true });
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    openSource();
    await editTranscriptAndSave("A transcript pasted after the call, long enough to be analysed later.");
    expect(updateActivity).toHaveBeenCalledWith("act-1", {
      transcript: "A transcript pasted after the call, long enough to be analysed later.",
    });
  });

  it("COMPLETED campaign activity: the transcript is editable and saved too", async () => {
    vi.mocked(updateActivity).mockResolvedValue({ success: true });
    mockActivity = dcActivity({
      status: "COMPLETED", decision_cycle: null, outcome: "NO_ANSWER",
      campaign_detail: { id: "camp-1", name: "Q4 push" },
    });
    render(<ActivityWorkspacePage />);
    openSource();
    await editTranscriptAndSave("Voicemail transcript of the campaign call, pasted afterwards.");
    expect(updateActivity).toHaveBeenCalledWith("act-1", {
      transcript: "Voicemail transcript of the campaign call, pasted afterwards.",
    });
  });

  it("CANCELLED: the transcript is read-only", () => {
    mockActivity = dcActivity({ status: "CANCELLED" });
    render(<ActivityWorkspacePage />);
    openSource();
    fireEvent.click(screen.getByText(/We agreed on a security review/));
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("COMPLETED: the OTHER Source fields keep their rule — the notes stay read-only", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    openSource();
    fireEvent.click(screen.getByText(NOTES_PLACEHOLDER));
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("PLANNED: the notes are editable (the rule, unchanged)", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    openSource();
    fireEvent.click(screen.getByText(NOTES_PLACEHOLDER));
    expect(screen.getAllByRole("textbox").length).toBeGreaterThan(0);
  });
});
