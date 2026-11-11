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
// 8g-7: the last successful run (null = not analysed yet) — per test.
let mockLastRun = null;
// 3.2: the per-pipeline successful runs (the server state) — per test.
let mockRunsByPipeline = {};

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/activities/act-1",
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
    lastRun: mockLastRun, latestRun: null, runsByPipeline: mockRunsByPipeline, mutateLastRun: vi.fn(),
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
  displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn(), displayWarningSnackbar: vi.fn(),
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
// The Source's Run AI (same label as the band's since 5.12e): the one outside
// the Next steps band.
const sourceRunAI = () => {
  const band = screen.queryByTestId("next-steps-band");
  const [button] = screen.getAllByRole("button", { name: /Run AI Analysis/ })
    .filter((b) => !band || !band.contains(b));
  return button;
};
const bandRunAI = () => within(screen.getByTestId("next-steps-extraction")).getByRole("button", { name: "Run AI Analysis" });

afterEach(() => { cleanup(); mockLastRun = null; mockRunsByPipeline = {}; });

describe("Run AI — locked ONLY on CANCELLED, both bands (5.12c (5))", () => {
  it("COMPLETED: the Source's Run AI is available", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    openSource();
    expect(sourceRunAI()).not.toHaveAttribute("aria-disabled");
    // Lot 3 / 11 (TD-302, PO) replaces 5.12c (3): the Source's Run AI is the
    // shared pill too (in the band header), no MUI button any more.
    expect(sourceRunAI()).not.toHaveClass("MuiButton-root");
  });

  it("COMPLETED: the Next steps band's Run AI is available", () => {
    mockLastRun = { id: "run-1" };   // the Next steps band shows on an analysed activity
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    expect(bandRunAI()).not.toHaveAttribute("aria-disabled", "true");
    expect(bandRunAI()).toBeEnabled();
  });

  it("CANCELLED: both are locked", () => {
    mockLastRun = { id: "run-1" };   // the Next steps band shows on an analysed activity
    mockActivity = dcActivity({ status: "CANCELLED" });
    render(<ActivityWorkspacePage />);
    openSource();
    expect(sourceRunAI()).toHaveAttribute("aria-disabled", "true");
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

// N6: the band's note is READ-ONLY (written in the notes panel).
const NOTES_PLACEHOLDER = /No notes yet\./;
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

  // « Source / Notes » N6 (PO) — the ONE note is written in the notes panel
  // (its own lock: CANCELLED only, ActivityNotesPanel); the band shows it
  // READ-ONLY on every status (EditableTextBlock's read mode), no Save.
  it.each(["PLANNED", "COMPLETED", "CANCELLED"])("%s: the band's note is read-only", (status) => {
    mockActivity = dcActivity({ status, transcript: "", outcome_notes: "Takeaways from the call." });
    render(<ActivityWorkspacePage />);
    openSource();
    fireEvent.click(screen.getByText("Takeaways from the call."));
    // only the transcript may open (PLANNED / COMPLETED): never the note
    expect(screen.queryByDisplayValue("Takeaways from the call.")).toBeNull();
    expect(screen.queryByRole("button", { name: /Save/ })).toBeNull();
  });

  it("an empty note reads « No notes yet. », not an invitation to type", () => {
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    openSource();
    fireEvent.click(screen.getByText(NOTES_PLACEHOLDER));
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});

// ==============================|| 8g-7 (TD-25) — ANALYSED: THE TRANSCRIPT IS LOCKED ||============================== //
// PO: no re-run of an analysis; once an analysis SUCCEEDED, the transcript is
// locked (read-only) with an info notice. « Analysed » = lastRun, THE source
// of the wizard (RunAIWizard runsByPipeline, same last-run endpoint) — the
// server refuses the PATCH on the same rule (ai_pipelines/services/
// analysis_state.py). A failed analysis (no lastRun) leaves it editable.

const ANALYSED_RUN = { id: "run-1", last_run_at: "2026-11-01T10:00:00Z", last_run_by: null };

describe("The transcript — locked once analysed (8g-7)", () => {
  it("analysed: the transcript is read-only, with the info notice", () => {
    mockLastRun = ANALYSED_RUN;
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    openSource();
    fireEvent.click(screen.getByText(/We agreed on a security review/));
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByTestId("transcript-analysed-notice")).toHaveTextContent(/already been analysed/);
  });

  // N6: the band's note is read-only anyway — the analysis does not change
  // that (the note is written in the notes panel, CANCELLED its only lock).
  it("analysed: the band's note stays read-only", () => {
    mockLastRun = ANALYSED_RUN;
    mockActivity = dcActivity();
    render(<ActivityWorkspacePage />);
    openSource();
    fireEvent.click(screen.getByText(NOTES_PLACEHOLDER));
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("not analysed (none or a failed run): editable, no notice", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    openSource();
    expect(screen.queryByTestId("transcript-analysed-notice")).toBeNull();
    fireEvent.click(screen.getByText(/We agreed on a security review/));
    expect(screen.getAllByRole("textbox").length).toBeGreaterThan(0);
  });
});

// ==============================|| LOT 3 / 11 (TD-302) — THE SOURCE BAND'S RUN AI ||============================== //
// PO: the Source band's Run AI is a PILL placed as the other bands' actions —
// in the band header (CollapsibleStrip `meta`), as the Next steps band's
// « + Add next step » (ActivityNextStepsBand.jsx). Visible while folded; a
// click opens the wizard without toggling the band.

const sourceHeader = () => screen.getByText("Source").closest("[aria-expanded]");

describe("The Source band's Run AI — a pill in the band header (TD-302)", () => {
  it("is in the header, as a pill, while the band is folded", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    expect(sourceHeader()).toHaveAttribute("aria-expanded", "false");
    const pill = within(sourceHeader()).getByRole("button", { name: "Run AI Analysis" });
    expect(pill).not.toHaveClass("MuiButton-root");
    expect(pill).not.toHaveAttribute("aria-disabled");
  });

  it("a click opens the wizard and does not unfold the band", async () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    await act(async () => {
      fireEvent.click(within(sourceHeader()).getByRole("button", { name: "Run AI Analysis" }));
    });
    expect(screen.getByText(/Select objectives/)).toBeInTheDocument();
    expect(sourceHeader()).toHaveAttribute("aria-expanded", "false");
  });

  it("CANCELLED: the pill is disabled", () => {
    mockActivity = dcActivity({ status: "CANCELLED" });
    render(<ActivityWorkspacePage />);
    const pill = within(sourceHeader()).getByRole("button", { name: "Run AI Analysis" });
    expect(pill).toHaveAttribute("aria-disabled", "true");
  });
});

// ==============================|| « SOURCE / NOTES » 2.4 — NO NOTE LOST IN THE SOURCE BAND ||============================== //
// N6: the note is no longer edited in the band (read-only, written in the
// notes panel — autosaved, never an unsaved change): these 2.4 protections now
// hold for the TRANSCRIPT, the band's one edited field.
// The Source band's transcript, while edited, is a PAGE source of
// unsaved changes (EditableTextBlock.onDirtyChange → useUnsavedChanges): an
// internal link asks first (2.3); a drawer opening does not lose them (the
// page stays mounted — no confirmation). Folding the band no longer destroys
// the edit (disableUnmount). A Save refused by the front rule (the activity
// became CANCELLED meanwhile) is no longer silent: the ORANGE warning; a
// server refusal stays red. Real page in the real coque.

import WorkspaceCoque from "../_utils/workspaceCoque";
import UnsavedLinkGuard from "components/drawer/UnsavedLinkGuard";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { displayErrorSnackbar, displayWarningSnackbar } from "utils/displayError";
import { SOURCE_LOCKED_MESSAGE } from "utils/activitySignalsLock";

function OpenOther() {
  const { openDrawer } = useWorkspaceDrawer();
  return <button onClick={() => openDrawer(<div data-testid="other">other</div>)}>open-other</button>;
}

const renderInCoque = () =>
  rtlRender(
    <>
      <ActivityWorkspacePage />
      <OpenOther />
      <a href="/accounts/acc-1" onClick={(e) => e.preventDefault()}>Account link</a>
      <UnsavedLinkGuard />
    </>,
    { wrapper: WorkspaceCoque },
  );

// N6: the band's edited field is the transcript (empty → its placeholder).
const typeTranscript = (text) => {
  fireEvent.click(screen.getByText(/Paste the call transcript/));
  fireEvent.change(screen.getByRole("textbox"), { target: { value: text } });
};

describe("The Source band — no note lost (2.4)", () => {
  afterEach(() => {
    vi.mocked(updateActivity).mockReset();
    vi.mocked(displayWarningSnackbar).mockClear();
    vi.mocked(displayErrorSnackbar).mockClear();
  });

  it("folding then unfolding the band keeps the transcript being typed", async () => {
    mockActivity = dcActivity({ transcript: "" });
    render(<ActivityWorkspacePage />);
    openSource();
    typeTranscript("Half a transcript");
    fireEvent.click(screen.getByText("Source"));
    // Let the fold transition end (it used to unmount the body).
    await act(async () => { await new Promise((r) => setTimeout(r, 450)); });
    fireEvent.click(screen.getByText("Source"));
    expect(screen.getByRole("textbox")).toHaveValue("Half a transcript");
  });

  it("the band's note (read-only) never asks: an internal link goes through", () => {
    mockActivity = dcActivity({ outcome_notes: "A note" });
    renderInCoque();
    openSource();
    fireEvent.click(screen.getByText("A note"));
    fireEvent.click(screen.getByText("Account link"));
    expect(screen.queryByTestId("confirm-dialog")).toBeNull();
  });

  it("a transcript being typed: an internal link asks first", () => {
    mockActivity = dcActivity({ transcript: "" });
    renderInCoque();
    openSource();
    typeTranscript("A pasted transcript");
    fireEvent.click(screen.getByText("Account link"));
    expect(screen.getByTestId("confirm-dialog")).toHaveTextContent("Discard your changes?");
  });

  it("a transcript being typed survives a drawer opening — the page stays, no confirmation", () => {
    mockActivity = dcActivity({ transcript: "" });
    renderInCoque();
    openSource();
    typeTranscript("Half a transcript");
    fireEvent.click(screen.getByText("open-other"));
    expect(screen.queryByTestId("confirm-dialog")).toBeNull();
    expect(screen.getByTestId("other")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Half a transcript")).toBeInTheDocument();
  });

  it("nothing typed: an internal link does not ask", () => {
    mockActivity = dcActivity();
    renderInCoque();
    openSource();
    fireEvent.click(screen.getByText("Account link"));
    expect(screen.queryByTestId("confirm-dialog")).toBeNull();
  });

  it("the activity became CANCELLED while typing: Save shows the ORANGE warning, no PATCH", async () => {
    mockActivity = dcActivity({ transcript: "" });
    const { rerender } = render(<ActivityWorkspacePage />);
    openSource();
    typeTranscript("A pasted transcript");
    mockActivity = dcActivity({ status: "CANCELLED", transcript: "" });
    rerender(<AphoriqTheme><ActivityWorkspacePage /></AphoriqTheme>);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Save/ })); });
    expect(displayWarningSnackbar).toHaveBeenCalledWith(SOURCE_LOCKED_MESSAGE);
    expect(updateActivity).not.toHaveBeenCalled();
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
  });

  it("a server refusal stays a red error", async () => {
    vi.mocked(updateActivity).mockResolvedValue({ success: false, status: 400, error: "Refused" });
    mockActivity = dcActivity({ transcript: "" });
    render(<ActivityWorkspacePage />);
    openSource();
    typeTranscript("A pasted transcript");
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: /Save/ })); });
    expect(displayErrorSnackbar).toHaveBeenCalledWith(expect.objectContaining({ error: "Refused" }));
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
  });
});

