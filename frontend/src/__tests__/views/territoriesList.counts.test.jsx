// frontend/src/__tests__/views/territoriesList.counts.test.jsx
//
// The list fetches counts for the visible page in ONE batched POST
// (useGetTerritoryCounts) and prop-drills each card its number — replacing the
// per-card workspace N+1. Data hooks are mocked; the real TerritoryCard renders.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import {
  useGetTerritories,
  useGetTerritoryCounts,
} from "api/territories/territories";
import TerritoriesListPage from "views/territories/list";

const theme = createTheme();
const renderPage = () =>
  render(
    <ThemeProvider theme={theme}>
      <TerritoriesListPage />
    </ThemeProvider>,
  );

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

vi.mock("hooks/useTerritoryListFilters", () => ({
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

vi.mock("sections/territories/TerritoryModal", () => ({ default: () => null }));
vi.mock("sections/territories/AlertTerritoryDelete", () => ({ default: () => null }));
vi.mock("sections/territories/AlertTerritoryBulkDelete", () => ({ default: () => null }));
vi.mock("sections/territories/TerritoryListFilterPanel", () => ({ default: () => null }));

function territory(overrides = {}) {
  return {
    id: "id",
    name: "Name",
    type: "ACCOUNT",
    description: "",
    is_system: false,
    filter_definition: {},
    ...overrides,
  };
}

const FIXTURES = [
  territory({ id: "t1", name: "Alpha", type: "ACCOUNT" }),
  territory({ id: "t2", name: "Beta", type: "CONTACT" }),
];

beforeEach(() => {
  vi.mocked(useGetTerritories).mockReturnValue({
    territories: FIXTURES,
    territoriesCount: FIXTURES.length,
    territoriesLoading: false,
    territoriesError: null,
  });
  vi.mocked(useGetTerritoryCounts).mockReturnValue({
    counts: {
      t1: { type: "ACCOUNT", count: 11 },
      t2: { type: "CONTACT", count: 22 },
    },
    countsLoading: false,
    countsError: null,
  });
});

afterEach(cleanup);

describe("territories list — batched counts consumption", () => {
  it("calls useGetTerritoryCounts with the visible page ids", () => {
    renderPage();
    const [idsArg] = vi.mocked(useGetTerritoryCounts).mock.calls.at(-1);
    expect(idsArg).toEqual(["t1", "t2"]);
  });

  it("prop-drills each card its batched count (account + contact)", () => {
    renderPage();
    expect(screen.getByText("11")).toBeInTheDocument();
    expect(screen.getByText("22")).toBeInTheDocument();
  });
});
