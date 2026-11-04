// frontend/src/__tests__/nextSteps/ActivityCreateDefaultsPage.test.jsx
//
// Sprint « Cycle de vie des contacts », étape 7c (3) — on the Activity
// workspace PAGE, an activity created FROM an activity (« + Add next step »,
// ✓ Create of a next step) gets its defaults from the type and the origin:
//   * the date field follows the type (SCHEDULED_DATE_ACTIVITY_TYPES MEETING /
//     CALL / DEMO -> scheduled date; TASK and the others -> due date) — and
//     keeps following it when the type changes; still modifiable;
//   * the decision step: « + Add next step » -> the origin activity's step;
//     ✓ Create -> the next step's suggested step when it is a step of the DC,
//     else the origin activity's step (backend mirror,
//     next_step_materialization.next_step_step_default).
// REAL: the page, the Next steps band, the validation flow, the coque, the
// creation drawer, the API hooks (SWR fetcher). Mocked: the HTTP client.
// Harness of DrawerStakeholdersPage.test.jsx.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, within, fireEvent, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import WorkspaceCoque from "../_utils/workspaceCoque";

const ACT_ID = "11111111-1111-4111-8111-111111111111";
const ACC_ID = "22222222-2222-4222-8222-222222222222";
const NS_ID = "77777777-7777-4777-8777-777777777777";

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
vi.mock("sections/activities/workspace/ActivityNotesTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivitySignalsTab", () => ({
  default: () => null,
  ACTIVITY_FLAT_TYPES: ["pain"],
}));
vi.mock("components/signals/SignalsHaloBox", () => ({ default: ({ children }) => <>{children}</> }));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn() }));

import ActivityWorkspacePage from "views/activities/workspace";
import { api } from "utils/axiosClient";

const DC_ID = "44444444-4444-4444-8444-444444444444";
const STEP_Q = "55555555-5555-4555-8555-555555555551";
const STEP_BC = "55555555-5555-4555-8555-555555555552";
const STEP_P = "55555555-5555-4555-8555-555555555553";
const STEPS = [
  { id: STEP_Q, name: "Qualification", order: 1, is_current: true, cycle: DC_ID },
  { id: STEP_BC, name: "Business case", order: 2, is_current: false, cycle: DC_ID },
  { id: STEP_P, name: "Proposal", order: 3, is_current: false, cycle: DC_ID },
];
const OWNER = { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" };
const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", full_name: "Thomas Lefèvre" };

// The ORIGIN activity: in the DC, on « Business case » — NOT the current step.
const originActivity = (over = {}) => ({
  id: ACT_ID, title: "Discovery call", activity_type: "CALL", status: "COMPLETED",
  outcome: "FOLLOW_UP_NEEDED", scheduled_date: "2026-10-20",
  account: ACC_ID, account_detail: { id: ACC_ID, company_name: "Acme" },
  owner_detail: OWNER, invited_users_detail: [], contacts_detail: [THOMAS],
  decision_cycle: DC_ID, decision_cycle_detail: { id: DC_ID, name: "Deal Acme" },
  decision_step: STEP_BC, decision_step_detail: { id: STEP_BC, name: "Business case" },
  campaign_detail: null, source_activity_detail: null,
  next_step_origins: [], next_planned_step: null, transcript: "", outcome_notes: "",
  call_to_action: "", description: "",
  ...over,
});
const nextStep = (over = {}) => ({
  id: NS_ID, _signalType: "next-steps", signal_type: "next-steps", status: "PENDING",
  source: "LLM_EXTRACTED", suggested_title: "Security review", suggested_activity_type: "MEETING",
  suggested_due_date: null, suggested_decision_step: null, decision_cycle: DC_ID,
  source_activity: ACT_ID, confidence: 0.8, created_at: "2026-10-28T10:00:00Z",
  suggested_people: [], suggested_people_names: [],
  ...over,
});

let serverActivity;
// The names a next step cites, with what the server matched (étape 8).
let mockCited = [];
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  if (url.startsWith(`/module-activities/${ACT_ID}`)) return Promise.resolve({ data: serverActivity });
  if (url.startsWith(`/decision_cycles/by-account/${ACC_ID}`)) {
    return Promise.resolve({ data: { results: [{ id: DC_ID, name: "Deal Acme", outcome: null }], count: 1 } });
  }
  if (url.startsWith("/decision_cycles/steps/")) {
    return Promise.resolve({ data: { results: url.includes(DC_ID) ? STEPS : [], count: 3 } });
  }
  if (url.startsWith(`/decision_cycles/${DC_ID}/stakeholders/`)) return Promise.resolve({ data: [] });
  if (url.startsWith(`/module-signals/next-steps/${NS_ID}/link-candidates`)) {
    return Promise.resolve({ data: { candidates: [], proposed_activity_id: null } });
  }
  if (url.startsWith(`/module-signals/next-steps/${NS_ID}/cited-contacts`)) {
    return Promise.resolve({ data: { cited: mockCited } });
  }
  return Promise.resolve({ data: { results: [], count: 0 } });
};

