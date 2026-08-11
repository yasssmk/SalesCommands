// frontend/src/__tests__/views/campaignsList.inactive.test.jsx
//
// End-to-end (page → card) proof that the inactivity signal renders on
// /campaigns: the REAL CampaignsListPage feeds the REAL CampaignCard the raw
// campaign objects from useGetCampaigns (only that data hook is mocked). A
// campaign with is_inactive:true must show the "Inactive" chip; an active one
// must not. This guards the exact path the running page uses.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import { useSearchParams } from "next/navigation";
import { useGetCampaigns } from "api/campaigns/campaigns";
import CampaignsListPage from "views/campaigns/list";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));
vi.mock("api/campaigns/campaigns", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useGetCampaigns: vi.fn() };
});
vi.mock("api/territories/territories", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useGetTerritories: () => ({ territories: [] }) };
});
vi.mock("sections/campaigns/create/CampaignCreateModal", () => ({ default: () => null }));
vi.mock("sections/campaigns/CampaignFilterPanel", () => ({ default: () => null }));
vi.mock("sections/campaigns/AlertCampaignDelete", () => ({ default: () => null }));
vi.mock("sections/campaigns/AlertCampaignBulkDelete", () => ({ default: () => null }));

const theme = createTheme();

function campaign(overrides = {}) {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    name: "Q3 Outbound",
    campaign_type: "OUTBOUND",
    channel_override: "AUTO",
    status: "ACTIVE",
    description: "",
    planned_start_date: "2026-01-01",
    planned_end_date: "2026-12-31",
    actual_start_date: null,
    actual_end_date: null,
    accounts_count: 3,
    activities_today: 0,
    targets_total: 10,
    targets_worked: 2,
    primary_objective: null,
    owner: { id: "u1", first_name: "Sam", last_name: "K" },
    owner_team: null,
    executor: null,
    executor_team: null,
    is_inactive: false,
    ...overrides,
  };
}

function mockList(campaigns) {
  vi.mocked(useGetCampaigns).mockReturnValue({
    campaigns,
    campaignsCount: campaigns.length,
    campaignsLoading: false,
    campaignsError: null,
    campaignsEmpty: campaigns.length === 0,
    mutateCampaigns: vi.fn(),
  });
}

const renderPage = () =>
  render(
    <ThemeProvider theme={theme}>
      <CampaignsListPage />
    </ThemeProvider>,
  );

beforeEach(() => {
  vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams());
});
afterEach(cleanup);

describe("campaigns list — inactivity chip renders on the real page", () => {
  it("shows the Inactive chip for an is_inactive campaign", () => {
    mockList([campaign({ is_inactive: true })]);
    renderPage();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("shows no Inactive chip for an active campaign", () => {
    mockList([campaign({ id: "22222222-2222-4222-8222-222222222222", is_inactive: false })]);
    renderPage();
    expect(screen.queryByText("Inactive")).not.toBeInTheDocument();
  });
});
