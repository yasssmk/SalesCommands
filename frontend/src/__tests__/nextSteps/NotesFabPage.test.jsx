// frontend/src/__tests__/nextSteps/NotesFabPage.test.jsx
//
// Sprint « Source / Notes » — notes panel, N5: the floating « Notes » button,
// through the REAL Activity workspace page in the REAL coque (harness of
// WorkspaceHookDepsPage.test.jsx). Present on the Activity page — every
// activity type — and nowhere else; a click opens the notes zone, a second
// click closes it; it moves left by the coque's width + margin while the coque
// is open in PUSH mode; its Badge dot shows while a note is pending (primary)
// or in error (error).
// N6 — the Source band: the note READ-ONLY; its header's « Open notes » pill
// opens the SAME panel (the button shows it open, its dot follows it); a
// note typed in the panel shows in the band once saved.

import fs from "node:fs";
import path from "node:path";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor, within } from "@testing-library/react";
import { SWRConfig } from "swr";
import WorkspaceCoque from "../_utils/workspaceCoque";
import { testTheme } from "../_utils/aphoriqTheme";

const ACT_ID = "11111111-1111-4111-8111-111111111111";
const ACC_ID = "22222222-2222-4222-8222-222222222222";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "11111111-1111-4111-8111-111111111111" }),
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/activities/11111111-1111-4111-8111-111111111111",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("next/link", () => ({
  default: ({ href, children }) => <a href={typeof href === "string" ? href : "#"}>{children}</a>,
}));
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
vi.mock("@mui/x-date-pickers/DatePicker", () => ({ DatePicker: () => <input /> }));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));
vi.mock("utils/axiosClient", () => ({ api: { post: vi.fn(), get: vi.fn(), patch: vi.fn() } }));
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ tenantId: "t-1", user: { id: "u-1", first_name: "Ann", last_name: "Owner" } }),
  default: () => ({ tenantId: "t-1", user: { id: "u-1", first_name: "Ann", last_name: "Owner" } }),
}));
vi.mock("api/aiPipelines/lastRun", () => ({
  useGetLastExtractionRun: () => ({
    // An analysed activity: the Next steps band opens expanded (its rows).
    lastRun: { id: "run-1", last_run_at: "2026-10-28T10:00:00Z" }, latestRun: null,
    runsByPipeline: {}, mutateLastRun: vi.fn(),
  }),
}));
vi.mock("api/signals/signalCounts", () => ({
  useActivitySignalCounts: () => ({ counts: {}, mutateCounts: vi.fn() }),
}));
let mockNextSteps = [];
vi.mock("api/signals/aggregatedSignals", async (importOriginal) => ({
  ...(await importOriginal()),
  default: (args) => ({
    signals: (args?.signalTypes || []).includes("next-steps") ? mockNextSteps : [],
    loading: false, error: null, mutate: vi.fn(),
  }),
}));
vi.mock("hooks/usePipelineRunner", async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => ({ run: vi.fn(), state: "idle", result: null, error: null, pollProgress: null, reset: vi.fn() }),
}));
vi.mock("contexts/BreadcrumbContext", () => ({ useBreadcrumb: () => ({ setCrumbs: vi.fn() }) }));
vi.mock("sections/campaigns/CampaignOutcomeModal", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityPreparationTab", () => ({ default: () => null }));
// N6: the REAL Source band body (ActivityNotesTab) — the note read-only.
vi.mock("sections/activities/workspace/ActivitySignalsTab", () => ({
  default: () => null,
  ACTIVITY_FLAT_TYPES: ["pain"],
}));
vi.mock("components/signals/SignalsHaloBox", () => ({ default: ({ children }) => <>{children}</> }));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
}));
const { saveActivityNotes, saveActivityNotesKeepalive } = vi.hoisted(() => ({
  saveActivityNotes: vi.fn(),
  saveActivityNotesKeepalive: vi.fn(() => true),
}));
vi.mock("api/accounts/activities", async (importOriginal) => ({
  ...(await importOriginal()),
  saveActivityNotes,
  saveActivityNotesKeepalive,
}));