const renderPage = (a = originActivity()) => {
  serverActivity = a;
  return render(
    <SWRConfig value={{ fetcher, dedupingInterval: 0, provider: () => new Map() }}>
      <WorkspaceCoque>
        <ActivityWorkspacePage />
      </WorkspaceCoque>
    </SWRConfig>,
  );
};

const coque = () => screen.getByTestId("coque-panel");

// « + Add next step » → the type pill → the creation drawer.
const addNextStep = async (typeLabel) => {
  fireEvent.click(await screen.findByRole("button", { name: "+ Add next step" }));
  fireEvent.click(within(screen.getByTestId("add-next-step-types")).getByRole("button", { name: typeLabel }));
  return within(coque()).findByTestId("activity-create");
};
// The row ✓ → the validation flow → « Create the activity » → Next.
const validateAndCreate = async () => {
  fireEvent.click(await screen.findByLabelText("Validate signal"));
  const flow = within(coque()).getByTestId("next-step-validate-flow");
  fireEvent.click(within(flow).getByLabelText("Create the activity"));
  fireEvent.click(within(coque()).getByRole("button", { name: "Next" }));
  return within(coque()).findByTestId("activity-create");
};
// The date field's caption (read mode): « Scheduled » / « Due date ».
const dateLabel = (create) => within(create).getByTestId("inline-read-date").previousElementSibling.textContent;
// The toggle pressed when the date is opened.
const openedDateMode = (create) => {
  fireEvent.click(within(create).getByTestId("inline-read-date"));
  return within(create).getAllByRole("button", { pressed: true }).map((b) => b.textContent);
};
const stepShown = async (create) => {
  const read = await within(create).findByTestId("inline-read-decision_step");
  return read;
};
const changeType = async (create, label) => {
  fireEvent.click(within(create).getByTestId("inline-read-type"));
  fireEvent.click(await screen.findByRole("option", { name: label }));
  await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
};

