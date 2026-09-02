// frontend/src/__tests__/components/workspaceDrawer.coque.test.jsx
//
// B3.5.1 — the visual coque of the single workspace drawer.
//   - large screen: PUSH — the drawer is a flex column beside the main content
//     (both visible side by side, NO overlay backdrop);
//   - narrow screen: OVERLAY — a temporary Drawer with a backdrop.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup } from "@testing-library/react";
import AphoriqTheme from "../_utils/aphoriqTheme";

// config (theme-config.js) calls next/font/google at import time — not loadable
// under vitest; it is pulled transitively via MainCard → Highlighter.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

// Control push vs overlay deterministically (WorkspaceDrawer picks the mode via
// useMediaQuery(down('lg'))).
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
import useMediaQuery from "@mui/material/useMediaQuery";

import WorkspaceLayout from "components/WorkspaceLayout";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";

const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

// A child (inside the provider) that drives the drawer.
function Trigger() {
  const { openDrawer, closeDrawer } = useWorkspaceDrawer();
  return (
    <div>
      <div data-testid="main-content" />
      <button onClick={() => openDrawer(<div data-testid="dcontent">drawer body</div>)}>
        open
      </button>
      <button onClick={closeDrawer}>close</button>
    </div>
  );
}

function renderWorkspace() {
  return render(
    <WorkspaceLayout title="WS">
      <Trigger />
    </WorkspaceLayout>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useMediaQuery.mockReturnValue(false); // large by default
});
afterEach(() => cleanup());

describe("WorkspaceDrawer coque (B3.5.1)", () => {
  it("large: PUSH — drawer content and main content are visible side by side, no backdrop", () => {
    renderWorkspace();

    // closed initially
    expect(screen.queryByTestId("dcontent")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "open" }));

    // both present at once (push, not overlay)
    expect(screen.getByTestId("main-content")).toBeInTheDocument();
    expect(screen.getByTestId("dcontent")).toBeInTheDocument();
    // no overlay backdrop in push mode
    expect(document.querySelector(".MuiBackdrop-root")).toBeNull();
    expect(document.querySelector('[role="presentation"]')).toBeNull();
  });

  it("large: closing returns the main content to full width (coque gone)", () => {
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "open" }));
    expect(screen.getByTestId("dcontent")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "close" }));
    expect(screen.queryByTestId("dcontent")).not.toBeInTheDocument();
    expect(screen.getByTestId("main-content")).toBeInTheDocument();
  });

  it("narrow: OVERLAY — the drawer renders with a backdrop", () => {
    useMediaQuery.mockReturnValue(true); // narrow
    renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "open" }));

    expect(screen.getByTestId("dcontent")).toBeInTheDocument();
    // temporary MUI Drawer paints a backdrop overlay
    expect(document.querySelector(".MuiBackdrop-root")).not.toBeNull();
  });
});
