// frontend/src/__tests__/nextSteps/ContextExternalContactsPage.test.jsx
//
// Sprint Next steps 5.8c (PO rule: a next step neither creates nor describes
// any person) — the deduced participants (B2, 5.8a/5.8b) are WITHDRAWN: the
// "External contacts" of the Context section, on the Activity workspace PAGE
// as really rendered, are the activity's own contacts (contacts_detail) again,
// even if a payload still carried `participants`. A contact row opens the
// Contact fiche in the coque, as before.
// The page, the Context section and the coque are REAL; the other bands and
// the data hooks are mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";
import { testTheme } from "../_utils/aphoriqTheme";

let mockActivity;
const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/activities/act-1",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("next/link", () => ({
  default: ({ href, children }) => <a href={typeof href === "string" ? href : "#"}>{children}</a>,
}));
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
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
vi.mock("sections/activities/workspace/ActivityPreparationTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityNotesTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivitySignalsTab", () => ({
  default: () => null,
  ACTIVITY_FLAT_TYPES: ["pain"],
}));
vi.mock("sections/activities/workspace/ActivityNextStepsTab", () => ({ default: () => null }));
vi.mock("components/signals/SignalsHaloBox", () => ({ default: ({ children }) => <>{children}</> }));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn(),
}));
// The Contact fiche (its own data hooks) is out of scope: a stand-in naming
// the contact it was opened for.
vi.mock("sections/activities/workspace/ContactDrawerContent", () => ({
  default: ({ contactId }) => <div data-testid="contact-fiche">{contactId}</div>,
}));

import ActivityWorkspacePage from "views/activities/workspace";

const render = (ui) => rtlRender(<WorkspaceCoque>{ui}</WorkspaceCoque>);

const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", full_name: "Thomas Lefèvre",
                 job_title: "CTO", department_name: "IT" };
const LAURENT = { id: "c-9", first_name: "Laurent", last_name: "Dubois", full_name: "Laurent Dubois",
                  job_title: "CISO", department_name: null };

const activityWith = (participants, over = {}) => ({
  id: "act-1", title: "Security review", activity_type: "MEETING", status: "PLANNED",
  account: "acc-1", account_detail: { id: "acc-1", company_name: "Acme" },
  owner_detail: null, invited_users_detail: [], contacts_detail: [THOMAS],
  decision_cycle: "dc-1", decision_cycle_detail: null, source_activity_detail: null,
  sequence_context: null, next_planned_step: null, participants, ...over,
});

const PARTICIPANTS = [
  { source: "CONTACT", contact: THOMAS, people: null },
  { source: "NEXT_STEP", contact: null,
    people: { id: "p-2", full_name: "Karim Benali", role: "UNKNOWN", role_display: "Unknown" } },
  { source: "NEXT_STEP", contact: LAURENT,
    people: { id: "p-3", full_name: "Laurent Dubois", role: "CHAMPION", role_display: "Champion" } },
];

// The column: its label (Typography) sits in the ColumnHeader Stack.
const external = () => screen.getByText("External contacts").parentElement.parentElement;

afterEach(() => cleanup());

describe("Context — External contacts are the activity's contacts (5.8c)", () => {
  it("the contacts only — a People from a next step is not listed", () => {
    mockActivity = activityWith(PARTICIPANTS);
    render(<ActivityWorkspacePage />);
    const col = external();
    expect(within(col).getByText("Thomas Lefèvre")).toBeInTheDocument();
    expect(within(col).queryByText("Karim Benali")).toBeNull();
    expect(within(col).queryByText("Laurent Dubois")).toBeNull();
    expect(within(col).queryByText(/no contact/)).toBeNull();
  });

  it("a contact opens the Contact fiche, as before", () => {
    mockActivity = activityWith(undefined);
    render(<ActivityWorkspacePage />);
    fireEvent.click(within(external()).getByText("Thomas Lefèvre"));
    expect(screen.getByTestId("contact-fiche")).toHaveTextContent("c-1");
  });
});

