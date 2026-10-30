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
import { getOutcomesForType, CALLBACK_OUTCOME, EDIT_EXCLUDED_CAMPAIGN_OUTCOMES } from "utils/outcomes";

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

// 5.17b (PO): on a CAMPAIGN activity, the outcomes that drive the sequence
// (EDIT_EXCLUDED_CAMPAIGN_OUTCOMES: CALLBACK_REQUESTED, NO_ANSWER) go through
// the completion — not offered by Edit, unless one is the current outcome. A
// type change that the current outcome does not fit clears it (nothing
// invisible kept nor sent).
describe("The outcome in Edit — campaign set and type change (5.17b)", () => {
  const campaign = { campaign_detail: { id: "camp-1", name: "Q4 push" } };
  const selector = (drawer) => within(drawer).getByTestId("outcome-selector");
  const shownIds = (drawer) => within(selector(drawer)).getAllByRole("button").map((b) => b.getAttribute("data-testid"));
  const pickType = async (drawer, label) => {
    fireEvent.click(within(drawer).getByTestId("inline-read-type"));
    fireEvent.click(await screen.findByRole("option", { name: label }));
  };
  const save = async (drawer) => {
    const btn = within(drawer).getByRole("button", { name: "Save" });
    await waitFor(() => expect(btn).toBeEnabled());
    fireEvent.click(btn);
    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    return api.patch.mock.calls[0][1];
  };

  it("the set is ONE constant: CALLBACK_REQUESTED + NO_ANSWER", () => {
    expect([...EDIT_EXCLUDED_CAMPAIGN_OUTCOMES].sort()).toEqual([CALLBACK_OUTCOME, "NO_ANSWER"].sort());
  });

  it("a campaign activity: neither NO_ANSWER nor CALLBACK_REQUESTED offered", async () => {
    renderPage(activity(campaign));
    const drawer = await openEdit();
    expect(shownIds(drawer)).toEqual(
      getOutcomesForType("CALL")
        .filter((o) => o !== "NO_ANSWER" && o !== CALLBACK_OUTCOME)
        .map((o) => `outcome-pill-${o}`),
    );
  });

  it("a campaign activity whose current outcome is NO_ANSWER: it stays shown, selected", async () => {
    renderPage(activity({ ...campaign, outcome: "NO_ANSWER" }));
    const drawer = await openEdit();
    expect(within(selector(drawer)).getByTestId("outcome-pill-NO_ANSWER")).toHaveAttribute("aria-pressed", "true");
    expect(within(selector(drawer)).queryByTestId(`outcome-pill-${CALLBACK_OUTCOME}`)).toBeNull();
  });

  it("outside a campaign: NO_ANSWER stays offered", async () => {
    renderPage(activity());
    const drawer = await openEdit();
    expect(within(selector(drawer)).getByTestId("outcome-pill-NO_ANSWER")).toBeInTheDocument();
  });

  it("a type change the outcome does not fit: the outcome is cleared, and sent cleared", async () => {
    // INVALID_PHONE_NUMBER exists for a CALL, not for a MEETING.
    renderPage(activity({ outcome: "INVALID_PHONE_NUMBER" }));
    const drawer = await openEdit();
    await pickType(drawer, "Meeting");
    expect(within(selector(drawer)).queryAllByRole("button", { pressed: true })).toHaveLength(0);
    expect(within(selector(drawer)).queryByTestId("outcome-pill-INVALID_PHONE_NUMBER")).toBeNull();
    const body = await save(drawer);
    expect(body.activity_type).toBe("MEETING");
    expect(body).toHaveProperty("outcome", null);
  });

  it("a type change the outcome fits: the outcome is kept (not sent)", async () => {
    renderPage(activity({ outcome: "SUCCESSFUL" }));
    const drawer = await openEdit();
    await pickType(drawer, "Meeting");
    expect(within(selector(drawer)).getByTestId("outcome-pill-SUCCESSFUL")).toHaveAttribute("aria-pressed", "true");
    const body = await save(drawer);
    expect(body.activity_type).toBe("MEETING");
    expect(body).not.toHaveProperty("outcome");
  });
});
