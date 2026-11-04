// frontend/src/__tests__/nextSteps/StartDecisionCyclePage.test.jsx
//
// Sprint Next steps 5.13.3 — "Start Decision Cycle", on the Activity workspace
// PAGE as really rendered, end to end:
//   * the CTA is a ClickablePill (no MUI button in the band, 5.12c);
//   * it opens the creation DRAWER in conversion mode (a MEETING, a NEW cycle
//     only, the campaign activity's contact pre-filled) — no ActivityModal is
//     mounted any more;
//   * on save: create-with-entities (inline_cycle + inline_step_stage +
//     source_activity_id) → the standard revalidation (/module-activities/)
//     re-reads the campaign activity → the CTA disappears and Context shows the
//     born Decision Cycle (« In decision cycle <name> › … », 5.12 A-bis).
// REAL: the page, the Context section, the band, the coque, the drawer,
// InlineCycleForm, useGetActivity and createActivityWithEntities with their
// SWR revalidation. Mocked: the HTTP client (utils/axiosClient) and the other
// bands / data hooks.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, within, waitFor } from "@testing-library/react";
import { SWRConfig, mutate as swrMutate } from "swr";
import WorkspaceCoque from "../_utils/workspaceCoque";

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
vi.mock("api/signals/aggregatedSignals", async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => ({ signals: [], mutate: vi.fn() }),
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
// Any ActivityModal MOUNTED (open or not) is visible: there must be none.
vi.mock("sections/accounts/activities/ActivityModal", () => ({
  default: () => <div data-testid="activity-modal-mounted" />,
}));

import { api } from "utils/axiosClient";
import ActivityWorkspacePage from "views/activities/workspace";

const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", full_name: "Thomas Lefèvre", job_title: "CTO" };

// The campaign activity — SUCCESSFUL, no DC born yet; then, once the cycle is
// created, the server reads it with the born DC (next_planned_step).
const campaignActivity = {
  id: ACT_ID, title: "Cold call Thomas", activity_type: "CALL", status: "COMPLETED", outcome: "SUCCESSFUL",
  account: ACC_ID, account_detail: { id: ACC_ID, company_name: "Acme" },
  owner_detail: null, invited_users_detail: [], contacts_detail: [THOMAS],
  decision_cycle: null, decision_cycle_detail: null, decision_step: null,
  campaign_detail: { id: "camp-1", name: "Q4 push" }, source_activity_detail: null,
  next_step_origins: [], next_planned_step: null, transcript: "", outcome_notes: "",
};
const BORN = {
  source: "BORN_DECISION_CYCLE", decision_cycle: { id: "dc-new", name: "Deal Acme" },
  activity: { id: "act-born", title: "Discovery meeting", activity_type: "MEETING", status: "PLANNED",
              scheduled_date: "2026-11-12", decision_step_name: "Technical Fit", is_overdue: false },
};

let serverActivity;
// 8c-3 / 8d-2: the account's open cycles (the list endpoint, server search)
// and the steps of a cycle; every URL read is recorded.
let accountCycles = [];
let fetchedUrls = [];
const DC_ALPHA = "44444444-4444-4444-8444-444444444441";
const STEP_ALPHA = "55555555-5555-4555-8555-555555555551";
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  fetchedUrls.push(url);
  if (url.startsWith(`/module-activities/${ACT_ID}`)) return Promise.resolve({ data: serverActivity });
  if (url.startsWith("/decision_cycles/?")) {
    const q = new URLSearchParams(url.split("?")[1]).get("search") || "";
    const rows = accountCycles.filter((c) => c.name.toLowerCase().includes(q.toLowerCase()));
    return Promise.resolve({ data: { results: rows, count: rows.length } });
  }
  if (url.startsWith("/decision_cycles/steps/") && url.includes(DC_ALPHA)) {
    return Promise.resolve({ data: { results: [
      { id: STEP_ALPHA, name: "Qualification", order: 1, is_current: true, cycle: DC_ALPHA },
    ], count: 1 } });
  }
  return Promise.resolve({ data: { results: [], count: 0 } });
};

const renderPage = () =>
  render(
    // The DEFAULT cache, as in the app: the standard revalidation
    // (revalidateMetricSurfaces) goes through swr's global mutate.
    <SWRConfig value={{ fetcher, dedupingInterval: 0 }}>
      <WorkspaceCoque>
        <ActivityWorkspacePage />
      </WorkspaceCoque>
    </SWRConfig>,
  );

const startPill = () => screen.getByRole("button", { name: "Start Decision Cycle" });
const coque = () => screen.getByTestId("coque-panel");

beforeEach(() => {
  serverActivity = campaignActivity;
  accountCycles = [];
  fetchedUrls = [];
  api.post.mockImplementation(async () => {
    serverActivity = { ...campaignActivity, next_planned_step: BORN };
    return { success: true, data: { data: { activity: { id: "act-born" } } } };
  });
});
afterEach(async () => {
  cleanup();
  vi.clearAllMocks();
  // Empty the default cache between tests (no stale activity).
  await swrMutate(() => true, undefined, { revalidate: false });
});

