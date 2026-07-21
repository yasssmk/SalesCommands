// frontend/src/__tests__/views/campaignsList.multiselect.test.jsx
//
// List-level multi-select behaviour for the campaigns view. Only data/filter
// hooks and the feature modals are mocked (per the project's mock convention);
// the toolbar, the select cluster, the real CampaignCard, Checkbox, Tooltip and
// IconButton all render for real.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import { useGetCampaigns } from "api/campaigns/campaigns";
import CampaignsListPage from "views/campaigns/list";

const theme = createTheme();
const renderPage = () =>
  render(
    <ThemeProvider theme={theme}>
      <CampaignsListPage />
    </ThemeProvider>,
  );

// next/font is not executable outside a Next build — stub it (project convention).
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

// --- Data / filter hooks: mocked (not UI components) ------------------------

vi.mock("api/campaigns/campaigns", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useGetCampaigns: vi.fn() };
});

vi.mock("api/territories/territories", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useGetTerritories: () => ({ territories: [] }) };
});

vi.mock("hooks/useCampaignListFilters", () => ({
  default: () => ({
    filters: { owner_scope: "all" },
    pendingFilters: { owner_scope: "all" },
    activeFiltersCount: 0,
    hasPendingChanges: false,
    apiFilters: {},
    updatePendingFilter: vi.fn(),
    applyFilters: vi.fn(),
    clearFilters: vi.fn(),
    resetPendingFilters: vi.fn(),
    removeFilter: vi.fn(),
  }),
}));

// --- Feature modals: stubbed (not shared primitives) ------------------------

vi.mock("sections/campaigns/create/CampaignCreateModal", () => ({ default: () => null }));
vi.mock("sections/campaigns/CampaignFilterPanel", () => ({ default: () => null }));
vi.mock("sections/campaigns/AlertCampaignDelete", () => ({ default: () => null }));
vi.mock("sections/campaigns/AlertCampaignBulkDelete", () => ({ default: () => null }));

// ---------------------------------------------------------------------------

function campaign(overrides = {}) {
  return {
    id: "id",
    name: "Name",
    campaign_type: "OUTBOUND",
    status: "DRAFT",
    accounts_count: 1,
    activities_total: 2,
    activities_completed: 1,
    members: [],
    ...overrides,
  };
}

const FIXTURES = [
  campaign({ id: "targeted", name: "My Targets", campaign_type: "TARGETED" }),
  campaign({ id: "c1", name: "Alpha" }),
  campaign({ id: "c2", name: "Beta" }),
];

beforeEach(() => {
  vi.mocked(useGetCampaigns).mockReturnValue({
    campaigns: FIXTURES,
    campaignsCount: FIXTURES.length,
    campaignsLoading: false,
    campaignsError: null,
    campaignsEmpty: false,
    mutateCampaigns: vi.fn(),
  });
});

afterEach(cleanup);

const btnByIcon = (icon) =>
  document.querySelector(`[aria-label="${icon}"]`).closest("button");

async function enterSelectionMode(user) {
  await user.click(btnByIcon("check-square"));
}

describe("campaigns list — select cluster", () => {
  it("at rest shows an icon-only Select and no permanent counter text", () => {
    renderPage();
    // Icon-only Select present (antd check-square icon).
    expect(document.querySelector('[aria-label="check-square"]')).toBeTruthy();
    // No band / permanent counter text (no tooltip is open here).
    expect(screen.queryByText(/available/i)).toBeNull();
    expect(screen.queryByText(/\d+ campaign(s)? selected/i)).toBeNull();
  });

  it("entering selection mode reveals the cluster with a disabled delete", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    // Cluster icons: cancel (close) + delete; delete disabled at 0 selected.
    expect(btnByIcon("close")).toBeInTheDocument();
    expect(btnByIcon("delete")).toBeDisabled();
    // Still no permanent counter text before hovering.
    expect(screen.queryByText(/available/i)).toBeNull();
    expect(screen.queryByText(/\d+ campaign(s)? selected/i)).toBeNull();
  });

  it("renders a checkbox for every non-TARGETED card and none for TARGETED", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    // master checkbox + 2 non-TARGETED card checkboxes = 3 (TARGETED excluded).
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("select-all excludes the TARGETED singleton", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    const [master, ...cardBoxes] = screen.getAllByRole("checkbox");
    await user.click(master);

    // Both non-TARGETED card checkboxes are now checked.
    expect(cardBoxes).toHaveLength(2);
    cardBoxes.forEach((cb) => expect(cb).toBeChecked());
    // Delete becomes enabled once there is a selection.
    expect(btnByIcon("delete")).toBeEnabled();
  });

  it("the count lives only in the tooltips, not as permanent DOM text", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    const [master] = screen.getAllByRole("checkbox");
    await user.click(master); // select all (2)

    // No visible counter text outside a tooltip while nothing is hovered.
    const outsideTooltip = (re) =>
      screen.queryAllByText(re).filter((el) => !el.closest('[role="tooltip"]'));
    expect(outsideTooltip(/2 selected/i)).toHaveLength(0);
    expect(outsideTooltip(/Select all \(2\)/i)).toHaveLength(0);

    // Hovering the delete surfaces the count in a tooltip.
    await user.hover(btnByIcon("delete"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Delete 2 selected");
  });

  it("the master checkbox tooltip carries the selectable count", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    const [master] = screen.getAllByRole("checkbox");
    await user.hover(master);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Select all (2)");
  });
});
