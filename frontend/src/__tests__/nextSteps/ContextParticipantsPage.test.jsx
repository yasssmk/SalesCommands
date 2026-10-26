// frontend/src/__tests__/nextSteps/ContextParticipantsPage.test.jsx
//
// Sprint Next steps 5.8b (PO decision B2) — the Context section of the Activity
// workspace PAGE as really rendered shows the activity's DEDUCED participants
// (activity.participants, backend 5.8a) in "External contacts", with the
// existing PersonRow:
//   - a participant with a contact = as today: its row opens the Contact fiche
//     (ContactDrawerContent) in the coque;
//   - a People WITHOUT contact = a NON-interactive PersonRow, suffix
//     "<role_display> · no contact" (the job / department muted style); a click
//     does nothing (option A).
// The page, the Context section and the coque are REAL; the other bands and
// the data hooks are mocked.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";

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

describe("Context — the deduced participants in External contacts (5.8b)", () => {
  it("lists the participants: the contacts, then the People of the next steps", () => {
    mockActivity = activityWith(PARTICIPANTS);
    render(<ActivityWorkspacePage />);
    const col = external();
    expect(within(col).getByText("Thomas Lefèvre")).toBeInTheDocument();
    expect(within(col).getByText("Karim Benali")).toBeInTheDocument();
    expect(within(col).getByText("Laurent Dubois")).toBeInTheDocument();
  });

  it("a participant with a contact opens the Contact fiche, as today", () => {
    mockActivity = activityWith(PARTICIPANTS);
    render(<ActivityWorkspacePage />);
    fireEvent.click(within(external()).getByText("Laurent Dubois"));
    expect(screen.getByTestId("contact-fiche")).toHaveTextContent("c-9");
  });

  it("a People without contact: '<role> · no contact', not clickable", () => {
    mockActivity = activityWith(PARTICIPANTS);
    render(<ActivityWorkspacePage />);
    const karim = within(external()).getByText("Karim Benali");
    expect(karim.closest("p").textContent).toBe("Karim Benali · Unknown · no contact");
    expect(karim).not.toHaveAttribute("role", "button");
    fireEvent.click(karim);
    expect(screen.queryByTestId("contact-fiche")).not.toBeInTheDocument();
  });

  it("without participants in the payload, the contacts as before", () => {
    mockActivity = activityWith(undefined);
    render(<ActivityWorkspacePage />);
    expect(within(external()).getByText("Thomas Lefèvre")).toBeInTheDocument();
    expect(within(external()).queryByText("Karim Benali")).toBeNull();
  });
});
