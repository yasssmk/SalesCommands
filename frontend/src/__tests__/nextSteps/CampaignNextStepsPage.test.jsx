// frontend/src/__tests__/nextSteps/CampaignNextStepsPage.test.jsx
//
// Sprint Next steps 5.14b — a SUCCESSFUL campaign activity can have next steps
// (PO: the goal of a campaign is to create decision cycles), on the Activity
// workspace PAGE as really rendered:
//   * the band shows the suggested next steps (the front mirror of the backend
//     predicate next_steps_enabled: a DC, or a campaign activity whose outcome
//     is successful) — and, without any, the AI action in the empty state;
//   * no DC born yet: « Start Decision Cycle » stays (PO 5), « + Add next
//     step » is hidden (PO 6); the row ✓ → Create opens the creation drawer in
//     CONVERSION mode (5.13), pre-filled from the next step, a NEW cycle inline;
//   * a DC born from the activity: the CTA is gone, « + Add next step » shows
//     and creates in that cycle; ✓ → Create creates in that cycle (no
//     conversion).
// REAL: the page, the band, the list, the validation flow, the coque, the
// creation drawer. Mocked: the HTTP client (utils/axiosClient), the band's
// next-step list (aggregated signals) and the other bands / data hooks.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import WorkspaceCoque from "../_utils/workspaceCoque";

const ACT_ID = "11111111-1111-4111-8111-111111111111";
const ACC_ID = "22222222-2222-4222-8222-222222222222";
const NS_ID = "33333333-3333-4333-8333-333333333333";
const DC_ID = "44444444-4444-4444-8444-444444444444";
const STEP_ID = "55555555-5555-4555-8555-555555555555";

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
vi.mock("@mui/x-date-pickers/DatePicker", () => ({
  DatePicker: ({ label, onChange }) => {
    const dayjs = require("dayjs");
    return <input aria-label={label} onChange={(e) => onChange(dayjs(e.target.value))} />;
  },
}));
vi.mock("@mui/x-date-pickers/LocalizationProvider", () => ({
  LocalizationProvider: ({ children }) => <>{children}</>,
}));
vi.mock("@mui/x-date-pickers/AdapterDayjs", () => ({ AdapterDayjs: class {} }));
vi.mock("@mui/x-date-pickers/TimePicker", () => ({ TimePicker: () => <input /> }));
vi.mock("utils/axiosClient", () => ({ api: { post: vi.fn(), get: vi.fn(), patch: vi.fn() } }));
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ tenantId: "t-1", user: { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" } }),
  default: () => ({ tenantId: "t-1", user: { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" } }),
}));
vi.mock("api/aiPipelines/lastRun", () => ({
  useGetLastExtractionRun: () => ({
    lastRun: { id: "run-1" }, latestRun: null, runsByPipeline: {}, mutateLastRun: vi.fn(),
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
    loading: false,
    error: null,
    mutate: vi.fn(),
  }),
}));
vi.mock("hooks/usePipelineRunner", async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => ({ run: vi.fn(), state: "idle", result: null, error: null, pollProgress: null, reset: vi.fn() }),
}));
vi.mock("contexts/BreadcrumbContext", () => ({ useBreadcrumb: () => ({ setCrumbs: vi.fn() }) }));
vi.mock("components/WorkspaceHeader", () => ({ default: () => <div data-testid="header" /> }));
vi.mock("sections/activities/workspace/ActivityHeader", () => ({ default: () => ({ modals: null }) }));
vi.mock("sections/activities/workspace/ActivityPreparationTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivityNotesTab", () => ({ default: () => null }));
vi.mock("sections/activities/workspace/ActivitySignalsTab", () => ({
  default: () => null,
  ACTIVITY_FLAT_TYPES: ["pain"],
}));
vi.mock("components/signals/SignalsHaloBox", () => ({ default: ({ children }) => <>{children}</> }));
vi.mock("utils/displayError", () => ({ displaySuccessSnackbar: vi.fn(), displayErrorSnackbar: vi.fn() }));

import { api } from "utils/axiosClient";
import ActivityWorkspacePage from "views/activities/workspace";

const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", full_name: "Thomas Lefèvre", job_title: "CTO" };

