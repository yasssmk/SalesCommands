// frontend/src/__tests__/views/campaignsList.statusUrlParam.test.jsx
//
// The campaigns list view is addressable by ?status=<VALUE>: the URL seeds the
// initial filter (the Home "Active campaigns" card links here with ?status=ACTIVE
// so its destination lands pre-filtered). The URL only amorces — local drawer
// state wins afterwards, the URL is not rewritten on change nor cleaned on read.
//
// Real render: the page, the REAL useCampaignListFilters, MainCard and
// CampaignCard all render. Only DATA hooks, the framework font loader and the
// feature modals (not shared primitives) are mocked — same convention as
// campaignsList.multiselect.test.jsx.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, cleanup, renderHook, act } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import { useSearchParams } from "next/navigation";
import { useGetCampaigns } from "api/campaigns/campaigns";
import useCampaignListFilters from "hooks/useCampaignListFilters";
import CampaignsListPage from "views/campaigns/list";

// next/font is not executable outside a Next build — stub it (project convention).
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

// Data hooks mocked. useCampaignListFilters is NOT mocked — it is code under test.
vi.mock("api/campaigns/campaigns", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useGetCampaigns: vi.fn() };
});
vi.mock("api/territories/territories", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useGetTerritories: () => ({ territories: [] }) };
});

// Feature modals stubbed (not shared primitives) — same as the multiselect test.
vi.mock("sections/campaigns/create/CampaignCreateModal", () => ({ default: () => null }));
vi.mock("sections/campaigns/CampaignFilterPanel", () => ({ default: () => null }));
vi.mock("sections/campaigns/AlertCampaignDelete", () => ({ default: () => null }));
vi.mock("sections/campaigns/AlertCampaignBulkDelete", () => ({ default: () => null }));

const theme = createTheme();
const renderPage = () =>
  render(
    <ThemeProvider theme={theme}>
      <CampaignsListPage />
    </ThemeProvider>,
  );

// The `filters` object the view hands to the data hook on the latest render.
const lastRequestFilters = () => {
  const calls = vi.mocked(useGetCampaigns).mock.calls;
  return calls[calls.length - 1][0].filters;
};

beforeEach(() => {
  vi.mocked(useGetCampaigns).mockReturnValue({
    campaigns: [],
    campaignsCount: 0,
    campaignsLoading: false,
    campaignsError: null,
    campaignsEmpty: true,
    mutateCampaigns: vi.fn(),
  });
  // Default: no query params (overridden per test).
  vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams());
});
afterEach(cleanup);

describe("campaigns list — ?status URL seeds the initial filter (discriminant on the request)", () => {
  it("?status=ACTIVE → status=ACTIVE in the filters sent to the data hook", () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams("status=ACTIVE"));
    renderPage();
    expect(lastRequestFilters().status).toBe("ACTIVE");
  });

  it("no param → status is absent and owner_scope keeps its per-tier default (unchanged)", () => {
    renderPage(); // global mock returns empty params
    const f = lastRequestFilters();
    expect(f.status).toBeUndefined();
    // useAuth mock has no role_tier → individual fallback → 'mine'.
    expect(f.owner_scope).toBe("mine");
  });

  it("invalid value (?status=BANANA) → ignored, default applies, nothing forwarded", () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams("status=BANANA"));
    renderPage();
    expect(lastRequestFilters().status).toBeUndefined();
  });
});

describe("useCampaignListFilters — URL amorces, local state wins after", () => {
  it("seeds status from initialFilters, then a drawer change overrides it", () => {
    const { result } = renderHook(() => useCampaignListFilters({ status: "ACTIVE" }));
    expect(result.current.filters.status).toBe("ACTIVE");
    expect(result.current.apiFilters.status).toBe("ACTIVE");

    // The drawer changes the status → apply → local wins over the URL seed.
    act(() => result.current.updatePendingFilter("status", "PAUSED"));
    act(() => result.current.applyFilters());

    expect(result.current.filters.status).toBe("PAUSED");
    expect(result.current.apiFilters.status).toBe("PAUSED");
  });

  it("clear resets to the tier default, NOT the URL seed", () => {
    const { result } = renderHook(() => useCampaignListFilters({ status: "ACTIVE" }));
    act(() => result.current.clearFilters());
    expect(result.current.filters.status).toBe("");
    expect(result.current.apiFilters.status).toBeUndefined();
  });

  it("owner_scope keeps its tier default even when the URL seeds a status", () => {
    const { result } = renderHook(() => useCampaignListFilters({ status: "ACTIVE" }));
    expect(result.current.filters.owner_scope).toBe("mine"); // orthogonal to status
  });
});
