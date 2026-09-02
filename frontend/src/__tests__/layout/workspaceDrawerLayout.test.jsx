// frontend/src/__tests__/layout/workspaceDrawerLayout.test.jsx
//
// UX Activity L2 — the workspace drawer coque is mounted at the LAYOUT level and
// anchored BELOW the breadcrumb.
//
// Mounts the real DashboardLayout with a child page that (a) declares a trail
// and (b) can openDrawer. Asserts:
//   (a) from ANY page (a list, i.e. a plain page NOT using WorkspaceLayout),
//       openDrawer(node) opens the shared coque and renders the node — the
//       provider is now in scope everywhere;
//   (b) the coque opens BELOW the breadcrumb: the breadcrumb bar stays outside
//       the [content][coque] flex-row (never pushed), content + coque sit side
//       by side (push) with no backdrop on large screens;
//   (c) on a narrow screen the coque is an overlay (backdrop present).
//
// RED before L2: the provider + coque live in WorkspaceLayout, not the layout —
// so a plain page cannot open the coque (useWorkspaceDrawer is the no-op default)
// and there is no coque under the breadcrumb.

import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { render, screen, within, fireEvent, cleanup } from "@testing-library/react";
import { useEffect } from "react";
import AphoriqTheme from "../_utils/aphoriqTheme";

vi.mock("next/font/google", () => ({
  Inter: () => ({ className: "mock", style: { fontFamily: "mock" } }),
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

// Push vs overlay is driven by useMediaQuery(down('lg')); control it per test.
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
import useMediaQuery from "@mui/material/useMediaQuery";

vi.mock("next/navigation", () => ({
  usePathname: () => "/accounts",
  useRouter: () => ({ push: vi.fn() }),
}));

// Heavy chrome mocked away; the menu-state singleton the coque provider reads.
vi.mock("layout/DashboardLayout/Header", () => ({ default: () => null }));
vi.mock("layout/DashboardLayout/Drawer", () => ({ default: () => null }));
vi.mock("layout/DashboardLayout/Footer", () => ({ default: () => null }));
vi.mock("layout/DashboardLayout/Drawer/HorizontalBar", () => ({ default: () => null }));
const handlerDrawerOpen = vi.fn();
vi.mock("hooks/useMenuState", () => ({
  useMenuState: () => ({
    menuMasterLoading: false,
    menuMaster: { isDashboardDrawerOpened: false },
    handlerDrawerOpen,
  }),
}));
vi.mock("hooks/useConfig", () => ({
  default: () => ({ container: false, miniDrawer: false, menuOrientation: "vertical" }),
}));

import DashboardLayout from "layout/DashboardLayout";
import { useBreadcrumb } from "contexts/BreadcrumbContext";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";

// A plain page (like a list) — does NOT use WorkspaceLayout. It declares a trail
// and can open the shared coque.
function ListLikePage() {
  const { setCrumbs } = useBreadcrumb();
  const { openDrawer, closeDrawer } = useWorkspaceDrawer();
  useEffect(() => {
    setCrumbs([{ label: "Accounts" }]);
  }, [setCrumbs]);
  return (
    <div>
      <div data-testid="page-content" />
      <button onClick={() => openDrawer(<div data-testid="coque-content">detail</div>)}>
        open
      </button>
      <button onClick={closeDrawer}>close</button>
    </div>
  );
}

function renderLayout() {
  return render(
    <AphoriqTheme>
      <DashboardLayout>
        <ListLikePage />
      </DashboardLayout>
    </AphoriqTheme>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useMediaQuery.mockReturnValue(false); // large by default
});
afterEach(() => cleanup());

describe("Workspace drawer coque at the layout level (L2)", () => {
  it("(a) opens from a plain page (list) — provider is in scope everywhere", () => {
    renderLayout();
    // closed initially
    expect(screen.queryByTestId("coque-content")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "open" }));

    // the shared coque rendered the injected node — impossible before L2
    expect(screen.getByTestId("coque-content")).toBeInTheDocument();
  });

  it("(b) coque opens BELOW the breadcrumb (breadcrumb outside the row) — push, no backdrop", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: "open" }));

    const row = screen.getByTestId("content-coque-row");
    // page content + coque are side by side inside the row (push)
    expect(within(row).getByTestId("page-content")).toBeInTheDocument();
    expect(within(row).getByTestId("coque-content")).toBeInTheDocument();
    // the breadcrumb bar is NOT inside the row → it stays full-width above,
    // never pushed by the coque
    expect(within(row).queryByTestId("breadcrumb-bar")).not.toBeInTheDocument();
    expect(screen.getByTestId("breadcrumb-bar")).toBeInTheDocument();
    // push mode = no overlay backdrop
    expect(document.querySelector(".MuiBackdrop-root")).toBeNull();
  });

  it("(c) narrow screen → the coque is an overlay (backdrop present)", () => {
    useMediaQuery.mockReturnValue(true); // narrow
    renderLayout();

    fireEvent.click(screen.getByRole("button", { name: "open" }));

    expect(screen.getByTestId("coque-content")).toBeInTheDocument();
    expect(document.querySelector(".MuiBackdrop-root")).not.toBeNull();
  });
});
