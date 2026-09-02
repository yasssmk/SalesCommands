// frontend/src/__tests__/contexts/workspaceDrawer.exclusive.test.jsx
//
// B3.5.2 — reverse exclusivity: opening the global left menu closes the
// workspace drawer. The hamburger lives in the shell (outside the provider),
// so the provider OBSERVES the menu singleton (useMenuState) and closes the
// drawer when isDashboardDrawerOpened transitions false → true.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act } from "@testing-library/react";

// A tiny external store that mimics the real SWR singleton behind useMenuState:
// setting it notifies subscribers, so components re-render (as SWR would).
const menu = vi.hoisted(() => {
  let open = false;
  const subs = new Set();
  return {
    get: () => open,
    set: (v) => {
      open = v;
      subs.forEach((f) => f());
    },
    subscribe: (f) => {
      subs.add(f);
      return () => subs.delete(f);
    },
    reset: () => {
      open = false;
    },
  };
});
const handlerDrawerOpen = vi.hoisted(() => vi.fn());

vi.mock("hooks/useMenuState", () => {
  const React = require("react");
  return {
    useMenuState: () => {
      const open = React.useSyncExternalStore(menu.subscribe, menu.get, menu.get);
      return {
        menuMaster: { isDashboardDrawerOpened: open },
        handlerDrawerOpen: (v) => {
          handlerDrawerOpen(v);
          menu.set(v);
        },
      };
    },
  };
});

import {
  WorkspaceDrawerProvider,
  useWorkspaceDrawer,
} from "contexts/WorkspaceDrawerContext";

function Consumer() {
  const { isOpen, content, openDrawer } = useWorkspaceDrawer();
  return (
    <div>
      <span data-testid="is-open">{String(isOpen)}</span>
      <button onClick={() => openDrawer(<div data-testid="dcontent" />)}>
        open-drawer
      </button>
      {/* stand-in for the coque, which renders the injected content */}
      <div data-testid="slot">{content}</div>
    </div>
  );
}

const ui = (
  <WorkspaceDrawerProvider>
    <Consumer />
  </WorkspaceDrawerProvider>
);

beforeEach(() => {
  menu.reset();
  vi.clearAllMocks();
});
afterEach(() => cleanup());

describe("WorkspaceDrawer reverse exclusivity (B3.5.2)", () => {
  it("opening the menu (false→true) closes an open drawer", () => {
    render(ui);

    fireEvent.click(screen.getByRole("button", { name: "open-drawer" }));
    expect(screen.getByTestId("is-open").textContent).toBe("true");
    expect(screen.getByTestId("dcontent")).toBeInTheDocument();

    // the hamburger opens the menu → subscribers re-render (like SWR)
    act(() => menu.set(true));

    expect(screen.getByTestId("is-open").textContent).toBe("false");
    expect(screen.queryByTestId("dcontent")).not.toBeInTheDocument();
  });

  it("opening the drawer does not loop (menu collapses, drawer stays open)", () => {
    render(ui);

    fireEvent.click(screen.getByRole("button", { name: "open-drawer" }));

    // openDrawer collapsed the menu (handlerDrawerOpen(false)) — the observer
    // must NOT treat that as a menu-open and close itself.
    expect(handlerDrawerOpen).toHaveBeenCalledWith(false);
    expect(screen.getByTestId("is-open").textContent).toBe("true");
    expect(screen.getByTestId("dcontent")).toBeInTheDocument();
  });
});