// 5.8h (4) + 5.9 (PO) — the owner in the Context section: « First Last ·
// Owner · email ». The "Internal team" column has no "Activity owner" title,
// so the « · Owner » marker stays HERE (only the creation drawer, whose
// caption says it, drops "owner").
describe("Context — the owner reads 'First Last · Owner · email'", () => {
  const OWNER = { id: "u-1", first_name: "Ann", last_name: "Owner", full_name: "Ann Owner",
                  email: "ann@acme.test" };
  const TEAMMATE = { id: "u-2", first_name: "Tess", last_name: "Mate", full_name: "Tess Mate",
                     email: "tess@acme.test" };

  it("the owner: name + « · Owner » + email, in the muted suffix", () => {
    mockActivity = activityWith(undefined, { owner_detail: OWNER, invited_users_detail: [TEAMMATE] });
    render(<ActivityWorkspacePage />);
    const name = screen.getByText("Ann Owner");
    const row = name.closest("p");
    expect(row.textContent).toBe("Ann Owner · Owner · ann@acme.test");
    expect(within(row).getByText(/Owner · ann@acme\.test/)).toHaveStyle({ color: testTheme.aphoriQ.text.muted });
  });

  it("an invited teammate keeps its row unchanged (« · invited », no email)", () => {
    mockActivity = activityWith(undefined, { owner_detail: OWNER, invited_users_detail: [TEAMMATE] });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("Tess Mate").closest("p").textContent).toBe("Tess Mate · invited");
  });
});

describe("Context — no owner email: « First Last · Owner »", () => {
  it("the marker stays without an email", () => {
    mockActivity = activityWith(undefined, {
      owner_detail: { id: "u-1", first_name: "Ann", last_name: "Owner", full_name: "Ann Owner" },
    });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("Ann Owner").closest("p").textContent).toBe("Ann Owner · Owner");
  });
});

// ==============================|| 5.9 — PROVENANCE FROM NEXT STEPS ||============================== //
//
// PO (5.9, widened): an activity coming from next steps shows, in the Origin
// group of Context, the CONVERSATIONS they came from — the one whose next step
// CREATED it and those whose next steps were LINKED to it — one line each
// (the server dedupes, sorts by date and leaves REJECTED out:
// activity.next_step_origins), with the existing ProvenanceLine shell +
// AccentLink: « From next step › <conversation> · <date> », click → the
// conversation.

