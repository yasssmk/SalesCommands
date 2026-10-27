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

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "act-1" }),
  useRouter: () => ({ push: vi.fn() }),
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

// 5.8h (4) — the owner in the Context section: « First Last · email », never
// "· owner" (the column says it) — the same rule as the activity drawer.
describe("Context — the owner reads 'First Last · email' (5.8h)", () => {
  const OWNER = { id: "u-1", first_name: "Ann", last_name: "Owner", full_name: "Ann Owner",
                  email: "ann@acme.test" };
  const TEAMMATE = { id: "u-2", first_name: "Tess", last_name: "Mate", full_name: "Tess Mate",
                     email: "tess@acme.test" };

  it("the owner: name + email in the muted suffix, no '· owner'", () => {
    mockActivity = activityWith(undefined, { owner_detail: OWNER, invited_users_detail: [TEAMMATE] });
    render(<ActivityWorkspacePage />);
    const name = screen.getByText("Ann Owner");
    const row = name.closest("p");
    expect(row).toHaveTextContent("Ann Owner · ann@acme.test");
    expect(row.textContent).not.toMatch(/· owner/);
    expect(screen.queryByText(/· owner/)).toBeNull();
    expect(within(row).getByText(/ann@acme\.test/)).toHaveStyle({ color: testTheme.aphoriQ.text.muted });
  });

  it("an invited teammate keeps its row unchanged (« · invited », no email)", () => {
    mockActivity = activityWith(undefined, { owner_detail: OWNER, invited_users_detail: [TEAMMATE] });
    render(<ActivityWorkspacePage />);
    expect(screen.getByText("Tess Mate").closest("p").textContent).toBe("Tess Mate · invited");
  });
});
