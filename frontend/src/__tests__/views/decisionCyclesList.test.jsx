// frontend/src/__tests__/views/decisionCyclesList.test.jsx
//
// The Decision Cycles list view, sub-step 3: the per-row dc_cycle_state KPI call
// is gone (stage + status now come from the list serializer), the eight columns
// are all server-sortable, and the drawer carries eight facets.
//
// Real render: the page, the REAL useDecisionCycleFilters, the REAL ReusableTable
// and the REAL DecisionCycleFilterPanel all render. Only DATA hooks and the font
// loader are mocked (project convention — mocking shared primitives hides the
// TanStack sort / toolbar contract bugs these tests exist to catch).
//
// Discriminating assertions: every check reads what actually reaches the data
// hook — the { ordering, filters } options handed to useGetDecisionCycles — not
// the presence of some text.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, cleanup, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import Palette from "themes/palette";
import Typography from "themes/typography";
import CustomShadows from "themes/shadows";

import { useGetDecisionCycles } from "api/accounts/decisionCycles";
import { useKpiBatch } from "api/bi/kpi";
import DecisionCyclesListPage from "views/businessData/decisionCycles/list";

// ---- next / font ---------------------------------------------------------- //
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

// ---- next / navigation ---------------------------------------------------- //
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => ({ entries: () => [], toString: () => "", keys: () => [] }),
}));

// ---- framework glue (not shared UI primitives) ----------------------------- //
vi.mock("swr", () => ({ useSWRConfig: () => ({ mutate: vi.fn() }) }));
vi.mock("hooks/useLocalStorage", () => ({ default: (_k, init) => [init, vi.fn()] }));

// ---- auth (admin tier → owner_scope 'all', a clean baseline) --------------- //
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({
    user: { id: "u1", role: "Admin", role_tier: "admin", is_superuser: true },
    tenantId: "t1",
    isAuthenticated: true,
  }),
}));

// ---- the list data hook (code under test forwards ordering/filters here) ---- //
vi.mock("api/accounts/decisionCycles", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useGetDecisionCycles: vi.fn() };
});

// ---- the KPI batch hook: it must NOT be called by this view anymore -------- //
vi.mock("api/bi/kpi", () => ({ useKpiBatch: vi.fn(() => ({ results: [] })) }));

// ---- selector data hooks (async + static lookups) -------------------------- //
vi.mock("api/admin/accounts", () => ({
  useGetAccounts: () => ({ accounts: [{ id: "acc1", company_name: "Acme Co" }] }),
}));
vi.mock("api/admin/users", () => ({
  useGetUsers: () => ({
    users: [{ id: "usr1", first_name: "Olga", last_name: "Owner", email: "olga@x.io" }],
  }),
}));
vi.mock("api/admin/teams", () => ({
  useGetTeams: () => ({ teams: [{ id: "team1", name: "Team Alpha" }] }),
}));
vi.mock("api/businessData/contacts", () => ({
  useGetContacts: () => ({ contacts: [{ id: "con1", first_name: "Carl", last_name: "Contact" }] }),
}));
vi.mock("api/campaigns/campaigns", () => ({
  useGetCampaigns: () => ({ campaigns: [{ id: "camp1", name: "Camp One" }] }),
}));
vi.mock("api/businessData/productCatalog", () => ({
  useGetProductCatalogEntries: () => ({ entries: [{ id: "prod1", name: "Prod One" }] }),
}));

