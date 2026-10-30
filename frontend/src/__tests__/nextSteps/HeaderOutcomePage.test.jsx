// frontend/src/__tests__/nextSteps/HeaderOutcomePage.test.jsx
//
// Sprint Next steps 5.15 / 5.15b — the outcome of a COMPLETED activity is
// visible in the header: ONE pill (5.15b, PO — « Completed » + the outcome was
// a duplicate). A COMPLETED activity with an outcome: the existing OutcomeChip
// (components/outcomes/OutcomeChip — its unified label) REPLACES the
// « Completed » status pill; without an outcome: « Completed ». Every other
// status: its status pill, unchanged.
// REAL: the page, the header hook (useActivityHeaderProps), the header shell
// (WorkspaceHeader), StatusPill, OutcomeChip. Mocked: the HTTP client
// (utils/axiosClient) and the other bands / data hooks.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, within } from "@testing-library/react";
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

import ActivityWorkspacePage from "views/activities/workspace";
import { OUTCOME_META } from "utils/outcomes";

const activity = (over = {}) => ({
  id: ACT_ID, title: "Discovery call", activity_type: "CALL", status: "COMPLETED",
  outcome: "MEETING_SCHEDULED",
  account: ACC_ID, account_detail: { id: ACC_ID, company_name: "Acme" },
  owner_detail: null, invited_users_detail: [], contacts_detail: [],
  decision_cycle: null, decision_cycle_detail: null, decision_step: null,
  campaign_detail: null, source_activity_detail: null,
  next_step_origins: [], next_planned_step: null, transcript: "", outcome_notes: "",
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

// The header's title row: the <h1> title and its adornment, side by side.
const titleRow = async () => (await screen.findByRole("heading", { level: 1, name: "Discovery call" })).parentElement.parentElement;
const pills = (row) => within(row).queryAllByTestId("status-pill");

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("The outcome in the header — one pill (5.15 / 5.15b)", () => {
  it("a COMPLETED activity with an outcome: the OutcomeChip REPLACES « Completed »", async () => {
    renderPage(activity());
    const row = await titleRow();
    expect(pills(row)).toHaveLength(1);
    expect(pills(row)[0]).toHaveTextContent(OUTCOME_META.MEETING_SCHEDULED.label);
    expect(within(row).queryByText("Completed")).toBeNull();
  });

  it("the unified label of each outcome (OUTCOME_META)", async () => {
    renderPage(activity({ outcome: "NO_ANSWER" }));
    const row = await titleRow();
    expect(pills(row)).toHaveLength(1);
    expect(pills(row)[0]).toHaveTextContent(OUTCOME_META.NO_ANSWER.label);
  });

  it("a COMPLETED activity without an outcome: « Completed »", async () => {
    renderPage(activity({ outcome: null }));
    const row = await titleRow();
    expect(pills(row)).toHaveLength(1);
    expect(pills(row)[0]).toHaveTextContent("Completed");
  });

  it("a PLANNED activity (a stray outcome): the status pill only", async () => {
    renderPage(activity({ status: "PLANNED", outcome: "SUCCESSFUL" }));
    const row = await titleRow();
    expect(pills(row)).toHaveLength(1);
    expect(pills(row)[0]).toHaveTextContent("Planned");
  });

  it("a CANCELLED activity (a stray outcome): the status pill only", async () => {
    renderPage(activity({ status: "CANCELLED", outcome: "SUCCESSFUL" }));
    const row = await titleRow();
    expect(pills(row)).toHaveLength(1);
    expect(pills(row)[0]).toHaveTextContent("Cancelled");
  });
});