// The campaign call, SUCCESSFUL, no DC born yet (the AI proposes no step
// without a DC: suggested_decision_step null — PO 4).
const campaignActivity = {
  id: ACT_ID, title: "Cold call Thomas", activity_type: "CALL", status: "COMPLETED", outcome: "SUCCESSFUL",
  account: ACC_ID, account_detail: { id: ACC_ID, company_name: "Acme" },
  owner_detail: null, invited_users_detail: [], contacts_detail: [THOMAS],
  decision_cycle: null, decision_cycle_detail: null, decision_step: null,
  campaign_detail: { id: "camp-1", name: "Q4 push" }, source_activity_detail: null,
  next_step_origins: [], next_planned_step: null, transcript: "", outcome_notes: "",
};
const BORN = {
  source: "BORN_DECISION_CYCLE", decision_cycle: { id: DC_ID, name: "Deal Acme" },
  activity: { id: "act-born", title: "Discovery meeting", activity_type: "MEETING", status: "PLANNED",
              scheduled_date: "2026-11-12", decision_step_name: "Technical Fit", is_overdue: false },
};
const NEXT_STEP = {
  id: NS_ID, _signalType: "next-steps", status: "PENDING", source: "LLM_EXTRACTED",
  suggested_title: "Security review", suggested_activity_type: "MEETING",
  suggested_due_date: "2026-11-20", suggested_decision_step: null, decision_cycle: null,
  source_activity: ACT_ID, confidence: 0.8, created_at: "2026-10-28T10:00:00Z",
};

let serverActivity;
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  if (url.startsWith(`/module-activities/${ACT_ID}`)) return Promise.resolve({ data: serverActivity });
  if (url.startsWith(`/decision_cycles/by-account/${ACC_ID}`)) {
    return Promise.resolve({ data: { results: [{ id: DC_ID, name: "Deal Acme" }], count: 1 } });
  }
  if (url.startsWith(`/decision_cycles/steps/?cycle_id=${DC_ID}`)) {
    return Promise.resolve({
      data: { results: [{ id: STEP_ID, name: "Technical Fit", order: 2, is_current: true }], count: 1 },
    });
  }
  // The name the next step cites, matched to the account contact (TD-279).
  if (url.startsWith(`/module-signals/next-steps/${NS_ID}/cited-contacts`)) {
    return Promise.resolve({ data: { cited: [{ name: "Thomas", contact: THOMAS }] } });
  }
  return Promise.resolve({ data: { results: [], count: 0 } });
};

const renderPage = () =>
  render(
    // A fresh cache per test: the cycles hook dedupes for 10 s, so a cleared
    // shared cache would not refetch them (nothing here asserts the global
    // revalidation).
    <SWRConfig value={{ fetcher, dedupingInterval: 0, provider: () => new Map() }}>
      <WorkspaceCoque>
        <ActivityWorkspacePage />
      </WorkspaceCoque>
    </SWRConfig>,
  );

const coque = () => screen.getByTestId("coque-panel");
const addPill = () => screen.queryByRole("button", { name: "+ Add next step" });

// The row ✓ → the validation flow → « Create the activity » → Next.
const validateAndCreate = async () => {
  fireEvent.click(await screen.findByLabelText("Validate signal"));
  const flow = within(coque()).getByTestId("next-step-validate-flow");
  fireEvent.click(within(flow).getByLabelText("Create the activity"));
  fireEvent.click(within(coque()).getByRole("button", { name: "Next" }));
  return within(coque()).findByTestId("activity-create");
};

