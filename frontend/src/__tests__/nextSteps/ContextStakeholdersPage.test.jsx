// frontend/src/__tests__/nextSteps/ContextStakeholdersPage.test.jsx
//
// Sprint « Cycle de vie des contacts », étape 7 (4) / 7c / 7d-2 — the Context
// section of the Activity workspace PAGE, column « External team » (7d-2: the
// pair of « Internal team »; no « Not yet a contact » marker — no distinction
// shown at the activity level):
// the SAME list as the drawer = the activity's contacts + its non-converted DC
// stakeholders; a department-only stakeholder shows the department only. The « no way to contact » alert: PER contact participant without email
// nor phone (contacts_detail.is_reachable, computed by the server), ONLY for
// PEOPLE_ACTIVITY_TYPES, in orange (information, not an error).
// The page, the Context section and the coque are REAL; the other bands and
// the data hooks are mocked (harness of ContextExternalContactsPage.test.jsx).

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
// The Source band's Run AI pill (its header, lot 3 / 11) — not under test here.
vi.mock("sections/activities/workspace/RunAIAnalysisButton", () => ({ default: () => null }));
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


const MARC = { id: "st-marc", display_name: "Marc", full_name: "Marc", department: null, is_linked: false };
const FINANCE = { id: "st-fin", display_name: "Finance", full_name: "", is_linked: false,
                  department: { id: 7, name: "Finance" } };
const NOWAY = { id: "c-2", first_name: "Nina", last_name: "Noway", full_name: "Nina Noway",
                job_title: null, department_name: null, is_reachable: false };
const REACHABLE = { ...THOMAS, is_reachable: true };

const styleText = () => Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
const classesOf = (el) => (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
const column = () => screen.getByText("External team").parentElement.parentElement;
const MENTION = "No email or phone";

afterEach(() => cleanup());

describe("Context — « External team » = contacts + non-converted stakeholders, unmarked (7c / 7d-2)", () => {
  it("the column header reads « External team », the pair of « Internal team »", () => {
    mockActivity = activityWith(undefined, { contacts_detail: [REACHABLE], stakeholders_detail: [MARC] });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("External team")).toBeInTheDocument();
    expect(screen.getByText("Internal team")).toBeInTheDocument();
    expect(screen.queryByText("Stakeholders")).toBeNull();
    expect(screen.queryByText("External contacts")).toBeNull();
  });

  it("lists the contacts and the stakeholders, no « Not yet a contact » marker", () => {
    mockActivity = activityWith(undefined, { contacts_detail: [REACHABLE], stakeholders_detail: [MARC] });
    render(<ActivityWorkspacePage />);
    const col = column();
    expect(within(col).getByText("Thomas Lefèvre")).toBeInTheDocument();
    expect(within(col).getByTestId("ctx-stakeholder-st-marc")).toHaveTextContent("Marc");
    expect(within(col).getByTestId("ctx-stakeholder-st-marc").textContent).toBe("Marc");
    expect(col.textContent).not.toMatch(/Not yet a contact/);
  });

  it("a department-only stakeholder shows the department only", () => {
    mockActivity = activityWith(undefined, { contacts_detail: [], stakeholders_detail: [FINANCE] });
    render(<ActivityWorkspacePage />);
    const row = within(column()).getByTestId("ctx-stakeholder-st-fin");
    expect(row.textContent).toBe("Finance");
    expect(within(column()).queryByText("No contacts linked")).toBeNull();
  });

  it("a stakeholder opens no contact fiche", () => {
    mockActivity = activityWith(undefined, { contacts_detail: [], stakeholders_detail: [MARC] });
    render(<ActivityWorkspacePage />);
    fireEvent.click(within(column()).getByTestId("ctx-stakeholder-st-marc"));
    expect(screen.queryByTestId("contact-fiche")).toBeNull();
  });
});