describe("Context — provenance from next steps (5.9)", () => {
  const ORIGINS = [
    { id: "act-10", title: "Atelier business case", date: "2026-10-20" },
    { id: "act-11", title: "Call RSSI", date: "2026-11-03" },
  ];
  const lines = () => screen.queryAllByTestId("next-step-origin-line");

  it("one line per conversation, in the server's order, with its date", () => {
    mockActivity = activityWith(undefined, { next_step_origins: ORIGINS });
    render(<ActivityWorkspacePage />);
    expect(lines().map((l) => l.textContent)).toEqual([
      "From next step › Atelier business case · 20 Oct 2026",
      "From next step › Call RSSI · 3 Nov 2026",
    ]);
  });

  it("a click → the conversation (the existing AccentLink)", () => {
    mockActivity = activityWith(undefined, { next_step_origins: ORIGINS });
    render(<ActivityWorkspacePage />);
    const link = within(lines()[0]).getByRole("link", { name: "Atelier business case" });
    expect(link).toHaveAttribute("href", "/activities/act-10");
  });

  it("the ProvenanceLine shell: the branch icon, the muted text", () => {
    mockActivity = activityWith(undefined, { next_step_origins: ORIGINS });
    render(<ActivityWorkspacePage />);
    const line = lines()[0];
    expect(line.querySelector(".anticon-branches")).not.toBeNull();
    expect(within(line).getByText(/From next step/)).toHaveStyle({ color: testTheme.aphoriQ.text.muted });
  });

  it("an undated conversation: no date", () => {
    mockActivity = activityWith(undefined, {
      next_step_origins: [{ id: "act-12", title: "Notes sans date", date: null }],
    });
    render(<ActivityWorkspacePage />);
    expect(lines().map((l) => l.textContent)).toEqual(["From next step › Notes sans date"]);
  });

  it("with a campaign provenance too: both, the campaign line first", () => {
    mockActivity = activityWith(undefined, {
      next_step_origins: ORIGINS.slice(0, 1),
      source_activity_detail: {
        id: "act-5", title: "Cold call", source_context: { type: "CAMPAIGN", id: "camp-1", name: "Q4 push" },
      },
    });
    render(<ActivityWorkspacePage />);
    const campaign = screen.getByText(/From campaign/);
    expect(campaign.compareDocumentPosition(lines()[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(lines()).toHaveLength(1);
  });

  // 5.9b (1) — a conversation already shown by the provenance line
  // (source_activity) is not shown a second time as « From next step ».
  it("the conversation of the provenance line is not repeated", () => {
    mockActivity = activityWith(undefined, {
      next_step_origins: ORIGINS,
      source_activity_detail: {
        id: "act-10", title: "Atelier business case",
        source_context: { type: "DECISION_CYCLE", id: "dc-1", name: "Deal Acme" },
      },
    });
    render(<ActivityWorkspacePage />);
    expect(lines().map((l) => l.textContent)).toEqual(["From next step › Call RSSI · 3 Nov 2026"]);
    expect(screen.getAllByRole("link", { name: "Atelier business case" })).toHaveLength(1);
  });

  it("a provenance without source activity (a DC directly) filters nothing", () => {
    mockActivity = activityWith(undefined, {
      next_step_origins: ORIGINS,
      source_activity_detail: {
        id: null, title: null,
        source_context: { type: "DECISION_CYCLE", id: "dc-1", name: "Deal Acme" },
      },
    });
    render(<ActivityWorkspacePage />);
    expect(lines()).toHaveLength(2);
  });

  it("no next step origin and no other provenance: no Origin group", () => {
    mockActivity = activityWith(undefined, { next_step_origins: [] });
    const { container } = render(<ActivityWorkspacePage />);
    expect(lines()).toHaveLength(0);
    expect(container.querySelector('[data-testid="ctx-card"] .anticon-branches')).toBeNull();
  });
});

// 5.9b (2) — the shared label: an owner truly without a name reads its email
// ONCE (« email · Owner »), never « email · Owner · email ».
describe("Context — an owner without a name: the email once (5.9b)", () => {
  it("« ann@acme.test · Owner »", () => {
    mockActivity = activityWith(undefined, {
      owner_detail: { id: "u-1", first_name: "", last_name: "", full_name: "", email: "ann@acme.test" },
    });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("ann@acme.test").closest("p").textContent).toBe("ann@acme.test · Owner");
  });
});

// ==============================|| 5.12 — PREVIOUS / NEXT IN CONTEXT ||============================== //
//
// PO (5.12 A-bis): NO card in Context. The Origin group goes in TWO columns
// (5.12c: labelled « Previous activity » / « Next planned activity »),
// on the exact model of the People group (same column labels, same grid, same
// stacking when narrow):
//   left « Previous activity »: the provenance lines, unchanged;
//   right « Next planned activity »: ONE line on the ProvenanceRow shell, the
//   provenance typography — type icon · title · step · short date (+ the
//   existing "Overdue" label), the title → /activities/<id>. No card, no pill.
// A campaign activity whose DC was born: the line carries the DC
// (« In decision cycle <name> › … »); nothing open in it: the DC name alone.
// One column → it alone; none → no group. No new query
// (activity.next_planned_step, the server).

describe("Context — the previous / next group, two columns (5.12 A-bis)", () => {
  const ORIGIN = { id: "act-10", title: "Atelier business case", date: "2026-10-20" };
  const PLANNED = {
    id: "act-20", title: "Security workshop", activity_type: "MEETING", status: "PLANNED",
    scheduled_date: "2026-11-12", decision_step_name: "Technical Fit", is_overdue: false,
  };
  const ctx = () => screen.getByTestId("ctx-card");
  const group = () => within(ctx()).queryByTestId("ctx-prev-next");
  const nextLine = () => within(group()).getByTestId("next-planned-line");
  const planned = (activity = PLANNED, over = {}) => ({
    next_planned_step: { source: "CAMPAIGN", decision_cycle: null, activity, ...over },
  });

  it("only the next: the « Next planned activity » column alone, ONE line", () => {
    mockActivity = activityWith(undefined, { next_step_origins: [], ...planned() });
    render(<ActivityWorkspacePage />);
    expect(within(group()).getByText("Next planned activity")).toBeInTheDocument();
    expect(within(group()).queryByText("Previous activity")).toBeNull();
    expect(nextLine().textContent).toBe("Security workshop · Technical Fit · 12 Nov 2026");
  });

  it("no card, no status pill in Context", () => {
    mockActivity = activityWith(undefined, planned());
    render(<ActivityWorkspacePage />);
    expect(within(ctx()).queryByTestId("activity-mini-card")).toBeNull();
    expect(within(ctx()).queryByTestId("status-pill")).toBeNull();
  });

  it("the ProvenanceRow shell: the TYPE icon, the muted provenance typography", () => {
    mockActivity = activityWith(undefined, planned());
    render(<ActivityWorkspacePage />);
    expect(nextLine().querySelector(".anticon-team")).not.toBeNull();
    expect(nextLine().querySelector(".anticon-branches")).toBeNull();
    const body = nextLine().querySelector("p");
    expect(body).toHaveStyle({ color: testTheme.aphoriQ.text.muted });
    expect(body).toHaveClass("MuiTypography-body2");
  });

  it("the title → the planned activity (the provenance AccentLink)", () => {
    mockActivity = activityWith(undefined, planned());
    render(<ActivityWorkspacePage />);
    expect(within(nextLine()).getByRole("link", { name: "Security workshop" }))
      .toHaveAttribute("href", "/activities/act-20");
  });

  it("an overdue activity: the existing « Overdue » label in the line", () => {
    mockActivity = activityWith(undefined, planned({ ...PLANNED, is_overdue: true }));
    render(<ActivityWorkspacePage />);
    expect(nextLine().textContent).toBe("Security workshop · Technical Fit · 12 Nov 2026 · Overdue");
  });

  // 5.12c (1) — the « Overdue » of the line in red: the existing
  // ACTIVITY_OVERDUE_CHIP_COLORS.text (the overdue status pill's colour).
  it("the « Overdue » label in red (ACTIVITY_OVERDUE_CHIP_COLORS.text)", () => {
    mockActivity = activityWith(undefined, planned({ ...PLANNED, is_overdue: true }));
    render(<ActivityWorkspacePage />);
    const overdue = within(nextLine()).getByText("Overdue");
    expect(overdue).toHaveStyle({ color: testTheme.palette.error.main });
    expect(within(nextLine()).getByText(/Technical Fit/)).not.toHaveStyle({ color: testTheme.palette.error.main });
  });

  it("no step, no date: the title alone", () => {
    mockActivity = activityWith(undefined, planned({ ...PLANNED, decision_step_name: null, scheduled_date: null }));
    render(<ActivityWorkspacePage />);
    expect(nextLine().textContent).toBe("Security workshop");
  });

  it("only the previous: the « Previous activity » column alone, the provenance lines unchanged", () => {
    mockActivity = activityWith(undefined, { next_step_origins: [ORIGIN] });
    render(<ActivityWorkspacePage />);
    expect(within(group()).getByText("Previous activity")).toBeInTheDocument();
    expect(within(group()).queryByText("Next planned activity")).toBeNull();
    expect(within(group()).getByTestId("next-step-origin-line").textContent)
      .toBe("From next step › Atelier business case · 20 Oct 2026");
  });

  it("both: the People grid, « Previous activity » left then « Next planned activity » right", () => {
    mockActivity = activityWith(undefined, { next_step_origins: [ORIGIN], ...planned() });
    render(<ActivityWorkspacePage />);
    const grid = within(group()).getByTestId("ctx-grid");
    const [left, right] = Array.from(grid.children);
    expect(grid.children).toHaveLength(2);
    expect(within(left).getByText("Previous activity")).toBeInTheDocument();
    expect(within(left).getByTestId("next-step-origin-line")).toBeInTheDocument();
    expect(within(right).getByText("Next planned activity")).toBeInTheDocument();
    expect(within(right).getByTestId("next-planned-line")).toBeInTheDocument();
  });

  it("the column labels are the People ones (same ColumnHeader)", () => {
    mockActivity = activityWith(undefined, { next_step_origins: [ORIGIN], ...planned() });
    render(<ActivityWorkspacePage />);
    const people = screen.getByText("Internal team");
    for (const label of ["Previous activity", "Next planned activity"]) {
      const el = within(group()).getByText(label);
      expect(el.tagName).toBe(people.tagName);
      expect(el.className).toBe(people.className);
      expect(el.parentElement.className).toBe(people.parentElement.className);
    }
  });

  it("a DC born from the campaign activity: « In decision cycle <DC> › … »", () => {
    mockActivity = activityWith(undefined, planned({ ...PLANNED, title: "Send pricing" }, {
      source: "BORN_DECISION_CYCLE", decision_cycle: { id: "dc-7", name: "Deal Logistix" },
    }));
    render(<ActivityWorkspacePage />);
    expect(nextLine().textContent)
      .toBe("In decision cycle Deal Logistix › Send pricing · Technical Fit · 12 Nov 2026");
    expect(within(nextLine()).getByRole("link", { name: "Deal Logistix" }))
      .toHaveAttribute("href", "/accounts/acc-1/dc/dc-7?tab=timeline");
  });

  it("a born DC with nothing open: the DC name alone", () => {
    mockActivity = activityWith(undefined, planned(null, {
      source: "BORN_DECISION_CYCLE", decision_cycle: { id: "dc-7", name: "Deal Logistix" },
    }));
    render(<ActivityWorkspacePage />);
    expect(nextLine().textContent).toBe("In decision cycle Deal Logistix");
  });

  it("none: no group at all (only the People hairline)", () => {
    mockActivity = activityWith(undefined, { next_step_origins: [], next_planned_step: null });
    render(<ActivityWorkspacePage />);
    expect(group()).toBeNull();
    expect(within(ctx()).getAllByTestId("ctx-sep")).toHaveLength(1);
  });

  it("a next planned step without activity nor DC: as « none »", () => {
    mockActivity = activityWith(undefined, planned(null));
    render(<ActivityWorkspacePage />);
    expect(group()).toBeNull();
  });
});
