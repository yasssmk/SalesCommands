// frontend/src/__tests__/contexts/workspaceDrawer.test.jsx
//
// B3.5.0 — state-only provider for the single workspace drawer coque.
// Proves: openDrawer(node) → isOpen + content, and collapses the left menu
// (handlerDrawerOpen(false)); closeDrawer() → closed + content cleared.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

// Spy the existing menu state (exclusivity is wired through it).
const handlerDrawerOpen = vi.fn();
vi.mock("hooks/useMenuState", () => ({
  useMenuState: () => ({ handlerDrawerOpen }),
}));

import {
  WorkspaceDrawerProvider,
  useWorkspaceDrawer,
} from "contexts/WorkspaceDrawerContext";

function Consumer() {
  const { isOpen, content, openDrawer, closeDrawer } = useWorkspaceDrawer();
  return (
    <div>
      <span data-testid="is-open">{String(isOpen)}</span>
      <span data-testid="has-content">{String(content != null)}</span>
      <button onClick={() => openDrawer(<span data-testid="injected" />)}>
        open
      </button>
      <button onClick={closeDrawer}>close</button>
      <div data-testid="slot">{content}</div>
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

beforeEach(() => vi.clearAllMocks());
afterEach(() => cleanup());

describe("WorkspaceDrawerProvider / useWorkspaceDrawer (B3.5.0)", () => {
  it("starts closed with no content", () => {
    renderProvider();
    expect(screen.getByTestId("is-open").textContent).toBe("false");
    expect(screen.getByTestId("has-content").textContent).toBe("false");
  });

  it("openDrawer(node) opens, stores the node, and collapses the left menu", () => {
    renderProvider();
    fireEvent.click(screen.getByRole("button", { name: "open" }));

    expect(screen.getByTestId("is-open").textContent).toBe("true");
    expect(screen.getByTestId("has-content").textContent).toBe("true");
    expect(screen.getByTestId("injected")).toBeInTheDocument();
    // exclusivity: opening the drawer collapses the menu
    expect(handlerDrawerOpen).toHaveBeenCalledWith(false);
  });

  it("closeDrawer() closes and clears the content", () => {
    renderProvider();
    fireEvent.click(screen.getByRole("button", { name: "open" }));
    fireEvent.click(screen.getByRole("button", { name: "close" }));

    expect(screen.getByTestId("is-open").textContent).toBe("false");
    expect(screen.getByTestId("has-content").textContent).toBe("false");
    expect(screen.queryByTestId("injected")).not.toBeInTheDocument();
  });
});
