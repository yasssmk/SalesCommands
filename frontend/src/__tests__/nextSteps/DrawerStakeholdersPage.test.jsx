// frontend/src/__tests__/nextSteps/DrawerStakeholdersPage.test.jsx
//
// Sprint « Cycle de vie des contacts », étapes 7 (3) / 7c — on the Activity
// workspace PAGE, the Edit activity drawer (create AND edit), section People:
// ONE « Stakeholders » list and ONE « Add stakeholder » picker (7c: no « Add
// contact », no « New contact », no « Contact » / « Not yet a contact »
// marker). The picker reads the REAL endpoints through the real hooks: every
// stakeholder of the DC (GET /decision_cycles/{id}/stakeholders/, converted
// or not) + the account contacts (GET /contacts/?account_id=…) not yet
// stakeholders of it; without a DC, the account contacts.
// REAL: the page, the header ⋯ menu, the Next steps band, the coque, the
// drawers, the API hooks (SWR fetcher). Mocked: the HTTP client.
// Harness of DrawerSectionsPage.test.jsx.

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


const MARC_ST = { id: "st-marc", display_name: "Marc", full_name: "Marc", department: null,
                  is_linked: false, decision_cycle: "44444444-4444-4444-8444-444444444444" };
const FIN_ST = { id: "st-fin", display_name: "Finance", full_name: "",
                 department: { id: 7, name: "Finance" }, is_linked: false,
                 decision_cycle: "44444444-4444-4444-8444-444444444444" };
// A converted stakeholder: offered once, under its contact's name.
const PAUL_C = { id: "c-paul", first_name: "Paul", last_name: "X", full_name: "Paul X" };
const PAUL_ST = { id: "st-paul", display_name: "Paul X", full_name: "", department: null,
                  is_linked: true, contact: PAUL_C,
                  decision_cycle: "44444444-4444-4444-8444-444444444444" };
const ZOE = { id: "c-zoe", first_name: "Zoe", last_name: "Martin", full_name: "Zoe Martin" };
let serverActivity;
let fetchedUrls = [];
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  fetchedUrls.push(url);
  if (url.startsWith(`/module-activities/${ACT_ID}`)) return Promise.resolve({ data: serverActivity });
  if (url.startsWith(`/contacts/${C_ID}/`)) return Promise.resolve({ data: THOMAS });
  if (url.startsWith(`/decision_cycles/${DC_ID}/stakeholders/`)) {
    return Promise.resolve({ data: [MARC_ST, FIN_ST, PAUL_ST] });
  }
  if (url.startsWith("/contacts/") && url.includes(ACC_ID)) {
    return Promise.resolve({ data: { results: [THOMAS, ZOE, PAUL_C], count: 3 } });
  }
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


const openPicker = (root) => {
  fireEvent.click(within(root).getByTestId("add-stakeholder"));
  const input = within(within(root).getByTestId("stakeholder-select")).getByRole("combobox");
  fireEvent.focus(input);
  fireEvent.keyDown(input, { key: "ArrowDown" });
};
const optionNames = async () => (await screen.findAllByRole("option")).map((o) => o.textContent);

beforeEach(() => { fetchedUrls = []; });

describe("Edit activity on the page — ONE « Add stakeholder », no distinction (7c)", () => {
  it("create (« + Add next step » → Meeting): the DC's stakeholders + the account contacts, unmarked", async () => {
    renderPage(dcActivity({ contacts_detail: [] }));
    fireEvent.click(await screen.findByRole("button", { name: "+ Add next step" }));
    fireEvent.click(within(screen.getByTestId("add-next-step-types")).getByRole("button", { name: "Meeting" }));
    const create = await within(coque()).findByTestId("activity-create");
    const list = within(create).getByTestId("stakeholders-list");
    expect(within(list).getByText("Stakeholders")).toBeInTheDocument();
    expect(within(create).queryByTestId("add-contact")).toBeNull();
    expect(within(create).queryByTestId("add-inline-contact")).toBeNull();
    openPicker(create);
    await waitFor(async () =>
      expect((await optionNames()).sort()).toEqual(["Finance", "Marc", "Paul X", "Thomas Lefèvre", "Zoe Martin"]));
    fireEvent.click(screen.getByRole("option", { name: "Marc" }));
    expect(within(list).getByTestId("participant-st-marc").textContent).toBe("Marc");
    expect(list.textContent).not.toMatch(/Not yet a contact/);
    expect(screen.queryByRole("option", { name: "Marc" })).toBeNull();
  });

  it("outside a DC: « Add stakeholder » offers the account contacts", async () => {
    renderPage(activity());
    const drawer = await openEditActivity();
    expect(within(drawer).queryByTestId("add-contact")).toBeNull();
    expect(within(drawer).getByTestId("participant-" + C_ID).textContent).not.toMatch(/Contact/);
    openPicker(drawer);
    await waitFor(async () => expect((await optionNames()).sort()).toEqual(["Paul X", "Zoe Martin"]));
  });

  it("edit: the contacts and the stakeholders, unmarked (a department shown as such)", async () => {
    renderPage(dcActivity({ stakeholders_detail: [MARC_ST, FIN_ST] }));
    const drawer = await openEditActivity();
    expect(within(drawer).getByTestId("participant-" + C_ID).textContent).not.toMatch(/Contact/);
    expect(within(drawer).getByTestId("participant-st-marc").textContent).not.toMatch(/Not yet a contact/);
    expect(within(drawer).getByTestId("participant-st-fin")).toHaveTextContent("Finance");
    expect(within(drawer).queryByTestId("add-contact")).toBeNull();
  });
});

// 7d-1 — the picker is the standard AsyncContactSelect: a SERVER search, on the
// account contacts AND the DC's non-converted stakeholders (never the 7c read
// of 100 contacts).
describe("« Add stakeholder » searches the server (7d-1)", () => {
  it("typing searches the contacts and the non-converted stakeholders on the server", async () => {
    renderPage(dcActivity({ contacts_detail: [] }));
    fireEvent.click(await screen.findByRole("button", { name: "+ Add next step" }));
    fireEvent.click(within(screen.getByTestId("add-next-step-types")).getByRole("button", { name: "Meeting" }));
    const create = await within(coque()).findByTestId("activity-create");
    openPicker(create);
    const input = within(within(create).getByTestId("stakeholder-select")).getByRole("combobox");
    fireEvent.change(input, { target: { value: "Ma" } });
    await waitFor(() => {
      expect(fetchedUrls.some((u) => u.startsWith("/contacts/") && u.includes(`account_id=${ACC_ID}`)
        && u.includes("search=Ma") && u.includes("page_size=20"))).toBe(true);
      expect(fetchedUrls.some((u) => u.startsWith(`/decision_cycles/${DC_ID}/stakeholders/`)
        && u.includes("converted=false") && u.includes("search=Ma"))).toBe(true);
    }, { timeout: 2000 });
    expect(fetchedUrls.some((u) => u.startsWith("/contacts/") && u.includes("page_size=100"))).toBe(false);
  });
});