beforeEach(() => {
  serverActivity = campaignActivity;
  mockNextSteps = [NEXT_STEP];
  api.post.mockResolvedValue({ success: true, data: { data: { activity: { id: "act-new" } } } });
  api.get.mockResolvedValue({ success: true, data: { data: NEXT_STEP } });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("A SUCCESSFUL campaign activity — no DC born yet (5.14b)", () => {
  it("the band shows the suggested next steps; the CTA stays; no « + Add next step »", async () => {
    renderPage();
    const block = await screen.findByTestId("suggested-next-steps-block");
    expect(within(block).getByText("Security review")).toBeInTheDocument();
    expect(screen.getByTestId("campaign-conversion")).toBeInTheDocument();
    expect(addPill()).toBeNull();
  });

  it("without any next step: the AI action in the empty state", async () => {
    mockNextSteps = [];
    renderPage();
    const extraction = await screen.findByTestId("next-steps-extraction");
    expect(within(extraction).getByRole("button", { name: /Run AI Analysis/ })).toBeInTheDocument();
  });

  it("a campaign activity without a successful outcome: no suggested next steps", async () => {
    serverActivity = { ...campaignActivity, outcome: "NO_ANSWER" };
    renderPage();
    await screen.findByTestId("ctx-card");
    expect(screen.queryByTestId("suggested-next-steps-block")).toBeNull();
  });

  it("✓ → Create: the drawer in conversion mode, pre-filled from the next step, a new cycle inline", async () => {
    renderPage();
    const drawer = await validateAndCreate();
    expect(within(coque()).getByTestId("coque-title")).toHaveTextContent("Start Decision Cycle");
    expect(within(drawer).getByTestId("inline-read-title")).toHaveTextContent("Security review");
    expect(within(drawer).getByTestId("conversion-cycle")).toBeInTheDocument();
    expect(within(drawer).queryByTestId("inline-read-decision_cycle")).toBeNull();
    expect(within(drawer).getByText("Thomas Lefèvre")).toBeInTheDocument();

    const cycle = within(drawer).getByTestId("conversion-cycle");
    fireEvent.change(within(cycle).getByPlaceholderText("Cycle name *"), { target: { value: "Deal Acme" } });
    fireEvent.click(within(cycle).getByRole("button", { name: "Technical Fit" }));
    fireEvent.click(within(cycle).getByRole("button", { name: /Create Cycle/ }));
    await within(cycle).findByText("Deal Acme");
    const save = within(coque()).getByRole("button", { name: "Save" });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [url, body] = api.post.mock.calls[0];
    expect(url).toMatch(/create-with-entities/);
    expect(body.activity.next_step_signal_id).toBe(NS_ID);
    expect(body.activity.source_activity_id).toBe(ACT_ID);
    expect(body.inline_cycle).toEqual({ name: "Deal Acme" });
    expect(body.inline_step_stage).toBe("TECHNICAL_FIT");
  });
});

describe("A SUCCESSFUL campaign activity — a DC born from it (5.14b)", () => {
  beforeEach(() => {
    serverActivity = { ...campaignActivity, next_planned_step: BORN };
  });

  it("the CTA is gone; « + Add next step » shows", async () => {
    renderPage();
    await screen.findByTestId("suggested-next-steps-block");
    expect(screen.queryByTestId("campaign-conversion")).toBeNull();
    expect(addPill()).not.toBeNull();
  });

  it("« + Add next step » creates in the born cycle", async () => {
    renderPage();
    await screen.findByTestId("suggested-next-steps-block");
    fireEvent.click(addPill());
    fireEvent.click(within(screen.getByTestId("add-next-step-types")).getByRole("button", { name: "Meeting" }));
    const drawer = await within(coque()).findByTestId("activity-create");
    expect(within(drawer).queryByTestId("conversion-cycle")).toBeNull();
    await waitFor(() =>
      expect(within(drawer).getByTestId("inline-read-decision_cycle")).toHaveTextContent("Deal Acme"),
    );
  });

  it("✓ → Create: creates in the born cycle (no conversion)", async () => {
    renderPage();
    const drawer = await validateAndCreate();
    expect(within(drawer).queryByTestId("conversion-cycle")).toBeNull();
    await waitFor(() =>
      expect(within(drawer).getByTestId("inline-read-decision_cycle")).toHaveTextContent("Deal Acme"),
    );
    await waitFor(() =>
      expect(within(drawer).getByTestId("inline-read-decision_step")).toHaveTextContent("Technical Fit"),
    );
    const save = within(coque()).getByRole("button", { name: "Save" });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [url, body] = api.post.mock.calls[0];
    expect(url).not.toMatch(/create-with-entities/);
    expect(body.decision_cycle_id).toBe(DC_ID);
    expect(body.decision_step_id).toBe(STEP_ID);
    expect(body.next_step_signal_id).toBe(NS_ID);
    expect(body.contact_ids).toEqual(["c-1"]);
  });
});
