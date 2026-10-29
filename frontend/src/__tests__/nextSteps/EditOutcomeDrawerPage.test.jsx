// frontend/src/__tests__/nextSteps/EditOutcomeDrawerPage.test.jsx
//
// Sprint Next steps 5.17 — the outcome is editable in the Edit activity drawer
// (EditActivityContent, edit mode) when the activity is COMPLETED: a single
// choice in pills — the shared OutcomeSelector (labels and colours from
// OUTCOME_META, filtered by the activity type: getOutcomesForType — no local
// list), pre-selected on the current outcome; the global Save PATCHes it. Not
// on a PLANNED / CANCELLED activity. On a campaign activity the PATCH carries
// the outcome and still none of the campaign-locked fields.
// REAL: the page, the header and its ⋯ menu, the coque, the edit drawer,
// OutcomeSelector, updateActivity. Mocked: the HTTP client and the other bands.

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, within, fireEvent, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
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
    lastRun: null, latestRun: null, runsByPipeline: {}, mutateLastRun: vi.fn(),
  }),
}));
vi.mock("api/signals/signalCounts", () => ({
  useActivitySignalCounts: () => ({ counts: {}, mutateCounts: vi.fn() }),
}));
vi.mock("api/signals/aggregatedSignals", async (importOriginal) => ({
  ...(await importOriginal()),
  default: () => ({ signals: [], loading: false, error: null, mutate: vi.fn() }),
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

import { api } from "utils/axiosClient";
import ActivityWorkspacePage from "views/activities/workspace";
import { getOutcomesForType } from "utils/outcomes";

const OWNER = { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" };
const THOMAS = { id: "c-1", first_name: "Thomas", last_name: "Lefèvre", full_name: "Thomas Lefèvre" };

const activity = (over = {}) => ({
  id: ACT_ID, title: "Discovery call", activity_type: "CALL", status: "COMPLETED",
  outcome: "FOLLOW_UP_NEEDED", scheduled_date: "2026-10-20",
  account: ACC_ID, account_detail: { id: ACC_ID, company_name: "Acme" },
  owner_detail: OWNER, invited_users_detail: [], contacts_detail: [THOMAS],
  decision_cycle: null, decision_cycle_detail: null, decision_step: null,
  campaign_detail: null, source_activity_detail: null,
  next_step_origins: [], next_planned_step: null, transcript: "", outcome_notes: "",
  call_to_action: "", description: "",
  ...over,
});

let serverActivity;
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  if (url.startsWith(`/module-activities/${ACT_ID}`)) return Promise.resolve({ data: serverActivity });
  return Promise.resolve({ data: { results: [], count: 0 } });
};

const renderPage = (a) => {
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

// The real header's ⋯ menu → Edit → the edit drawer in the coque.
const openEdit = async () => {
  const header = await screen.findByTestId("workspace-header");
  fireEvent.click(within(header).getByRole("button", { name: /more/ }));
  fireEvent.click(await screen.findByText("Edit"));
  return coque();
};

beforeEach(() => {
  api.patch.mockResolvedValue({ success: true, data: { data: serverActivity } });
});
afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("The outcome in the Edit activity drawer (5.17)", () => {
  it("COMPLETED: the outcome pills (OutcomeSelector — the type's outcomes), the current one selected", async () => {
    renderPage(activity());
    const drawer = await openEdit();
    expect(within(drawer).getByTestId("coque-title")).toHaveTextContent("Edit activity");
    const selector = within(drawer).getByTestId("outcome-selector");
    const shown = within(selector).getAllByRole("button").map((b) => b.getAttribute("data-testid"));
    expect(shown).toEqual(
      getOutcomesForType("CALL").filter((o) => o !== "CALLBACK_REQUESTED").map((o) => `outcome-pill-${o}`),
    );
    expect(within(selector).getByTestId("outcome-pill-FOLLOW_UP_NEEDED")).toHaveAttribute("aria-pressed", "true");
    expect(within(selector).getByTestId("outcome-pill-SUCCESSFUL")).toHaveAttribute("aria-pressed", "false");
  });

  it("a single choice: picking another outcome selects it alone; Save PATCHes it", async () => {
    renderPage(activity());
    const drawer = await openEdit();
    const selector = within(drawer).getByTestId("outcome-selector");
    fireEvent.click(within(selector).getByTestId("outcome-pill-SUCCESSFUL"));
    expect(within(selector).getByTestId("outcome-pill-SUCCESSFUL")).toHaveAttribute("aria-pressed", "true");
    expect(within(selector).getAllByRole("button", { pressed: true })).toHaveLength(1);
    const save = within(drawer).getByRole("button", { name: "Save" });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);
    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    const [url, body] = api.patch.mock.calls[0];
    expect(url).toBe(`/module-activities/${ACT_ID}/`);
    expect(body.outcome).toBe("SUCCESSFUL");
  });

  it("a campaign activity: the outcome is sent, the campaign-locked fields still are not", async () => {
    renderPage(activity({ campaign_detail: { id: "camp-1", name: "Q4 push" } }));
    const drawer = await openEdit();
    fireEvent.click(within(within(drawer).getByTestId("outcome-selector")).getByTestId("outcome-pill-NOT_INTERESTED"));
    const save = within(drawer).getByRole("button", { name: "Save" });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);
    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    const body = api.patch.mock.calls[0][1];
    expect(body.outcome).toBe("NOT_INTERESTED");
    for (const locked of ["scheduled_date", "scheduled_time", "due_date", "owner_id", "contact_ids", "invited_user_ids"]) {
      expect(body).not.toHaveProperty(locked);
    }
  });

  it("an edit without touching the outcome: the outcome is not sent", async () => {
    renderPage(activity());
    const drawer = await openEdit();
    fireEvent.click(within(drawer).getByTestId("inline-read-title"));
    fireEvent.change(within(drawer).getByTestId("inline-input-title"), { target: { value: "Discovery call #2" } });
    fireEvent.blur(within(drawer).getByTestId("inline-input-title"));
    const save = within(drawer).getByRole("button", { name: "Save" });
    await waitFor(() => expect(save).toBeEnabled());
    fireEvent.click(save);
    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    const body = api.patch.mock.calls[0][1];
    expect(body.title).toBe("Discovery call #2");
    expect(body).not.toHaveProperty("outcome");
  });

  it("PLANNED: no outcome in the drawer", async () => {
    renderPage(activity({ status: "PLANNED", outcome: null }));
    const drawer = await openEdit();
    expect(within(drawer).queryByTestId("outcome-selector")).toBeNull();
  });

  it("CANCELLED: no outcome in the drawer", async () => {
    renderPage(activity({ status: "CANCELLED", outcome: null }));
    const drawer = await openEdit();
    expect(within(drawer).queryByTestId("outcome-selector")).toBeNull();
  });
});
