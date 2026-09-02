// frontend/src/__tests__/layout/breadcrumbSingle.test.jsx
//
// UX Activity L1 — a SINGLE contextual breadcrumb at the layout.
//
// Mounts the real DashboardLayout with a child page that declares its trail via
// useBreadcrumb, and asserts:
//   - exactly ONE breadcrumb is rendered — the contextual BreadcrumbBar — and
//     the legacy menu-derived @extended/Breadcrumbs is GONE (no duplicate);
//   - the page's pushed trail renders in that single bar, with href segments as
//     clickable links and the last (current page) as plain text.
//
// RED before L1: the layout still renders the legacy breadcrumb alongside the
// bar (double). GREEN after L1 removes the legacy.

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import { useEffect } from "react";
import AphoriqTheme from "../_utils/aphoriqTheme";

// config (theme-config.js) calls next/font at import time — not loadable in jsdom.
vi.mock("next/font/google", () => ({
  Inter: () => ({ className: "mock", style: { fontFamily: "mock" } }),
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

// Deterministic layout mode (avoid jsdom matchMedia).
vi.mock("@mui/material/useMediaQuery", () => ({ default: () => false }));

// next/navigation: pathname drives the legacy breadcrumb's render condition;
// useRouter backs the bar's clickable segments.
vi.mock("next/navigation", () => ({
  usePathname: () => "/campaigns",
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock the heavy chrome so only the breadcrumb composition is under test.
vi.mock("layout/DashboardLayout/Header", () => ({ default: () => null }));
vi.mock("layout/DashboardLayout/Drawer", () => ({ default: () => null }));
vi.mock("layout/DashboardLayout/Footer", () => ({ default: () => null }));
vi.mock("layout/DashboardLayout/Drawer/HorizontalBar", () => ({ default: () => null }));
vi.mock("hooks/useMenuState", () => ({
  useMenuState: () => ({ menuMasterLoading: false }),
}));
vi.mock("hooks/useConfig", () => ({
  default: () => ({ container: false, miniDrawer: false, menuOrientation: "vertical" }),
}));

// The legacy menu-derived breadcrumb → a marker so we can detect the duplicate.
vi.mock("components/@extended/Breadcrumbs", () => ({
  default: () => <div data-testid="legacy-breadcrumb" />,
}));

import DashboardLayout from "layout/DashboardLayout";
import { useBreadcrumb } from "contexts/BreadcrumbContext";

// A child page (rendered inside the layout's BreadcrumbProvider) declaring its
// trail, exactly as a real page does.
function FilPusher() {
  const { setCrumbs } = useBreadcrumb();
  useEffect(() => {
    setCrumbs([{ label: "Campaigns", href: "/campaigns" }, { label: "ACME" }]);
  }, [setCrumbs]);
  return <div data-testid="page" />;
}

function renderLayout() {
  return render(
    <AphoriqTheme>
      <DashboardLayout>
        <FilPusher />
      </DashboardLayout>
    </AphoriqTheme>,
  );
}

afterEach(() => cleanup());

describe("Single contextual breadcrumb at the layout (L1)", () => {
  it("renders ONE breadcrumb — the contextual bar — and NOT the legacy", () => {
    renderLayout();
    expect(screen.getByTestId("breadcrumb-bar")).toBeInTheDocument();
    // the legacy menu-derived breadcrumb must be gone (no duplicate)
    expect(screen.queryByTestId("legacy-breadcrumb")).not.toBeInTheDocument();
  });

  it("the page's pushed trail renders in the single bar, href segments clickable", () => {
    renderLayout();
    const bar = screen.getByTestId("breadcrumb-bar");
    expect(within(bar).getByText("Campaigns")).toBeInTheDocument();
    expect(within(bar).getByText("ACME")).toBeInTheDocument();
    // href segment = client-side link; last (current page) = plain text.
    expect(within(bar).getByText("Campaigns").closest("a")).not.toBeNull();
    expect(within(bar).getByText("ACME").closest("a")).toBeNull();
  });
});