import ActivityWorkspacePage from "views/activities/workspace";
import useMediaQuery from "@mui/material/useMediaQuery";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { NOTES_FAB_TOOLTIP, OPEN_NOTES_PILL_LABEL } from "sections/activities/workspace/ActivityNotesFab";
import { clearLocalNoteWrites, NOTES_AUTOSAVE_DELAY_MS } from "hooks/useNoteAutosave";

// ==============================|| HARNESS ||============================== //

const OWNER = { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" };
const activityOf = (over = {}) => ({
  id: ACT_ID, title: "Discovery call", activity_type: "CALL", status: "PLANNED",
  outcome: null, scheduled_date: "2026-11-20",
  account: ACC_ID, account_detail: { id: ACC_ID, company_name: "Acme" },
  owner_detail: OWNER, invited_users_detail: [], contacts_detail: [],
  decision_cycle: null, decision_cycle_detail: null, decision_step: null, decision_step_detail: null,
  campaign_detail: null, source_activity_detail: null,
  next_step_origins: [], next_planned_step: null, transcript: "", outcome_notes: "First thoughts",
  call_to_action: "", description: "", updated_at: "2026-11-11T09:00:00Z",
  ...over,
});

let serverActivity;
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  if (url.startsWith(`/module-activities/${ACT_ID}`)) return Promise.resolve({ data: serverActivity });
  return Promise.resolve({ data: { results: [], count: 0 } });
};

const swr = { fetcher, dedupingInterval: 0, provider: () => new Map() };
const renderPage = (a = activityOf()) => {
  serverActivity = a;
  return render(
    <SWRConfig value={swr}>
      <WorkspaceCoque>
        <ActivityWorkspacePage />
      </WorkspaceCoque>
    </SWRConfig>,
  );
};

function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
  const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
  return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
}

const fab = () => screen.findByRole("button", { name: NOTES_FAB_TOOLTIP });
const notesZone = () => screen.queryByTestId("coque-notes-zone");
const notesBox = () => screen.getByRole("textbox", { name: "Notes" });
const dot = () => screen.getByTestId("activity-notes-fab-badge").querySelector(".MuiBadge-badge");
const PUSH_OFFSET = `right:calc(${testTheme.aphoriQ.drawer.width}px + ${testTheme.spacing(1.5)} + ${testTheme.spacing(3)})`;

beforeEach(() => {
  clearLocalNoteWrites();
  useMediaQuery.mockReturnValue(false); // large: push
  saveActivityNotes.mockReset();
  saveActivityNotes.mockImplementation(async (_id, notes) => ({
    success: true, data: { outcome_notes: notes, updated_at: new Date().toISOString() },
  }));
  saveActivityNotesKeepalive.mockClear();
});
afterEach(() => cleanup());

// ==============================|| PRESENCE ||============================== //