// ---- fixture rows served by the (mocked) list hook ------------------------- //
const CYCLES = [
  {
    id: "dc1",
    account: "acc1",
    account_name: "Acme Co",
    cycle_name: "Alpha deal",
    name: "Alpha deal",
    owner: "usr1",
    owner_name: "Olga Owner",
    owner_email: "olga@x.io",
    team: { id: "team1", name: "Team Alpha" },
    outcome: null,
    cycle_status: "IN_PROGRESS",
    current_stage: "QUALIFICATION",
    current_step_name: "Qualification",
    estimated_value: "1000.00",
    steps_count: 5,
    validated_steps_count: 1,
    updated_at: "2026-07-01T10:00:00Z",
  },
  {
    id: "dc2",
    account: "acc2",
    account_name: "Beta Inc",
    cycle_name: "Beta deal",
    name: "Beta deal",
    owner: "usr2",
    owner_name: "Zed Zeta",
    owner_email: "zed@x.io",
    team: { id: "team2", name: "Team Beta" },
    outcome: "LOST",
    cycle_status: "LOST",
    current_stage: null,
    current_step_name: "Closing",
    estimated_value: "500.00",
    steps_count: 5,
    validated_steps_count: 3,
    updated_at: "2026-06-01T10:00:00Z",
  },
];

const paletteTheme = Palette("light", "default");
const theme = createTheme({
  breakpoints: { values: { xs: 0, sm: 768, md: 1024, lg: 1266, xl: 1440 } },
  palette: paletteTheme.palette,
  customShadows: CustomShadows(paletteTheme),
  typography: Typography(`'Public Sans', sans-serif`),
});

const renderPage = () =>
  render(
    <ThemeProvider theme={theme}>
      <DecisionCyclesListPage />
    </ThemeProvider>,
  );

// The options object the view hands to useGetDecisionCycles on the latest render.
const lastRequest = () => {
  const calls = vi.mocked(useGetDecisionCycles).mock.calls;
  return calls[calls.length - 1][0];
};

beforeEach(() => {
  vi.mocked(useGetDecisionCycles).mockReturnValue({
    cycles: CYCLES,
    cyclesCount: CYCLES.length,
    cyclesLoading: false,
    cyclesError: null,
  });
  vi.mocked(useKpiBatch).mockClear();
});

afterEach(cleanup);

// Open the advanced-filter drawer via the toolbar funnel (ant icon, role img).
async function openDrawer(user) {
  const funnel = screen.getByRole("img", { name: "filter" });
  await user.click(funnel.closest("button"));
  await screen.findByRole("button", { name: "Apply" });
}

// =============================================================================
// KPI removal + serializer-served stage/status
// =============================================================================

describe("Decision Cycles list — no KPI, serializer-served state", () => {
  it("never calls the dc_cycle_state KPI batch", () => {
    renderPage();
    expect(vi.mocked(useKpiBatch)).not.toHaveBeenCalled();
  });

  it("shows stage and status from the serializer fields", () => {
    renderPage();
    // Stage column reads current_step_name; Status reads cycle_status/outcome.
    expect(screen.getByText("Qualification")).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument(); // dc1 derived
    expect(screen.getByText("Lost")).toBeInTheDocument(); // dc2 outcome
  });
});

// =============================================================================
// Sorting — one header per column, ascending then descending
// =============================================================================

describe("Decision Cycles list — server sorting on all 8 columns", () => {
  const CASES = [
    ["Decision Cycle", "name"],
    ["Account", "account__company_name"],
    ["Stage", "_current_step_stage"],
    ["Status", "_cycle_effective_status"],
    ["Amount", "estimated_value"],
    ["Owner", "owner__first_name"],
    ["Team", "owner__team__name"],
    ["Last Updated", "updated_at"],
  ];

  // Two consecutive header clicks toggle ascending and descending. TanStack
  // picks the first direction from the column's inferred type (object / accessor
  // -less columns start descending), so we assert the two clicks produce BOTH
  // the ascending (`field`) and the descending (`-field`) param, order-agnostic.
  it.each(CASES)("column %s produces asc + desc ordering → %s", async (header, field) => {
    const user = userEvent.setup();
    renderPage();
    const th = screen.getByText(header);

    await user.click(th);
    await waitFor(() => expect(lastRequest().ordering).not.toBe(""));
    const first = lastRequest().ordering;

    await user.click(th);
    await waitFor(() => expect(lastRequest().ordering).not.toBe(first));
    const second = lastRequest().ordering;

    expect(new Set([first, second])).toEqual(new Set([field, `-${field}`]));
  });
});

