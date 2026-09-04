// frontend/src/__tests__/contexts/workspaceDrawer.navclose.test.jsx
//
// CT-2b(-fix) point 7 — the workspace drawer must CLOSE on route change. The fix
// lives in the shared provider (transverse to every drawer): it observes the
// Next pathname and clears the content when the pathname changes.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

const handlerDrawerOpen = vi.fn();
vi.mock("hooks/useMenuState", () => ({
  useMenuState: () => ({ handlerDrawerOpen }),
}));

// Controllable pathname — mutate between renders to simulate navigation.
let currentPath = "/accounts/a1";
vi.mock("next/navigation", () => ({
  usePathname: () => currentPath,
}));

import {
  WorkspaceDrawerProvider,
  useWorkspaceDrawer,
} from "contexts/WorkspaceDrawerContext";

function Consumer() {
  const { isOpen, openDrawer } = useWorkspaceDrawer();
  return (
    <div>
      <span data-testid="is-open">{String(isOpen)}</span>
      <button onClick={() => openDrawer(<span data-testid="injected" />)}>open</button>
    </div>
  );
}

function renderProvider() {
  return render(
    <WorkspaceDrawerProvider>
      <Consumer />
    </WorkspaceDrawerProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  currentPath = "/accounts/a1";
});
afterEach(() => cleanup());

describe("WorkspaceDrawerProvider — close on navigation (point 7)", () => {
  it("closes the drawer when the pathname changes", () => {
    const { rerender } = renderProvider();

    fireEvent.click(screen.getByRole("button", { name: "open" }));
    expect(screen.getByTestId("is-open").textContent).toBe("true");

    // Navigate: the pathname changes, then the tree re-renders.
    currentPath = "/campaigns";
    rerender(
      <WorkspaceDrawerProvider>
        <Consumer />
      </WorkspaceDrawerProvider>,
    );

    expect(screen.getByTestId("is-open").textContent).toBe("false");
    expect(screen.queryByTestId("injected")).not.toBeInTheDocument();
  });

  it("does NOT close on re-render when the pathname is unchanged", () => {
    const { rerender } = renderProvider();

    fireEvent.click(screen.getByRole("button", { name: "open" }));
    expect(screen.getByTestId("is-open").textContent).toBe("true");

    // Same path → drawer stays open.
    rerender(
      <WorkspaceDrawerProvider>
        <Consumer />
      </WorkspaceDrawerProvider>,
    );

    expect(screen.getByTestId("is-open").textContent).toBe("true");
  });
});