beforeEach(() => {
  mockNextSteps = [];
  mockCited = [];
  api.get.mockResolvedValue({ success: true, data: { data: nextStep() } });
  api.post.mockResolvedValue({ success: true, data: { data: { id: "act-new" } } });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("« + Add next step » — the date field follows the type", () => {
  it("Meeting → the scheduled date", async () => {
    renderPage();
    const create = await addNextStep("Meeting");
    expect(dateLabel(create)).toMatch(/^Scheduled/);
    expect(openedDateMode(create)).toEqual(["Scheduled"]);
  });

  it("Task → the due date", async () => {
    renderPage();
    const create = await addNextStep("Task");
    expect(dateLabel(create)).toMatch(/^Due date/);
    expect(openedDateMode(create)).toEqual(["Due Date"]);
  });

  it("Email (not a scheduling type) → the due date", async () => {
    renderPage();
    const create = await addNextStep("Email");
    expect(dateLabel(create)).toMatch(/^Due date/);
  });

  it("the type changed in the drawer (Task → Phone Call) → the date field follows it", async () => {
    renderPage();
    const create = await addNextStep("Task");
    await changeType(create, "Phone Call");
    expect(dateLabel(create)).toMatch(/^Scheduled/);
  });
});

describe("« + Add next step » from a DC activity — the DC pre-filled, unchanged (8d-2)", () => {
  it("section 1 « Decision cycle » shows the activity's DC, pre-filled", async () => {
    renderPage();
    const create = await addNextStep("Meeting");
    const section = within(create).getByTestId("activity-cycle-section");
    expect(await within(section).findByText("Deal Acme")).toBeInTheDocument();
    expect(within(section).getByTestId("inline-read-decision_cycle")).toHaveTextContent("Deal Acme");
    expect(within(section).queryByRole("button", { name: /Create new cycle/ })).toBeNull();
  });
});

describe("« + Add next step » — the step of the origin activity", () => {
  it("the origin activity's step, not the cycle's current one", async () => {
    renderPage();
    const create = await addNextStep("Meeting");
    expect(await stepShown(create)).toHaveTextContent("Business case");
  });

  it("an origin activity without step → the cycle's current step", async () => {
    renderPage(originActivity({ decision_step: null, decision_step_detail: null }));
    const create = await addNextStep("Meeting");
    expect(await stepShown(create)).toHaveTextContent("Qualification");
  });
});

describe("✓ Create of a next step — date by type, suggested step else the origin's", () => {
  it("a TASK next step without date → the due date", async () => {
    mockNextSteps = [nextStep({ suggested_activity_type: "TASK" })];
    api.get.mockResolvedValue({ success: true, data: { data: mockNextSteps[0] } });
    renderPage();
    const create = await validateAndCreate();
    expect(dateLabel(create)).toMatch(/^Due date/);
  });

  it("a MEETING next step with a date → the scheduled date, pre-filled", async () => {
    mockNextSteps = [nextStep({ suggested_activity_type: "MEETING", suggested_due_date: "2026-11-20" })];
    api.get.mockResolvedValue({ success: true, data: { data: mockNextSteps[0] } });
    renderPage();
    const create = await validateAndCreate();
    expect(dateLabel(create)).toMatch(/^Scheduled/);
    expect(within(create).getByTestId("inline-read-date")).toHaveTextContent("Nov 20, 2026");
  });

  it("a MEETING next step with a date, the type changed to Task → the date becomes the due date", async () => {
    mockNextSteps = [nextStep({ suggested_activity_type: "MEETING", suggested_due_date: "2026-11-20" })];
    api.get.mockResolvedValue({ success: true, data: { data: mockNextSteps[0] } });
    renderPage();
    const create = await validateAndCreate();
    await changeType(create, "Task");
    expect(dateLabel(create)).toMatch(/^Due date/);
    expect(within(create).getByTestId("inline-read-date")).toHaveTextContent("Nov 20, 2026");
    expect(openedDateMode(create)).toEqual(["Due Date"]);
  });

  it("the suggested step of the DC wins", async () => {
    mockNextSteps = [nextStep({ suggested_decision_step: STEP_P })];
    api.get.mockResolvedValue({ success: true, data: { data: mockNextSteps[0] } });
    renderPage();
    const create = await validateAndCreate();
    expect(await stepShown(create)).toHaveTextContent("Proposal");
  });

  it("no suggested step → the origin activity's step", async () => {
    mockNextSteps = [nextStep({ suggested_decision_step: null })];
    api.get.mockResolvedValue({ success: true, data: { data: mockNextSteps[0] } });
    renderPage();
    const create = await validateAndCreate();
    expect(await stepShown(create)).toHaveTextContent("Business case");
  });

  it("a suggested step outside the DC → the origin activity's step", async () => {
    mockNextSteps = [nextStep({ suggested_decision_step: "99999999-9999-4999-8999-999999999999" })];
    api.get.mockResolvedValue({ success: true, data: { data: mockNextSteps[0] } });
    renderPage();
    const create = await validateAndCreate();
    expect(await stepShown(create)).toHaveTextContent("Business case");
  });
});

// Étape 8 — the workflow's last link on the page: ✓ Create from a next step
// citing a stakeholder linked to a contact (Paul X -> its contact) AND a
// non-converted stakeholder (Marc): the list is pre-filled with both, with
// no distinction shown, and Save sends contact_ids + stakeholder_ids.
describe("✓ Create — a next step citing both kinds of people (étape 8)", () => {
  const PAUL = { id: "c-paul", first_name: "Paul", last_name: "X", full_name: "Paul X",
                 department_name: null, is_reachable: true };
  const MARC = { id: "st-marc", display_name: "Marc", full_name: "Marc", department: null,
                 is_linked: false, contact: null, decision_cycle: DC_ID };

  it("both pre-filled, unmarked; the payload carries contact_ids AND stakeholder_ids", async () => {
    mockNextSteps = [nextStep({
      suggested_activity_type: "MEETING", suggested_due_date: "2026-12-10",
      suggested_decision_step: STEP_P, suggested_people_names: ["Paul X", "Marc"],
    })];
    mockCited = [
      { name: "Paul X", contact: PAUL, stakeholder: null },
      { name: "Marc", contact: null, stakeholder: MARC },
    ];
    api.get.mockResolvedValue({ success: true, data: { data: mockNextSteps[0] } });
    renderPage();
    const create = await validateAndCreate();
    const list = within(create).getByTestId("stakeholders-list");
    expect(within(list).getByText("External team")).toBeInTheDocument();
    expect(within(list).getByTestId("participant-c-paul").textContent).toBe("Paul X");
    expect(within(list).getByTestId("participant-st-marc").textContent).toBe("Marc");
    expect(list.textContent).not.toMatch(/Not yet a contact|Contact ·/);
    expect(within(create).queryByTestId("mentioned-names")).toBeNull();
    expect(await stepShown(create)).toHaveTextContent("Proposal");

    fireEvent.click(within(coque()).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(api.post).toHaveBeenCalledWith("/module-activities/", expect.anything()));
    const body = api.post.mock.calls.find(([url]) => url === "/module-activities/")[1];
    expect(body).toMatchObject({
      activity_type: "MEETING",
      contact_ids: ["c-paul"],
      stakeholder_ids: ["st-marc"],
      decision_cycle_id: DC_ID,
      decision_step_id: STEP_P,
      scheduled_date: "2026-12-10",
      next_step_signal_id: NS_ID,
    });
  });
});