describe("N5 — the floating Notes button: where", () => {
  it.each(["CALL", "EMAIL", "MEETING", "DEMO", "TASK", "LINKEDIN", "OTHER"])(
    "present on the Activity page — %s",
    async (type) => {
      renderPage(activityOf({ activity_type: type }));
      const button = await fab();
      expect(button).toHaveAttribute("data-testid", "activity-notes-fab");
      // fixed, bottom right, at the speed-dial layer
      const rule = rulesForElement(button);
      expect(rule).toMatch(/position:\s*fixed/);
      expect(rule).toContain(`z-index:${testTheme.zIndex.speedDial}`);
      expect(rule).toContain(`right:${testTheme.spacing(3)}`);
      expect(rule).toContain(`bottom:${testTheme.spacing(3)}`);
    },
  );

  it("its tooltip is « Notes »", async () => {
    renderPage();
    fireEvent.mouseOver(await fab());
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Notes");
  });

  it("absent elsewhere: the coque alone renders none", () => {
    function OpenSomething() {
      const { openDrawer } = useWorkspaceDrawer();
      return <button onClick={() => openDrawer(<div>content</div>)}>open</button>;
    }
    render(<WorkspaceCoque><OpenSomething /></WorkspaceCoque>);
    fireEvent.click(screen.getByText("open"));
    expect(screen.queryByTestId("activity-notes-fab")).not.toBeInTheDocument();
  });

  it("absent elsewhere: ONLY the Activity page renders it", () => {
    const root = path.resolve(__dirname, "../..");
    const importers = [];
    const walk = (dir) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (entry.name !== "__tests__" && entry.name !== "node_modules") walk(full);
        } else if (/\.(jsx?|tsx?)$/.test(entry.name)) {
          const source = fs.readFileSync(full, "utf8");
          if (/from\s+["'][^"']*ActivityNotesFab["']/.test(source)) {
            importers.push(path.relative(root, full));
          }
        }
      }
    };
    walk(root);
    expect(importers).toEqual([path.join("views", "activities", "workspace", "index.jsx")]);
  });
});

// ==============================|| OPEN / CLOSE / OFFSET ||============================== //

describe("N5 — click opens, second click closes; out of the coque's way", () => {
  it("click → the notes zone opens with the note; click again → it closes", async () => {
    renderPage();
    const button = await fab();
    expect(notesZone()).not.toBeInTheDocument();
    fireEvent.click(button);
    expect(notesZone()).toBeInTheDocument();
    expect(await screen.findByRole("textbox", { name: "Notes" })).toHaveValue("First thoughts");
    expect(button).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(button);
    expect(notesZone()).not.toBeInTheDocument();
    expect(button).toHaveAttribute("aria-pressed", "false");
  });

  it("push: moves left by the coque's width + margin while the coque is open, back once closed", async () => {
    renderPage();
    const button = await fab();
    expect(rulesForElement(button)).not.toContain(PUSH_OFFSET);
    fireEvent.click(button);
    expect(rulesForElement(button)).toContain(PUSH_OFFSET);
    fireEvent.click(button);
    expect(rulesForElement(button)).not.toContain(PUSH_OFFSET);
  });

  it("overlay (narrow): no offset — the backdrop covers the page", async () => {
    useMediaQuery.mockReturnValue(true);
    renderPage();
    const button = await fab();
    fireEvent.click(button);
    expect(notesZone()).toBeInTheDocument();
    expect(rulesForElement(button)).not.toContain(PUSH_OFFSET);
  });
});

// ==============================|| THE DOT ||============================== //

describe("N5 — the Badge dot", () => {
  it("hidden at rest; shown while a note is pending; hidden once saved", async () => {
    renderPage();
    fireEvent.click(await fab());
    await screen.findByRole("textbox", { name: "Notes" });
    expect(dot()).toHaveClass("MuiBadge-invisible");
    fireEvent.change(notesBox(), { target: { value: "First thoughts, more" } });
    expect(dot()).not.toHaveClass("MuiBadge-invisible");
    expect(dot()).toHaveClass("MuiBadge-colorPrimary");
    await waitFor(() => expect(saveActivityNotes).toHaveBeenCalledTimes(1), {
      timeout: NOTES_AUTOSAVE_DELAY_MS + 2000,
    });
    await waitFor(() => expect(dot()).toHaveClass("MuiBadge-invisible"));
  });

  it("shown in ERROR colour when the save fails", async () => {
    saveActivityNotes.mockImplementation(async () => ({ success: false, error: "Network Error", status: 0 }));
    renderPage();
    fireEvent.click(await fab());
    await screen.findByRole("textbox", { name: "Notes" });
    fireEvent.change(notesBox(), { target: { value: "Lost connection" } });
    await waitFor(() => expect(dot()).toHaveClass("MuiBadge-colorError"), {
      timeout: NOTES_AUTOSAVE_DELAY_MS + 2000,
    });
    expect(dot()).not.toHaveClass("MuiBadge-invisible");
  });

  it("closing the panel (note flushed) → the dot goes", async () => {
    renderPage();
    const button = await fab();
    fireEvent.click(button);
    await screen.findByRole("textbox", { name: "Notes" });
    fireEvent.change(notesBox(), { target: { value: "Typed then closed" } });
    expect(dot()).not.toHaveClass("MuiBadge-invisible");
    fireEvent.click(button);
    expect(saveActivityNotesKeepalive).toHaveBeenCalledWith(ACT_ID, "Typed then closed", expect.any(Function));
    expect(dot()).toHaveClass("MuiBadge-invisible");
  });
});

