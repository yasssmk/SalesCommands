// frontend/src/views/accounts/dc-workspace/__tests__/DCWorkspace.loading.test.jsx
//
// FIX-LOADING-2 — the DC workspace page must not flash "Decision cycle not
// found" while the fetch is not yet resolved. The ids come from the route, so a
// null SWR key (tenantId hydrating) means "not resolved yet" → spinner, never
// "not found". "Not found" shows only on a real error.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "acc-1", cycleId: "cy-1" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => ({ get: () => null, toString: () => "" }),
}));

const useGetDecisionCyclesByAccount = vi.fn();
vi.mock("api/accounts/decisionCycles", () => ({
  useGetDecisionCyclesByAccount: (...a) => useGetDecisionCyclesByAccount(...a),
}));

vi.mock("components/WorkspaceLayout", () => ({
  default: () => <div data-testid="workspace-layout" />,
}));
vi.mock("components/WorkspaceBreadcrumb", () => ({
  __esModule: true,
  default: () => null,
  buildDCWorkspaceBreadcrumbs: () => [],
}));
vi.mock("sections/accounts/dc-workspace/DCWorkspaceHeader", () => ({ default: () => ({}) }));
vi.mock("sections/accounts/dc-workspace/DCWorkspaceTabs", () => ({
  DC_WORKSPACE_TABS: [{ id: "overview", label: "Overview" }],
  DEFAULT_TAB: "overview",
}));
vi.mock("utils/workspaceTabs", () => ({ resolveWorkspaceTab: () => "overview" }));
vi.mock("contexts/BreadcrumbContext", () => ({ useBreadcrumb: () => ({ setCrumbs: vi.fn() }) }));
vi.mock("sections/accounts/dc-workspace/TimelineTab", () => ({ default: () => null }));
vi.mock("sections/accounts/dc-workspace/SignalsTab", () => ({ default: () => null }));
vi.mock("sections/accounts/dc-workspace/ProductsTab", () => ({ default: () => null }));
vi.mock("sections/accounts/dc-workspace/PeopleTab", () => ({ default: () => null }));
vi.mock("sections/accounts/dc-workspace/StrategicTab", () => ({ default: () => null }));
vi.mock("sections/accounts/dc-workspace/OverviewTab", () => ({ default: () => null }));

import DCWorkspacePage from "views/accounts/dc-workspace/index";

function mockCycles(over = {}) {
  useGetDecisionCyclesByAccount.mockReturnValue({
    cycles: null,
    cyclesLoading: false,
    cyclesError: null,
    mutateCycles: vi.fn(),
    ...over,
  });
}

beforeEach(() => useGetDecisionCyclesByAccount.mockReset());
afterEach(() => cleanup());

describe("DCWorkspacePage — loading guard (no 'not found' flash)", () => {
  it("shows a spinner while loading, not 'Decision cycle not found'", () => {
    mockCycles({ cyclesLoading: true });
    render(<DCWorkspacePage />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.queryByText(/Decision cycle not found/i)).not.toBeInTheDocument();
  });

  it("shows a spinner (NOT 'not found') during the unresolved window: no data, no error", () => {
    mockCycles({ cyclesLoading: false, cycles: null, cyclesError: null });
    render(<DCWorkspacePage />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.queryByText(/Decision cycle not found/i)).not.toBeInTheDocument();
  });

  it("shows the error state only on a real error", () => {
    mockCycles({ cyclesLoading: false, cycles: null, cyclesError: new Error("500") });
    render(<DCWorkspacePage />);
    expect(screen.getByText(/Failed to load decision cycle/i)).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("renders the workspace content once the cycle resolves", () => {
    mockCycles({
      cyclesLoading: false,
      cycles: [{ id: "cy-1", name: "Q3 Renewal", account_name: "RED RUBAN" }],
    });
    render(<DCWorkspacePage />);
    expect(screen.getByTestId("workspace-layout")).toBeInTheDocument();
    expect(screen.queryByText(/Decision cycle not found/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});