describe("Context — the « no way to contact » alert (étape 7)", () => {
  it("a MEETING: an orange alert on the contact without email nor phone only", () => {
    mockActivity = activityWith(undefined, { contacts_detail: [REACHABLE, NOWAY] });
    render(<ActivityWorkspacePage />);
    const alert = within(column()).getByTestId("ctx-no-contact-means-c-2");
    expect(alert).toHaveTextContent(MENTION);
    expect(alert).toHaveStyle({ color: testTheme.palette.warning.main });
    expect(within(column()).queryByTestId("ctx-no-contact-means-c-1")).toBeNull();
  });

  it.each(["CALL", "EMAIL", "DEMO"])("a %s carries the alert too", (type) => {
    mockActivity = activityWith(undefined, { activity_type: type, contacts_detail: [NOWAY] });
    render(<ActivityWorkspacePage />);
    expect(within(column()).getByTestId("ctx-no-contact-means-c-2")).toBeInTheDocument();
  });

  // 8b-2 (PO): EVERY participant without email nor phone — a contact OR a
  // non-converted stakeholder (is_reachable false, server-side): ONE message,
  // the same for both, the same component, no distinction.
  it("a non-converted stakeholder carries the SAME alert as a contact", () => {
    mockActivity = activityWith(undefined, {
      contacts_detail: [NOWAY],
      stakeholders_detail: [{ ...MARC, is_reachable: false }, { ...FINANCE, is_reachable: false }],
    });
    render(<ActivityWorkspacePage />);
    const contactAlert = within(column()).getByTestId("ctx-no-contact-means-c-2");
    for (const id of ["st-marc", "st-fin"]) {
      const alert = within(column()).getByTestId(`ctx-no-contact-means-${id}`);
      expect(alert.textContent).toBe(contactAlert.textContent);
      expect(alert.textContent).toBe(MENTION);
      expect(alert).toHaveStyle({ color: testTheme.palette.warning.main });
      expect(alert.innerHTML).toBe(contactAlert.innerHTML);   // the same component
    }
  });

  // 8c-2 (PO): the alert on the SAME line as the person from md, under it on
  // a narrow screen (the responsive Stack direction pattern; the generated
  // media rule read as in NextStepsStripPage.test.jsx).
  it.each([["c-2", "contact"], ["st-marc", "stakeholder"]])(
    "%s (%s): the alert beside the person from md, under it below md",
    (id) => {
      mockActivity = activityWith(undefined, {
        contacts_detail: [NOWAY], stakeholders_detail: [{ ...MARC, is_reachable: false }],
      });
      render(<ActivityWorkspacePage />);
      const alert = within(column()).getByTestId(`ctx-no-contact-means-${id}`);
      const line = alert.parentElement;
      expect(line).toHaveAttribute("data-testid", "ctx-person-line");
      expect(line).toHaveStyle({ display: "flex", flexDirection: "column" });     // narrow
      const css = styleText();
      expect(classesOf(line).some((c) =>
        new RegExp(`@media \\(min-width:900px\\)\\{\\.${c}\\{[^}]*flex-direction:row`).test(css),
      )).toBe(true);                                                              // from md
    },
  );

  it("a stakeholder in a TASK carries no alert", () => {
    mockActivity = activityWith(undefined, {
      activity_type: "TASK", contacts_detail: [], stakeholders_detail: [{ ...MARC, is_reachable: false }],
    });
    render(<ActivityWorkspacePage />);
    expect(within(column()).queryByTestId("ctx-no-contact-means-st-marc")).toBeNull();
  });

  it.each(["TASK", "LINKEDIN", "OTHER"])("a %s carries no alert", (type) => {
    mockActivity = activityWith(undefined, { activity_type: type, contacts_detail: [NOWAY] });
    render(<ActivityWorkspacePage />);
    expect(within(column()).queryByTestId("ctx-no-contact-means-c-2")).toBeNull();
  });
});
