// frontend/src/__tests__/components/workspaceDrawer.coque.test.jsx
//
// B3.5.1 — the visual coque of the single workspace drawer.
//   - large screen: PUSH — the drawer is a flex column beside the main content
//     (both visible side by side, NO overlay backdrop);
//   - narrow screen: OVERLAY — a temporary Drawer with a backdrop.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render as rtlRender, screen, fireEvent, cleanup } from "@testing-library/react";
import WorkspaceCoque from "../_utils/workspaceCoque";
import { testTheme } from "../_utils/aphoriqTheme";

// The emotion rule text for an element's own css-* classes (scoped).
function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
  const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
  return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
}

// The cascade winner background-color of an element's emotion rules — the LAST
// declaration across its css-* classes (sx overrides come last and win).
function bgOf(el) {
  const all = rulesForElement(el).match(/background-color:\s*([^;}]+)/g) || [];
  if (all.length === 0) return null;
  return all[all.length - 1].replace(/background-color:\s*/, "").trim();
}

// Walk up from `el` and return the background-color of the first ancestor that
// declares one (the coque panel Box paints the shell background).
function bgOfAncestor(el) {
  let node = el;
  while (node) {
    const bg = bgOf(node);
    if (bg) return bg;
    node = node.parentElement;
  }
  return null;
}

// The coque panel element itself: the first ancestor of `el` that paints a
// background-color (the CoquePanel Box carries bg + radius + border + margin).
function panelOfAncestor(el) {
  let node = el;
  while (node) {
    if (bgOf(node)) return node;
    node = node.parentElement;
  }
  return null;
}

// Control push vs overlay deterministically (WorkspaceDrawer picks the mode via
// useMediaQuery(down('lg'))). Since L2 the coque + provider live at the layout,
// so this mounts the standalone WorkspaceCoque harness (provider + coque).
vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
import useMediaQuery from "@mui/material/useMediaQuery";

import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";

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
  return rtlRender(
    <WorkspaceCoque>
      <Trigger />
    </WorkspaceCoque>,
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

describe("WorkspaceDrawer coque — anthracite background (S2c-2)", () => {
  it("large PUSH: the coque panel background is the aphoriQ surface.level2 token (not level1)", () => {
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "open" }));

    const bg = bgOfAncestor(screen.getByTestId("dcontent"));
    expect(bg).toBe(testTheme.aphoriQ.surface.level2);
    expect(bg).not.toBe(testTheme.aphoriQ.surface.level1);
  });

  it("narrow OVERLAY: the temporary Drawer paper background is surface.level2 (not level1)", () => {
    useMediaQuery.mockReturnValue(true); // narrow
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "open" }));

    const paper = document.querySelector(".MuiDrawer-paper");
    expect(paper).not.toBeNull();
    const bg = bgOf(paper);
    expect(bg).toBe(testTheme.aphoriQ.surface.level2);
    expect(bg).not.toBe(testTheme.aphoriQ.surface.level1);
  });
});

describe("WorkspaceDrawer coque — rounded, detached floating card (SE-a)", () => {
  it("large PUSH: the panel is rounded (radius.lg), has a detachment margin, and a full hairline border", () => {
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "open" }));

    const panel = panelOfAncestor(screen.getByTestId("dcontent"));
    expect(panel).not.toBeNull();
    const rule = rulesForElement(panel);
    // same radius as the page boxes (aphoriQ.radius.lg = 12px)
    expect(rule).toContain(`border-radius:${testTheme.aphoriQ.radius.lg}px`);
    // detached from the edges — a margin is present
    expect(rule).toMatch(/margin(-top|-right|-bottom|-left)?:/);
    // full border (not the old left-only border): a solid border shorthand/side
    expect(rule).toMatch(/border(-top|-right|-bottom)?(-style)?:\s*[^;]*solid|border-width:/);
    // background stays anthracite
    expect(bgOf(panel)).toBe(testTheme.aphoriQ.surface.level2);
  });

  it("large PUSH: the panel is NOT bordered on the left side only (border-left-only is gone)", () => {
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "open" }));

    const rule = rulesForElement(panelOfAncestor(screen.getByTestId("dcontent")));
    // the old design declared ONLY border-left-*; a full card must not be
    // left-only. If a left border is declared it must be part of an all-sides
    // border (a plain shorthand or explicit widths), so assert a non-left
    // border declaration exists.
    expect(rule).toMatch(/(^|[;{])border:|border-top|border-right|border-bottom|border-width:/);
  });

  it("narrow OVERLAY: the paper is rounded (radius.lg) and detached with a margin", () => {
    useMediaQuery.mockReturnValue(true); // narrow
    renderWorkspace();
    fireEvent.click(screen.getByRole("button", { name: "open" }));

    const paper = document.querySelector(".MuiDrawer-paper");
    const rule = rulesForElement(paper);
    expect(rule).toContain(`border-radius:${testTheme.aphoriQ.radius.lg}px`);
    expect(rule).toMatch(/margin(-top|-right|-bottom|-left)?:/);
    expect(bgOf(paper)).toBe(testTheme.aphoriQ.surface.level2);
  });
});
