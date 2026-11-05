// frontend/src/__tests__/nextSteps/PersonSignalsPage.test.jsx
//
// Sprint « Cycle de vie des contacts », 8g-6 (TD-232) — « See signals » on the
// Activity workspace PAGE: a contact OR a non-converted stakeholder of the
// « External team » → its fiche → « See signals » → THEN (never before) one
// request to the aggregated endpoint: the account's signals of the activities
// this person took part in (contact / stakeholder filter), PENDING + VALIDATED
// only (no rejected), the 8 qualification types only (no next steps).
// Read-only list « Signals from conversations with <name> »; a click opens the
// signal detail; Back returns to the person's fiche.
// The page, the Context section, the fiches, the list, the detail and the
// coque are REAL; the data hooks are mocked (harness of
// ContextStakeholdersPage.test.jsx). The server side (tenant / account /
// rejected / next steps) is tested on the real endpoint
// (test_aggregated_stakeholder_filter.py, test_aggregated_signals_endpoint.py).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup, within } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";
import { sectionTitles } from "../_utils/sectionHeaders";

let mockActivity;
const mockAggregated = vi.fn();

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
// The aggregated endpoint, recorded: a person query returns its signals.
vi.mock("api/signals/aggregatedSignals", () => ({
  default: (args) => {
    mockAggregated(args);
    const person = args?.contact || args?.stakeholder;
    return { signals: person ? PERSON_SIGNALS : [], loading: false };
  },
}));
vi.mock("api/signals/signals", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetSignalChoices: () => ({ choices: {}, choicesLoading: false }),
}));
vi.mock("api/businessData/contacts", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetContact: (id) => ({ contact: id ? THOMAS : null, contactLoading: false, contactError: null }),
}));
vi.mock("api/accounts/decisionCycles", async (importOriginal) => ({
  ...(await importOriginal()),
  useGetDCPeople: () => ({ people: { qualified: [], unqualified: [] }, peopleLoading: false }),
}));
vi.mock("hooks/usePipelineRunner", () => ({ default: () => ({ state: {} }) }));
vi.mock("contexts/BreadcrumbContext", () => ({ useBreadcrumb: () => ({ setCrumbs: vi.fn() }) }));
vi.mock("components/WorkspaceHeader", () => ({ default: () => <div data-testid="header" /> }));
vi.mock("sections/activities/workspace/ActivityHeader", () => ({ default: () => ({ modals: null }) }));
vi.mock("sections/activities/workspace/ActivityPreparationTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityNotesTab", () => ({ default: () => null }));
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

import ActivityWorkspacePage from "views/activities/workspace";
import { QUALIFICATION_SIGNAL_TYPES } from "utils/signalTypes";

const render = (ui) => rtlRender(<WorkspaceCoque>{ui}</WorkspaceCoque>);

const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", full_name: "Thomas Lefèvre",
                 job_title: "CTO", department_name: "IT", email: "t@acme.io", is_reachable: true };
const MARC = { id: "st-marc", display_name: "Marc", full_name: "Marc", department: { id: 7, name: "Finance" },
               is_linked: false, is_reachable: false, role: "CHAMPION", role_display: "Champion",
               influence_display: "High" };
const PERSON_SIGNALS = [
  { id: "p-1", status: "PENDING", signal_type: "pain", _signalType: "pain",
    summary: "Reporting takes three weeks", what_display: "Data", dimension_display: "Time",
    created_at: "2026-11-01T10:00:00Z", source_context: { contacts: [] } },
];

const activity = () => ({
  id: "act-1", title: "Security review", activity_type: "MEETING", status: "PLANNED",
  account: "11111111-1111-4111-8111-111111111111",
  account_detail: { id: "11111111-1111-4111-8111-111111111111", company_name: "Acme" },
  owner_detail: null, invited_users_detail: [], contacts_detail: [THOMAS], stakeholders_detail: [MARC],
  decision_cycle: "dc-1", decision_cycle_detail: null, source_activity_detail: null,
  sequence_context: null, next_planned_step: null,
});
const ACCOUNT_ID = "11111111-1111-4111-8111-111111111111";

