// frontend/src/views/accounts/workspace/__tests__/AccountWorkspace.loading.test.jsx
//
// FIX-LOADING-2 — the account workspace page must not flash "Account not found"
// while the fetch is not yet resolved. On this page the id always comes from the
// route, so a null SWR key (tenantId still hydrating) means "not resolved yet" →
// spinner, never "not found". "Account not found" shows only on a real error.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "acc-1" }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => ({ get: () => null, toString: () => "" }),
}));

const useGetAccountWorkspace = vi.fn();
vi.mock("api/admin/accounts", () => ({
  useGetAccountWorkspace: (...a) => useGetAccountWorkspace(...a),
  useGetAccountChoices: () => ({ industries: [], choicesLoading: false }),
  updateAccount: vi.fn(),
}));

// Isolate the branch under test: stub the layout (ignore children so the tab
// tree never mounts) and the header hook.
vi.mock("components/WorkspaceLayout", () => ({
  default: () => <div data-testid="workspace-layout" />,
}));
vi.mock("components/MainCard", () => ({
  default: ({ children }) => <div>{children}</div>,
}));
vi.mock("sections/accounts/workspace/AccountHeader", () => ({ default: () => ({}) }));
vi.mock("sections/accounts/workspace/AccountTabs", () => ({
  WORKSPACE_TABS: [{ id: "overview", label: "Overview" }],
  DEFAULT_TAB: "overview",
}));
vi.mock("utils/workspaceTabs", () => ({ resolveWorkspaceTab: () => "overview" }));
vi.mock("contexts/BreadcrumbContext", () => ({ useBreadcrumb: () => ({ setCrumbs: vi.fn() }) }));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
// Tab sections imported at module top — stub to keep the import light.
vi.mock("sections/accounts/contacts/AccountContactsTab", () => ({ default: () => null }));
vi.mock("sections/accounts/workspace/DecisionCycleTab", () => ({ default: () => null }));
vi.mock("sections/accounts/activities/AccountActivitiesTab", () => ({ default: () => null }));
vi.mock("sections/accounts/workspace/AccountSignalsTab", () => ({ default: () => null }));

import AccountWorkspacePage from "views/accounts/workspace/index";

function mockWorkspace(over = {}) {
  useGetAccountWorkspace.mockReturnValue({
    account: null,
    stats: null,
    workspaceLoading: false,
    workspaceError: null,
    mutateWorkspace: vi.fn(),
    ...over,
  });
}

beforeEach(() => useGetAccountWorkspace.mockReset());
afterEach(() => cleanup());

describe("AccountWorkspacePage — loading guard (no 'not found' flash)", () => {
  it("shows a spinner while loading (workspaceLoading true), not 'Account not found'", () => {
    mockWorkspace({ workspaceLoading: true });
    render(<AccountWorkspacePage />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.queryByText(/Account not found/i)).not.toBeInTheDocument();
  });

  it("shows a spinner (NOT 'not found') during the unresolved window: no data, no error", () => {
    // SWR key null (tenantId hydrating) → isLoading false, account null, no error.
    mockWorkspace({ workspaceLoading: false, account: null, workspaceError: null });
    render(<AccountWorkspacePage />);
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.queryByText(/Account not found/i)).not.toBeInTheDocument();
  });

  it("shows 'Account not found' only on a real error (404)", () => {
    mockWorkspace({ workspaceLoading: false, account: null, workspaceError: new Error("404") });
    render(<AccountWorkspacePage />);
    expect(screen.getByText(/Account not found/i)).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("renders the workspace content once the account resolves", () => {
    mockWorkspace({ workspaceLoading: false, account: { id: "acc-1", company_name: "RED RUBAN" } });
    render(<AccountWorkspacePage />);
    expect(screen.getByTestId("workspace-layout")).toBeInTheDocument();
    expect(screen.queryByText(/Account not found/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});