describe("Start Decision Cycle — the pill, the drawer, the born DC (5.13.3)", () => {
  it("the CTA is a ClickablePill; no ActivityModal is mounted", async () => {
    renderPage();
    expect(await screen.findByRole("button", { name: "Start Decision Cycle" })).toHaveAttribute("data-testid", "status-pill");
    expect(screen.getByTestId("campaign-conversion").querySelector(".MuiButton-root")).toBeNull();
    expect(screen.queryByTestId("activity-modal-mounted")).toBeNull();
  });

  it("the pill opens the creation drawer in conversion mode: a MEETING, a new cycle, the contact pre-filled", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Start Decision Cycle" }));
    const drawer = within(coque()).getByTestId("activity-create");
    expect(within(coque()).getByTestId("coque-title")).toHaveTextContent("Start Decision Cycle");
    expect(within(drawer).getByTestId("inline-read-type")).toHaveTextContent("Meeting");
    // 8d-2: the cycle section — an existing cycle (nothing pre-selected) or
    // « Create new cycle ».
    expect(within(drawer).getByTestId("inline-read-decision_cycle")).toHaveTextContent("Choose a decision cycle");
    expect(within(drawer).getByRole("button", { name: /Create new cycle/ })).toBeInTheDocument();
    expect(within(drawer).getByText("Thomas Lefèvre")).toBeInTheDocument();
    expect(screen.queryByTestId("activity-modal-mounted")).toBeNull();
  });

  it("on save: create-with-entities from the campaign activity, then the CTA disappears and Context shows the born DC", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Start Decision Cycle" }));
    const drawer = within(coque()).getByTestId("activity-create");
    fireEvent.click(within(drawer).getByTestId("inline-read-title"));
    fireEvent.change(within(drawer).getByTestId("inline-input-title"), { target: { value: "Discovery meeting" } });
    fireEvent.click(within(drawer).getByTestId("inline-read-date"));
    fireEvent.change(screen.getByLabelText("Scheduled date"), { target: { value: "2026-11-12" } });
    fireEvent.click(screen.getByTestId("date-confirm"));
    // 8d-2: the new cycle opens from « Create new cycle » (the old modal's way).
    fireEvent.click(within(drawer).getByRole("button", { name: /Create new cycle/ }));
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
    expect(body.activity.source_activity_id).toBe(ACT_ID);
    expect(body.activity.contact_ids).toEqual(["c-1"]);
    expect(body.inline_cycle).toEqual({ name: "Deal Acme" });
    expect(body.inline_step_stage).toBe("TECHNICAL_FIT");

    await waitFor(() => expect(screen.queryByRole("button", { name: "Start Decision Cycle" })).toBeNull());
    const line = await screen.findByTestId("next-planned-line");
    expect(line.textContent).toBe("In decision cycle Deal Acme › Discovery meeting · Technical Fit · 12 Nov 2026");
    // The coque closes (its Collapse exit transition, then unmounted).
    await waitFor(() => expect(screen.queryByTestId("coque-panel")).toBeNull());
  });
});

