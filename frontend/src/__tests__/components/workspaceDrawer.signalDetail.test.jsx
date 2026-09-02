// frontend/src/__tests__/components/workspaceDrawer.signalDetail.test.jsx
//
// B3.5.3 — the FIRST real content wired into the single workspace drawer coque:
// the signal DETAIL (SignalDetailPanel, dé-coqué). This exercises the frozen
// interaction contract at the coque level:
//   - clicking a signal → openDrawer(<SignalDetailPanel signal=… />) shows the
//     detail INSIDE the coque (push on large — no overlay backdrop);
//   - clicking ANOTHER signal → REPLACES the content, the coque stays open
//     (one coque, not two), the previous signal's detail is gone;
//   - the coque SLIDES open on large via a theme.transitions-driven wrapper
//     (MUI Collapse) — not a sharp mount/unmount.
//
// next/navigation is globally mocked in vitest.setup.js; next/font is mocked
// here because WorkspaceLayout pulls MainCard → Highlighter at import time.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup } from "@testing-library/react";
import AphoriqTheme from "../_utils/aphoriqTheme";

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

// Deterministic push (large) vs overlay (narrow).
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
import useMediaQuery from "@mui/material/useMediaQuery";

import WorkspaceLayout from "components/WorkspaceLayout";
import SignalDetailPanel from "components/signals/SignalDetailPanel";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";

const render = (ui, opts) => rtlRender(ui, { wrapper: AphoriqTheme, ...opts });

const SIGNAL_A = {
  id: "sig-a",
  status: "PENDING",
  summary: "Signal ALPHA summary",
  source_context: { contacts: [] },
};
const SIGNAL_B = {
  id: "sig-b",
  status: "PENDING",
  summary: "Signal BETA summary",
  source_context: { contacts: [] },
};

// A child (inside the provider) that opens the detail for A or B, exactly as the
// real callers do (openDrawer of a SignalDetailPanel node).
function Trigger() {
  const { openDrawer } = useWorkspaceDrawer();
  return (
    <div>
      <div data-testid="main-content" />
      <button onClick={() => openDrawer(<SignalDetailPanel signal={SIGNAL_A} signalType="pain" />)}>
        open-A
      </button>
      <button onClick={() => openDrawer(<SignalDetailPanel signal={SIGNAL_B} signalType="pain" />)}>
        open-B
      </button>
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

describe("WorkspaceDrawer — signal detail content (B3.5.3)", () => {
  it("large: clicking a signal shows its detail INSIDE the coque (push, no backdrop)", () => {
    renderWorkspace();
    expect(screen.queryByText("Signal ALPHA summary")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "open-A" }));

    // detail visible alongside the main content (push, not overlay)
    expect(screen.getByTestId("main-content")).toBeInTheDocument();
    expect(screen.getByText("Signal ALPHA summary")).toBeInTheDocument();
    expect(document.querySelector(".MuiBackdrop-root")).toBeNull();
  });

  it("clicking ANOTHER signal REPLACES the content (coque stays open, one coque)", () => {
    renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "open-A" }));
    expect(screen.getByText("Signal ALPHA summary")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "open-B" }));

    // B replaced A — previous detail gone, new detail shown, still no backdrop
    expect(screen.queryByText("Signal ALPHA summary")).not.toBeInTheDocument();
    expect(screen.getByText("Signal BETA summary")).toBeInTheDocument();
    expect(document.querySelector(".MuiBackdrop-root")).toBeNull();
  });

  it("large: the coque slides via a theme-driven transition wrapper (MUI Collapse)", () => {
    renderWorkspace();
    // closed → no transition wrapper mounted
    expect(document.querySelector(".MuiCollapse-root")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "open-A" }));

    // open → the push coque is wrapped in a Collapse (width transition, not a
    // sharp mount). Collapse uses theme.transitions internally (no hardcode).
    expect(document.querySelector(".MuiCollapse-root")).not.toBeNull();
  });

  it("narrow: the detail renders as an overlay (temporary Drawer backdrop)", () => {
    useMediaQuery.mockReturnValue(true); // narrow
    renderWorkspace();

    fireEvent.click(screen.getByRole("button", { name: "open-A" }));

    expect(screen.getByText("Signal ALPHA summary")).toBeInTheDocument();
    expect(document.querySelector(".MuiBackdrop-root")).not.toBeNull();
  });
});
