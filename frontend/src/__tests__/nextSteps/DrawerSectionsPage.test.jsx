// frontend/src/__tests__/nextSteps/DrawerSectionsPage.test.jsx
//
// Sprint Next steps 5.18 — Edit activity (edit AND create) and Edit contact
// take EXACTLY the design of the Edit signal drawers: numbered sections — the
// shared SectionHeader (components/display/SectionHeader: the index badge on
// the primary palette role + title + subtitle), one Stack per section,
// separated by the MUI Divider (EditNextStepContent / EditPainContent…).
// The badge is compared to a reference SectionHeader rendered in the same
// theme (same emotion class → same component, no copy).
// REAL: the page, the header ⋯ menu, the Next steps band, the Context section,
// the coque, the drawers. Mocked: the HTTP client and the other bands.

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

import ActivityWorkspacePage from "views/activities/workspace";
import SectionHeader from "components/display/SectionHeader";
import AphoriqTheme from "../_utils/aphoriqTheme";

const C_ID = "66666666-6666-4666-8666-666666666666";
const DC_ID = "44444444-4444-4444-8444-444444444444";
const OWNER = { id: "u-1", first_name: "Ann", last_name: "Owner", email: "ann@acme.test" };
const THOMAS = { id: C_ID, first_name: "Thomas", last_name: "Lefèvre", full_name: "Thomas Lefèvre" };

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
const dcActivity = (over = {}) => activity({
  decision_cycle: DC_ID, decision_cycle_detail: { id: DC_ID, name: "Deal Acme" }, ...over,
});
const campaignActivity = (over = {}) => activity({
  outcome: "SUCCESSFUL", campaign_detail: { id: "camp-1", name: "Q4 push" }, ...over,
});

let serverActivity;
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  if (url.startsWith(`/module-activities/${ACT_ID}`)) return Promise.resolve({ data: serverActivity });
  if (url.startsWith(`/contacts/${C_ID}/`)) return Promise.resolve({ data: THOMAS });
  if (url.startsWith(`/decision_cycles/${DC_ID}/people/`)) {
    return Promise.resolve({ data: { qualified: [], unqualified: [] } });
  }
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

// The reference: the Edit signal drawers' SectionHeader badge, in the same theme.
const referenceBadgeClass = () => {
  const { container, unmount } = render(
    <AphoriqTheme><SectionHeader index={1} title="Reference" subtitle="ref" /></AphoriqTheme>,
  );
  const cls = container.querySelector(".MuiChip-root").className;
  unmount();
  return cls;
};

// The numbered sections of a drawer: [{ index, title, badge }] in order.
const sectionsOf = (drawer) =>
  [...drawer.querySelectorAll(".MuiChip-root")]
    .filter((chip) => /^\d+$/.test(chip.textContent))
    .map((chip) => ({ index: chip.textContent, title: chip.nextElementSibling?.textContent, badge: chip }));

const expectSignalDesign = (drawer, titles) => {
  const sections = sectionsOf(drawer);
  expect(sections.map((s) => s.index)).toEqual(titles.map((_, i) => String(i + 1)));
  expect(sections.map((s) => s.title)).toEqual(titles);
  const ref = referenceBadgeClass();
  for (const s of sections) expect(s.badge.className).toBe(ref);
  // Sections separated by the MUI Divider, as in the Edit signal drawers.
  expect(drawer.querySelectorAll("hr.MuiDivider-root")).toHaveLength(titles.length - 1);
  expect(within(drawer).queryByTestId("group-filet")).toBeNull();
};

const ACTIVITY_SECTIONS = ["Activity", "When", "Purpose", "People"];

// The real header's ⋯ menu → Edit.
const openEditActivity = async () => {
  const header = await screen.findByTestId("workspace-header");
  fireEvent.click(within(header).getByRole("button", { name: /more/ }));
  fireEvent.click(await screen.findByText("Edit"));
  return coque();
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("Edit activity — the Edit signal design (5.18)", () => {
  it("edit mode: numbered sections 1-4, the shared SectionHeader, Dividers", async () => {
    renderPage(activity());
    const drawer = await openEditActivity();
    expect(within(drawer).getByTestId("coque-title")).toHaveTextContent("Edit activity");
    expectSignalDesign(drawer, ACTIVITY_SECTIONS);
  });

  it("create mode (« + Add next step » → a type): the same sections", async () => {
    renderPage(dcActivity());
    fireEvent.click(await screen.findByRole("button", { name: "+ Add next step" }));
    fireEvent.click(within(screen.getByTestId("add-next-step-types")).getByRole("button", { name: "Meeting" }));
    const create = await within(coque()).findByTestId("activity-create");
    expectSignalDesign(create, ACTIVITY_SECTIONS);
  });

  it("create mode, conversion (« Start Decision Cycle »): the same sections", async () => {
    renderPage(campaignActivity());
    // The band starts folded (not analysed): unfold it.
    fireEvent.click(await screen.findByText("Next steps"));
    fireEvent.click(await screen.findByRole("button", { name: "Start Decision Cycle" }));
    const create = await within(coque()).findByTestId("activity-create");
    expectSignalDesign(create, ACTIVITY_SECTIONS);
  });
});

describe("Edit contact — the Edit signal design (5.18)", () => {
  // Context → External contacts → the contact fiche → Edit.
  const openEditContact = async () => {
    fireEvent.click(await screen.findByText("Thomas Lefèvre"));
    fireEvent.click(await within(coque()).findByRole("button", { name: /edit/i }));
    await within(coque()).findByTestId("inline-read-first_name");
    return coque();
  };

  it("outside a DC: Identity, Contact", async () => {
    renderPage(activity());
    const drawer = await openEditContact();
    expect(within(drawer).getByTestId("coque-title")).toHaveTextContent("Edit contact");
    expectSignalDesign(drawer, ["Identity", "Contact"]);
  });

  it("inside a DC: Identity, Contact, Role in the decision", async () => {
    renderPage(dcActivity());
    const drawer = await openEditContact();
    expectSignalDesign(drawer, ["Identity", "Contact", "Role in the decision"]);
  });
});
