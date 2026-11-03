// frontend/src/__tests__/nextSteps/WorkspaceHookDepsPage.test.jsx
//
// Sprint « Cycle de vie des contacts », 7d-0 — the REAL Activity workspace
// page never logs React's « The final argument passed to useEffect changed
// size between renders »: opening the page, data changing between two
// renders (SWR revalidation), and the creation drawers whose step effect sees
// its values change (decision_step_id "" -> the chosen step). A hook whose
// dependency list is built dynamically (spread, conditional element) fails
// here. Harness of ActivityCreateDefaultsPage.test.jsx.

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
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  if (url.startsWith(`/module-activities/${ACT_ID}`)) return Promise.resolve({ data: serverActivity });
  if (url.startsWith("/decision_cycles/steps/")) {
    return Promise.resolve({ data: { results: url.includes(DC_ID) ? STEPS : [], count: 3 } });
  }
  if (url.startsWith(`/decision_cycles/${DC_ID}/stakeholders/`)) return Promise.resolve({ data: [] });
  if (url.startsWith(`/module-signals/next-steps/${NS_ID}/link-candidates`)) {
    return Promise.resolve({ data: { candidates: [], proposed_activity_id: null } });
  }
  if (url.startsWith(`/module-signals/next-steps/${NS_ID}/cited-contacts`)) {
    return Promise.resolve({ data: { cited: [] } });
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

const SIZE_WARNING = /changed size between renders/;
let errorSpy;
const sizeWarnings = () =>
  errorSpy.mock.calls.map((c) => c.map(String).join(" ")).filter((m) => SIZE_WARNING.test(m));
const rerenderPage = (r) =>
  r.rerender(
    <SWRConfig value={{ fetcher, dedupingInterval: 0, provider: () => new Map() }}>
      <WorkspaceCoque><ActivityWorkspacePage /></WorkspaceCoque>
    </SWRConfig>,
  );

beforeEach(() => {
  mockNextSteps = [];
  errorSpy = vi.spyOn(console, "error");
  api.get.mockResolvedValue({ success: true, data: { data: nextStep() } });
  api.post.mockResolvedValue({ success: true, data: { data: { id: "act-new" } } });
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("7d-0 — no hook dependency list changes size on the workspace page", () => {
  it("opening the page, then its data changing between two renders", async () => {
    mockNextSteps = [nextStep({ suggested_decision_step: STEP_P })];
    const r = renderPage();
    await screen.findByLabelText("Validate signal");
    serverActivity = originActivity({ decision_step: STEP_Q, title: "Changed" });
    mockNextSteps = [nextStep({ suggested_decision_step: STEP_Q }),
                     nextStep({ id: "88888888-8888-4888-8888-888888888888" })];
    rerenderPage(r);
    await waitFor(() => expect(screen.getAllByLabelText("Validate signal")).toHaveLength(2));
    expect(sizeWarnings()).toEqual([]);
  });

  it("« + Add next step »: the creation drawer sets its step (values change)", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "+ Add next step" }));
    fireEvent.click(within(screen.getByTestId("add-next-step-types")).getByRole("button", { name: "Meeting" }));
    const create = await within(coque()).findByTestId("activity-create");
    expect(await within(create).findByTestId("inline-read-decision_step")).toHaveTextContent("Business case");
    expect(sizeWarnings()).toEqual([]);
  });

  it("✓ Create: the creation drawer from a next step sets its step (values change)", async () => {
    mockNextSteps = [nextStep({ suggested_decision_step: STEP_P })];
    api.get.mockResolvedValue({ success: true, data: { data: mockNextSteps[0] } });
    renderPage();
    fireEvent.click(await screen.findByLabelText("Validate signal"));
    const flow = within(coque()).getByTestId("next-step-validate-flow");
    fireEvent.click(within(flow).getByLabelText("Create the activity"));
    fireEvent.click(within(coque()).getByRole("button", { name: "Next" }));
    const create = await within(coque()).findByTestId("activity-create");
    expect(await within(create).findByTestId("inline-read-decision_step")).toHaveTextContent("Proposal");
    expect(sizeWarnings()).toEqual([]);
  });
});