// =============================================================================
// Facets — selection in the drawer → the exact backend param in the request
// =============================================================================

describe("Decision Cycles list — drawer facets reach the request", () => {
  async function selectAutocomplete(user, label, optionRe) {
    const input = screen.getByRole("combobox", { name: label });
    await user.click(input);
    await user.click(await screen.findByRole("option", { name: optionRe }));
  }

  async function selectDropdown(user, label, optionName) {
    await user.click(screen.getByRole("combobox", { name: label }));
    const listbox = await screen.findByRole("listbox");
    await user.click(within(listbox).getByRole("option", { name: optionName }));
  }

  async function apply(user) {
    await user.click(screen.getByRole("button", { name: "Apply" }));
  }

  it("status (from outcome) → status=LOST", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await selectDropdown(user, "Status", "Lost");
    await apply(user);
    await waitFor(() => expect(lastRequest().filters.status).toBe("LOST"));
  });

  it("status (derived) → status=STALLED", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await selectDropdown(user, "Status", "Stalled");
    await apply(user);
    await waitFor(() => expect(lastRequest().filters.status).toBe("STALLED"));
  });

  it("account → account=acc1", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await selectAutocomplete(user, "Account", /Acme Co/);
    await apply(user);
    await waitFor(() => expect(lastRequest().filters.account).toBe("acc1"));
  });

  it("owner → owner=usr1", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await selectAutocomplete(user, "Owner", /Olga Owner/);
    await apply(user);
    await waitFor(() => expect(lastRequest().filters.owner).toBe("usr1"));
  });

  it("team → team=team1", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await selectAutocomplete(user, "Team", /Team Alpha/);
    await apply(user);
    await waitFor(() => expect(lastRequest().filters.team).toBe("team1"));
  });

  it("contact → contact=con1", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await selectAutocomplete(user, "Contact", /Carl Contact/);
    await apply(user);
    await waitFor(() => expect(lastRequest().filters.contact).toBe("con1"));
  });

  it("source campaign → source_campaign=camp1", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await selectDropdown(user, "Source campaign", "Camp One");
    await apply(user);
    await waitFor(() => expect(lastRequest().filters.source_campaign).toBe("camp1"));
  });

  it("product → product=prod1", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await selectDropdown(user, "Product", "Prod One");
    await apply(user);
    await waitFor(() => expect(lastRequest().filters.product).toBe("prod1"));
  });
});

// =============================================================================
// Chips — an applied facet renders a removable chip; removing it drops the param
// =============================================================================

describe("Decision Cycles list — facet chips are removable", () => {
  it("status chip renders and removing it drops status from the next request", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    await user.click(screen.getByRole("combobox", { name: "Status" }));
    const listbox = await screen.findByRole("listbox");
    await user.click(within(listbox).getByRole("option", { name: "Lost" }));
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(lastRequest().filters.status).toBe("LOST"));

    // the chip is shown …
    const chip = (await screen.findByText("Status: Lost")).closest(".MuiChip-root");
    expect(chip).toBeTruthy();

    // … and removing it clears the param on the following request.
    await user.click(chip.querySelector(".MuiChip-deleteIcon"));
    await waitFor(() => expect(lastRequest().filters.status).toBeUndefined());
  });

  it("owner facet renders its own chip", async () => {
    const user = userEvent.setup();
    renderPage();
    await openDrawer(user);
    const input = screen.getByRole("combobox", { name: "Owner" });
    await user.click(input);
    await user.click(await screen.findByRole("option", { name: /Olga Owner/ }));
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(lastRequest().filters.owner).toBe("usr1"));
    expect(await screen.findByText(/Owner: Olga Owner/)).toBeInTheDocument();
  });
});