// ==============================|| « SOURCE / NOTES » 3.2 — EVERYTHING ANALYSED ||============================== //
// ONE predicate (canRunAIAnalysis) for the Source band's pill and the Next
// steps band's: disabled once everything AVAILABLE is analysed.

const DONE = { last_run_at: "2026-11-01T10:00:00Z", created_signals_count: 1 };

describe("Run AI — everything available already analysed (3.2)", () => {
  it("qualification + next steps analysed (DC): the Source pill is disabled", () => {
    mockLastRun = DONE;
    mockRunsByPipeline = { TRANSCRIPT_SIGNALS: DONE, NEXT_STEPS: DONE };
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    const pill = within(sourceHeader()).getByRole("button", { name: "Run AI Analysis" });
    expect(pill).toHaveAttribute("aria-disabled", "true");
  });

  it("qualification analysed, next steps still available (DC): both pills active", () => {
    mockLastRun = DONE;
    mockRunsByPipeline = { TRANSCRIPT_SIGNALS: DONE, NEXT_STEPS: null };
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    expect(within(sourceHeader()).getByRole("button", { name: "Run AI Analysis" }))
      .not.toHaveAttribute("aria-disabled");
    expect(bandRunAI()).not.toHaveAttribute("aria-disabled");
  });

  it("qualification analysed, no next steps possible (no DC, no campaign): the Source pill is disabled", () => {
    mockLastRun = DONE;
    mockRunsByPipeline = { TRANSCRIPT_SIGNALS: DONE, NEXT_STEPS: null };
    mockActivity = dcActivity({ status: "COMPLETED", decision_cycle: null });
    render(<ActivityWorkspacePage />);
    expect(within(sourceHeader()).getByRole("button", { name: "Run AI Analysis" }))
      .toHaveAttribute("aria-disabled", "true");
  });

  it("nothing analysed: the Source pill is active", () => {
    mockActivity = dcActivity({ status: "COMPLETED" });
    render(<ActivityWorkspacePage />);
    expect(within(sourceHeader()).getByRole("button", { name: "Run AI Analysis" }))
      .not.toHaveAttribute("aria-disabled");
  });
});
