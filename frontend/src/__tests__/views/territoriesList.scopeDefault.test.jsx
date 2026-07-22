// frontend/src/__tests__/views/territoriesList.scopeDefault.test.jsx
//
// List-level smoke: the real useTerritoryListFilters seeds owner_scope by tier,
// so a manager lands with the removable "Scope: My Team ✕" chip and an admin
// with none. Only data hooks + modals are mocked; the filters hook and the real
// chip rendering run for real. Mirrors territoriesList.multiselect.test.jsx.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import { useAuth } from "hooks/useAuth";
import {
  useGetTerritories,
  useGetTerritoryCounts,
} from "api/territories/territories";
import TerritoriesListPage from "views/territories/list";

// Spy useAuth so each test sets the tier (the filters hook reads it at seed).
vi.mock("hooks/useAuth", () => ({ useAuth: vi.fn() }));

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

vi.mock("api/territories/territories", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useGetTerritories: vi.fn(),
    useGetTerritoryCounts: vi.fn(),
  };
});

vi.mock("sections/territories/TerritoryModal", () => ({ default: () => null }));
vi.mock("sections/territories/AlertTerritoryDelete", () => ({ default: () => null }));
vi.mock("sections/territories/AlertTerritoryBulkDelete", () => ({ default: () => null }));
vi.mock("sections/territories/TerritoryListFilterPanel", () => ({ default: () => null }));

const theme = createTheme();
const renderPage = () =>
  render(
    <ThemeProvider theme={theme}>
      <TerritoriesListPage />
    </ThemeProvider>,
  );

// Real /me (UserSerializer) shape: `role` is a bare UUID string, tier is the
// top-level `role_tier`, is_manager/is_superuser are flat booleans.
const asTier = (role_tier) =>
  vi.mocked(useAuth).mockReturnValue({
    user: {
      id: "u1",
      role: "5f3e9c00-0000-0000-0000-000000000001",
      role_tier,
      is_manager: role_tier === "manager",
      is_superuser: false,
    },
    isAuthenticated: true,
    tenantId: "test-tenant-id",
  });

beforeEach(() => {
  vi.mocked(useGetTerritories).mockReturnValue({
    territories: [],
    territoriesCount: 0,
    territoriesLoading: false,
    territoriesError: null,
  });
  vi.mocked(useGetTerritoryCounts).mockReturnValue({
    counts: {},
    countsLoading: false,
    countsError: null,
  });
});

afterEach(cleanup);

describe("territories list — tier-based default scope chip", () => {
  it("manager lands with the 'Scope: My Team' chip", () => {
    asTier("manager");
    renderPage();
    expect(screen.getByText("Scope: My Team")).toBeInTheDocument();
  });

  it("individual lands with the 'Scope: Mine' chip", () => {
    asTier("individual");
    renderPage();
    expect(screen.getByText("Scope: Mine")).toBeInTheDocument();
  });

  it("admin lands with no scope chip (default is 'all')", () => {
    asTier("admin");
    renderPage();
    expect(screen.queryByText(/^Scope:/)).toBeNull();
  });
});