// 8d-2 (PO): the conversion's « Decision cycle » section (section 1) — the
// standard AsyncDecisionCycleSelect (server search on the account's OPEN cycles,
// newest update first, NOTHING pre-selected) OR « Create new cycle » (the
// existing InlineCycleForm; once created: the cycle chosen emptied, the step
// hidden, the confirmation row with Remove), as the old ActivityModal.
describe("Start Decision Cycle — an existing DC or « Create new cycle » (8d-2)", () => {
  const drawerNow = () => within(coque()).getByTestId("activity-create");
  const openStart = async () => {
    fireEvent.click(await screen.findByRole("button", { name: "Start Decision Cycle" }));
    return drawerNow();
  };
  const openCycleSearch = () => {
    fireEvent.click(within(drawerNow()).getByTestId("inline-read-decision_cycle"));
    const input = within(drawerNow()).getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    return input;
  };
  const fillTitleAndDate = () => {
    fireEvent.click(within(drawerNow()).getByTestId("inline-read-title"));
    fireEvent.change(within(drawerNow()).getByTestId("inline-input-title"), { target: { value: "Discovery meeting" } });
    fireEvent.click(within(drawerNow()).getByTestId("inline-read-date"));
    fireEvent.change(screen.getByLabelText("Scheduled date"), { target: { value: "2026-11-12" } });
    fireEvent.click(screen.getByTestId("date-confirm"));
  };
  const listUrls = () => fetchedUrls.filter((u) => u.startsWith("/decision_cycles/?"));

  beforeEach(() => {
    accountCycles = [
      { id: DC_ALPHA, name: "Deal Alpha", outcome: null },
      { id: "44444444-4444-4444-8444-444444444442", name: "Deal Beta", outcome: null },
    ];
  });

  it("nothing pre-selected; the server search: the account, the OPEN cycles, newest update first", async () => {
    renderPage();
    await openStart();
    expect(within(drawerNow()).getByTestId("inline-read-decision_cycle")).toHaveTextContent("Choose a decision cycle");
    const input = openCycleSearch();
    await waitFor(() => expect(listUrls().length).toBeGreaterThan(0));
    const params = new URLSearchParams(listUrls().at(-1).split("?")[1]);
    expect(params.get("account")).toBe(ACC_ID);
    expect(params.get("outcome__isnull")).toBe("true");
    expect(params.get("ordering")).toBe("-updated_at");
    fireEvent.change(input, { target: { value: "Alp" } });
    await waitFor(() =>
      expect(listUrls().some((u) => new URLSearchParams(u.split("?")[1]).get("search") === "Alp")).toBe(true),
      { timeout: 2000 });
    expect((await screen.findAllByRole("option")).map((o) => o.textContent)).toEqual(["Deal Alpha"]);
  });

  it("an existing cycle: its step required, then create-with-entities in it from the campaign activity", async () => {
    api.post.mockImplementation(async () => {
      serverActivity = { ...campaignActivity, next_planned_step: {
        ...BORN, decision_cycle: { id: DC_ALPHA, name: "Deal Alpha" } } };
      return { success: true, data: { data: { activity: { id: "act-born" } } } };
    });
    renderPage();
    await openStart();
    fillTitleAndDate();
    openCycleSearch();
    fireEvent.click(await screen.findByRole("option", { name: "Deal Alpha" }));
    expect(within(drawerNow()).getByTestId("inline-read-decision_cycle")).toHaveTextContent("Deal Alpha");
    expect(await waitFor(() => within(drawerNow()).getByTestId("inline-read-decision_step")))
      .toHaveTextContent("Qualification");
    const save = within(coque()).getByRole("button", { name: "Save" });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [url, body] = api.post.mock.calls[0];
    expect(url).toMatch(/create-with-entities/);
    expect(body.activity).toMatchObject({
      decision_cycle_id: DC_ALPHA, decision_step_id: STEP_ALPHA, source_activity_id: ACT_ID,
    });
    expect(body.inline_cycle).toBeUndefined();
    await waitFor(() => expect(screen.queryByRole("button", { name: "Start Decision Cycle" })).toBeNull());
  });

  it("« Create new cycle »: the chosen cycle emptied, the step hidden, the confirmation row with Remove; inline_cycle sent", async () => {
    renderPage();
    await openStart();
    fillTitleAndDate();
    openCycleSearch();
    fireEvent.click(await screen.findByRole("option", { name: "Deal Alpha" }));
    await waitFor(() => within(drawerNow()).getByTestId("inline-read-decision_step"));
    fireEvent.click(within(drawerNow()).getByRole("button", { name: /Create new cycle/ }));
    // the form open: the step hidden already (the old modal's behaviour)
    expect(within(drawerNow()).queryByTestId("inline-read-decision_step")).toBeNull();
    const cycle = within(drawerNow()).getByTestId("conversion-cycle");
    fireEvent.change(within(cycle).getByPlaceholderText("Cycle name *"), { target: { value: "Deal Acme" } });
    fireEvent.click(within(cycle).getByRole("button", { name: /Create Cycle/ }));
    await within(cycle).findByText("Deal Acme");
    expect(within(drawerNow()).queryByTestId("inline-read-decision_cycle")).toBeNull();
    expect(within(drawerNow()).queryByTestId("inline-read-decision_step")).toBeNull();
    const save = within(coque()).getByRole("button", { name: "Save" });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const body = api.post.mock.calls[0][1];
    expect(body.inline_cycle).toEqual({ name: "Deal Acme" });
    expect(body.activity.decision_cycle_id).toBeNull();
    expect(body.activity.decision_step_id).toBeNull();
    expect(body.activity.source_activity_id).toBe(ACT_ID);
  });

  it("Remove: back to the choice (an existing cycle or « Create new cycle »)", async () => {
    renderPage();
    await openStart();
    fireEvent.click(within(drawerNow()).getByRole("button", { name: /Create new cycle/ }));
    const cycle = within(drawerNow()).getByTestId("conversion-cycle");
    fireEvent.change(within(cycle).getByPlaceholderText("Cycle name *"), { target: { value: "Deal Acme" } });
    fireEvent.click(within(cycle).getByRole("button", { name: /Create Cycle/ }));
    await within(cycle).findByText("Deal Acme");
    fireEvent.click(within(drawerNow()).getByTestId("remove-inline-cycle"));
    expect(within(drawerNow()).getByTestId("inline-read-decision_cycle")).toHaveTextContent("Choose a decision cycle");
  });

  it("the People section follows the cycle chosen in section 1 (its stakeholders)", async () => {
    renderPage();
    await openStart();
    openCycleSearch();
    fireEvent.click(await screen.findByRole("option", { name: "Deal Alpha" }));
    fireEvent.click(within(drawerNow()).getByTestId("add-stakeholder"));
    const input = within(within(drawerNow()).getByTestId("stakeholder-select")).getByRole("combobox");
    fireEvent.focus(input);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    await waitFor(() =>
      expect(fetchedUrls.some((u) => u.startsWith(`/decision_cycles/${DC_ALPHA}/stakeholders/`))).toBe(true));
  });
});
