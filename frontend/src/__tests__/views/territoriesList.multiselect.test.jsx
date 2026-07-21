// frontend/src/__tests__/views/territoriesList.multiselect.test.jsx
//
// List-level multi-select behaviour for the territories view. Only data/filter
// hooks and the feature modals are mocked; the toolbar, select cluster, real
// TerritoryCard, Checkbox, Tooltip and IconButton all render for real.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import { useGetTerritories } from "api/territories/territories";
import TerritoriesListPage from "views/territories/list";

const theme = createTheme();
const renderPage = () =>
  render(
    <ThemeProvider theme={theme}>
      <TerritoriesListPage />
    </ThemeProvider>,
  );

// next/font is not executable outside a Next build — stub it (project convention).
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock-public-sans", style: { fontFamily: "mock" } }),
}));

// --- Data / filter hooks: mocked (not UI components) ------------------------

vi.mock("api/territories/territories", async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useGetTerritories: vi.fn(),
    useGetTerritoryWorkspace: () => ({
      stats: { accounts_count: 0, contacts_count: 0, activities_count: 0 },
      loading: false,
    }),
  };
});

vi.mock("api/admin/accounts", () => ({
  useGetAccounts: () => ({ accountsCount: 0, accountsLoading: false }),
}));

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

// --- Feature modals: stubbed (not shared primitives) ------------------------

vi.mock("sections/territories/TerritoryModal", () => ({ default: () => null }));
vi.mock("sections/territories/AlertTerritoryDelete", () => ({ default: () => null }));
vi.mock("sections/territories/AlertTerritoryBulkDelete", () => ({ default: () => null }));
vi.mock("sections/territories/TerritoryListFilterPanel", () => ({ default: () => null }));

// ---------------------------------------------------------------------------

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
  territory({ id: "sys", name: "All Accounts", is_system: true }),
  territory({ id: "t1", name: "Alpha" }),
  territory({ id: "t2", name: "Beta" }),
];

beforeEach(() => {
  vi.mocked(useGetTerritories).mockReturnValue({
    territories: FIXTURES,
    territoriesCount: FIXTURES.length,
    territoriesLoading: false,
    territoriesError: null,
  });
});

afterEach(cleanup);

const btnByIcon = (icon) =>
  document.querySelector(`[aria-label="${icon}"]`).closest("button");

async function enterSelectionMode(user) {
  await user.click(btnByIcon("check-square"));
}

describe("territories list — select cluster", () => {
  it("at rest shows an icon-only Select and no permanent counter text", () => {
    renderPage();
    expect(document.querySelector('[aria-label="check-square"]')).toBeTruthy();
    expect(screen.queryByText(/available/i)).toBeNull();
    expect(screen.queryByText(/\d+ territor(y|ies) selected/i)).toBeNull();
  });

  it("entering selection mode reveals the cluster with a disabled delete", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    expect(btnByIcon("close")).toBeInTheDocument();
    expect(btnByIcon("delete")).toBeDisabled();
    expect(screen.queryByText(/available/i)).toBeNull();
    expect(screen.queryByText(/\d+ territor(y|ies) selected/i)).toBeNull();
  });

  it("renders a checkbox for every non-system card and none for is_system", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    // master checkbox + 2 non-system card checkboxes = 3 (system excluded).
    expect(screen.getAllByRole("checkbox")).toHaveLength(3);
  });

  it("select-all excludes the system territory", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    const [master, ...cardBoxes] = screen.getAllByRole("checkbox");
    await user.click(master);

    expect(cardBoxes).toHaveLength(2);
    cardBoxes.forEach((cb) => expect(cb).toBeChecked());
    expect(btnByIcon("delete")).toBeEnabled();
  });

  it("the count lives only in the tooltips, not as permanent DOM text", async () => {
    const user = userEvent.setup();
    renderPage();
    await enterSelectionMode(user);

    const [master] = screen.getAllByRole("checkbox");
    await user.click(master); // select all (2)

    const outsideTooltip = (re) =>
      screen.queryAllByText(re).filter((el) => !el.closest('[role="tooltip"]'));
    expect(outsideTooltip(/2 selected/i)).toHaveLength(0);
    expect(outsideTooltip(/Select all \(2\)/i)).toHaveLength(0);

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