const personCalls = () => mockAggregated.mock.calls.map(([a]) => a).filter((a) => a?.contact || a?.stakeholder);
const coque = () => screen.getByTestId("coque-panel");
const seeSignals = () => fireEvent.click(within(coque()).getByText("See signals"));

afterEach(() => { cleanup(); mockAggregated.mockClear(); });

describe("« See signals » — a contact (8g-6)", () => {
  it("no request before the click; one after: account + contact, PENDING + VALIDATED, the 8 qualification types", async () => {
    mockActivity = activity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByText("Thomas Lefèvre"));
    await screen.findByTestId("contact-identity-row");
    expect(personCalls()).toEqual([]);
    seeSignals();
    expect(await within(coque()).findByText("Reporting takes three weeks")).toBeInTheDocument();
    const [args] = personCalls().slice(-1);
    expect(args).toMatchObject({ accountId: ACCOUNT_ID, contact: "c-1", statuses: ["PENDING", "VALIDATED"] });
    expect(args.signalTypes).toEqual(QUALIFICATION_SIGNAL_TYPES);
    expect(args.signalTypes).not.toContain("next-steps");
    expect(args.statuses).not.toContain("REJECTED");
    expect(within(coque()).getByText("Signals from conversations with Thomas Lefèvre")).toBeInTheDocument();
  });

  it("read-only: no validate / reject on the rows", async () => {
    mockActivity = activity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByText("Thomas Lefèvre"));
    seeSignals();
    await within(coque()).findByText("Reporting takes three weeks");
    expect(within(coque()).queryByLabelText("Validate signal")).toBeNull();
    expect(within(coque()).queryByLabelText("Reject signal")).toBeNull();
  });

  it("Back returns to the contact's fiche", async () => {
    mockActivity = activity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByText("Thomas Lefèvre"));
    seeSignals();
    await within(coque()).findByText("Reporting takes three weeks");
    fireEvent.click(within(coque()).getByRole("button", { name: "Back" }));
    expect(await within(coque()).findByTestId("contact-identity-row")).toBeInTheDocument();
  });

  it("a click opens the signal's detail (read-only); its Back returns to the fiche", async () => {
    mockActivity = activity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByText("Thomas Lefèvre"));
    seeSignals();
    fireEvent.click(await within(coque()).findByText("Reporting takes three weeks"));
    expect(await within(coque()).findByTestId("pain-summary-box")).toBeInTheDocument();
    expect(within(coque()).queryByRole("button", { name: /Validate/ })).toBeNull();
    fireEvent.click(within(coque()).getByRole("button", { name: "Back" }));
    expect(await within(coque()).findByTestId("contact-identity-row")).toBeInTheDocument();
  });
});

describe("« See signals » — a non-converted stakeholder (8g-6)", () => {
  it("a click in « External team » opens its fiche: the contact fiche's sections, its role", async () => {
    mockActivity = activity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByText("Marc"));
    const panel = await screen.findByTestId("coque-panel");
    expect(sectionTitles(panel)).toEqual(["Identity", "Contact", "Role in the decision"]);
    expect(within(panel).getByTestId("contact-role")).toHaveTextContent("Champion");
    expect(within(panel).getByText("See signals")).toBeInTheDocument();
    expect(within(panel).queryByRole("button", { name: /Edit/ })).toBeNull();
  });

  it("no request before the click; one after: account + stakeholder; Back → its fiche", async () => {
    mockActivity = activity();
    render(<ActivityWorkspacePage />);
    fireEvent.click(screen.getByText("Marc"));
    await screen.findByTestId("coque-panel");
    expect(personCalls()).toEqual([]);
    seeSignals();
    expect(await within(coque()).findByText("Reporting takes three weeks")).toBeInTheDocument();
    const [args] = personCalls().slice(-1);
    expect(args).toMatchObject({ accountId: ACCOUNT_ID, stakeholder: "st-marc", statuses: ["PENDING", "VALIDATED"] });
    expect(args.contact).toBeUndefined();
    expect(args.signalTypes).toEqual(QUALIFICATION_SIGNAL_TYPES);
    expect(within(coque()).getByText("Signals from conversations with Marc")).toBeInTheDocument();
    fireEvent.click(within(coque()).getByRole("button", { name: "Back" }));
    expect(await within(coque()).findByTestId("contact-role")).toHaveTextContent("Champion");
  });
});