// ==============================|| N6 — THE SOURCE BAND ||============================== //

const sourceHeader = () => screen.getByText("Source").closest("[aria-expanded]");
const sourceBody = () => sourceHeader().parentElement;
const openNotesPill = () => within(sourceHeader()).getByRole("button", { name: OPEN_NOTES_PILL_LABEL });

describe("N6 — the Source band: the note read-only, « Open notes »", () => {
  it("the band shows the note READ-ONLY", async () => {
    renderPage();
    await fab();
    fireEvent.click(screen.getByText("Source"));
    const note = within(sourceBody()).getByText("First thoughts");
    fireEvent.click(note);
    expect(within(sourceBody()).queryByDisplayValue("First thoughts")).toBeNull();
    expect(screen.queryByRole("textbox", { name: "Notes" })).toBeNull();
  });

  it("« Open notes » sits in the band header (folded band) and opens the SAME panel: the button shows it open", async () => {
    renderPage();
    const button = await fab();
    expect(sourceHeader()).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(openNotesPill());
    expect(notesZone()).toBeInTheDocument();
    expect(await screen.findByRole("textbox", { name: "Notes" })).toHaveValue("First thoughts");
    expect(button).toHaveAttribute("aria-pressed", "true");
    // the band header did not toggle
    expect(sourceHeader()).toHaveAttribute("aria-expanded", "false");
    // the button closes what the pill opened
    fireEvent.click(button);
    expect(notesZone()).not.toBeInTheDocument();
  });

  it("« Open notes » on an open panel keeps it as is (no remount: the pending note is not flushed)", async () => {
    renderPage();
    await fab();
    fireEvent.click(openNotesPill());
    await screen.findByRole("textbox", { name: "Notes" });
    fireEvent.change(notesBox(), { target: { value: "Being typed" } });
    fireEvent.click(openNotesPill());
    expect(saveActivityNotesKeepalive).not.toHaveBeenCalled();
    expect(notesBox()).toHaveValue("Being typed");
  });

  it("opened by the pill, the button's dot follows the panel", async () => {
    renderPage();
    await fab();
    fireEvent.click(openNotesPill());
    await screen.findByRole("textbox", { name: "Notes" });
    fireEvent.change(notesBox(), { target: { value: "Typed via the pill" } });
    expect(dot()).not.toHaveClass("MuiBadge-invisible");
  });

  it("a note typed in the panel shows in the band once saved", async () => {
    renderPage();
    await fab();
    fireEvent.click(screen.getByText("Source"));
    fireEvent.click(openNotesPill());
    await screen.findByRole("textbox", { name: "Notes" });
    fireEvent.change(notesBox(), { target: { value: "Decisions taken with the CISO" } });
    expect(within(sourceBody()).queryByText("Decisions taken with the CISO")).toBeNull();
    await waitFor(() => expect(saveActivityNotes).toHaveBeenCalledTimes(1), {
      timeout: NOTES_AUTOSAVE_DELAY_MS + 2000,
    });
    expect(await within(sourceBody()).findByText("Decisions taken with the CISO")).toBeInTheDocument();
  });
});
