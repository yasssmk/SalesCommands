// frontend/src/__tests__/components/workspaceDrawer.notesZone.test.jsx
//
// Sprint « Source / Notes » — notes panel, N3: the coque has TWO zones.
//   - TOP: the injected content (openDrawer / closeDrawer — unchanged);
//   - BOTTOM: the notes panel (openNotesPanel / closeNotesPanel), its own
//     « Notes » header and ×, its own scroll, NOTES_ZONE_HEIGHT of the coque;
//     notes alone → the bottom zone alone.
// Replacing / closing the top never touches the notes (they stay MOUNTED —
// their autosave is not flushed by a remount); a route change, the menu
// opening and the overlay's backdrop close BOTH; the 2.2 guard still only asks
// for the top's modified content.
// Real provider, real coque (WorkspaceDrawer).

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, act, waitFor } from "@testing-library/react";
import { useEffect } from "react";

vi.mock("@mui/material/useMediaQuery", () => ({ default: vi.fn(() => false) }));
import useMediaQuery from "@mui/material/useMediaQuery";
import { usePathname } from "next/navigation";

import WorkspaceCoque from "../_utils/workspaceCoque";
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { useMenuState } from "hooks/useMenuState";
import useUnsavedChanges from "hooks/useUnsavedChanges";
import { NOTES_ZONE_HEIGHT } from "components/WorkspaceDrawer";
import { testTheme } from "../_utils/aphoriqTheme";

// ==============================|| HELPERS ||============================== //

function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
  const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
  return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
}

// The notes panel's node: counts its mounts / unmounts (a remount would flush
// and restart the autosave).
const lifecycle = { mounts: 0, unmounts: 0 };
function NotesNode() {
  useEffect(() => {
    lifecycle.mounts += 1;
    return () => {
      lifecycle.unmounts += 1;
    };
  }, []);
  return <div data-testid="notes-body">the note</div>;
}

// A top content declared MODIFIED (the 2.2 guard's drawer source).
function DirtyTop() {
  useUnsavedChanges(true);
  return <div data-testid="dirty-top">half-written</div>;
}

function Trigger() {
  const { openDrawer, closeDrawer, openNotesPanel, closeNotesPanel } = useWorkspaceDrawer();
  const { menuMaster, handlerDrawerOpen } = useMenuState();
  return (
    <div>
      <span data-testid="menu-state">{menuMaster?.isDashboardDrawerOpened ? "open" : "closed"}</span>
      <button onClick={() => openDrawer(<div data-testid="top-a">content A</div>, { title: "Edit A" })}>open-a</button>
      <button onClick={() => openDrawer(<div data-testid="top-b">content B</div>, { title: "Edit B" })}>open-b</button>
      <button onClick={() => openDrawer(<DirtyTop />, { title: "Dirty" })}>open-dirty</button>
      <button onClick={() => closeDrawer()}>close-top</button>
      <button onClick={() => openNotesPanel(<NotesNode />)}>open-notes</button>
      <button onClick={() => closeNotesPanel()}>close-notes</button>
      <button onClick={() => handlerDrawerOpen(true)}>open-menu</button>
    </div>
  );
}

const renderWorkspace = () => render(<Trigger />, { wrapper: WorkspaceCoque });
const click = (name) => fireEvent.click(screen.getByText(name));
const topZone = () => screen.queryByTestId("coque-top-zone");
const notesZone = () => screen.queryByTestId("coque-notes-zone");
const dialog = () => screen.queryByTestId("confirm-dialog");

beforeEach(() => {
  try { localStorage.clear(); } catch { /* ignore */ }
  lifecycle.mounts = 0;
  lifecycle.unmounts = 0;
  useMediaQuery.mockReturnValue(false); // large: push
  usePathname.mockReturnValue("/activities/1");
});
afterEach(() => cleanup());

// ==============================|| LAYOUT ||============================== //

describe("two-zone coque — layout (push)", () => {
  it("notes alone → the bottom zone alone, « Notes » header with its own ×", () => {
    renderWorkspace();
    expect(screen.queryByTestId("coque-panel")).not.toBeInTheDocument();
    click("open-notes");
    expect(screen.getByTestId("coque-panel")).toBeInTheDocument();
    expect(notesZone()).toBeInTheDocument();
    expect(topZone()).not.toBeInTheDocument();
    expect(notesZone()).toHaveTextContent("Notes");
    expect(screen.getByRole("button", { name: "Close notes" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close drawer" })).not.toBeInTheDocument();
    expect(screen.getByTestId("notes-body")).toBeInTheDocument();
  });

  it("content + notes → the top zone ABOVE the notes zone, which takes NOTES_ZONE_HEIGHT", () => {
    renderWorkspace();
    click("open-a");
    click("open-notes");
    const panel = screen.getByTestId("coque-panel");
    const [first, second] = [...panel.children];
    expect(first).toBe(topZone());
    expect(second).toBe(notesZone());
    expect(NOTES_ZONE_HEIGHT).toBe("40%");
    expect(rulesForElement(notesZone())).toContain(`flex:0 0 ${NOTES_ZONE_HEIGHT}`);
    // The coque takes the whole bounded height, so the share resolves.
    expect(rulesForElement(panel)).toMatch(/(^|[;{])height:\s*calc\(100vh/);
    expect(rulesForElement(notesZone())).toContain(
      `border-top-color:${testTheme.aphoriQ.border.color}`,
    );
    expect(screen.getByRole("button", { name: "Close drawer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Close notes" })).toBeInTheDocument();
  });

  it("each zone scrolls on its own (flex child, min-height 0, overflow-y auto)", () => {
    renderWorkspace();
    click("open-a");
    click("open-notes");
    for (const body of [screen.getByTestId("top-a").parentElement, screen.getByTestId("notes-body").parentElement]) {
      const rule = rulesForElement(body);
      expect(rule).toMatch(/overflow-y:\s*auto/);
      expect(rule).toMatch(/min-height:\s*0/);
    }
  });

  it("without notes the coque is as before: no fixed height, no notes zone", () => {
    renderWorkspace();
    click("open-a");
    expect(notesZone()).not.toBeInTheDocument();
    expect(rulesForElement(screen.getByTestId("coque-panel"))).not.toMatch(/(^|[;{])height:/);
  });
});

// ==============================|| ZONES ARE INDEPENDENT ||============================== //

describe("two-zone coque — the top never touches the notes", () => {
  it("the top × closes the top only; the notes stay mounted", () => {
    renderWorkspace();
    click("open-a");
    click("open-notes");
    fireEvent.click(screen.getByRole("button", { name: "Close drawer" }));
    expect(topZone()).not.toBeInTheDocument();
    expect(screen.getByTestId("notes-body")).toBeInTheDocument();
    expect(lifecycle).toEqual({ mounts: 1, unmounts: 0 });
  });

  it("replacing the top keeps the notes mounted", () => {
    renderWorkspace();
    click("open-notes");
    click("open-a");
    click("open-b");
    expect(screen.getByTestId("top-b")).toBeInTheDocument();
    expect(screen.queryByTestId("top-a")).not.toBeInTheDocument();
    expect(lifecycle).toEqual({ mounts: 1, unmounts: 0 });
  });

  it("the notes × closes the notes only; the top stays", () => {
    renderWorkspace();
    click("open-a");
    click("open-notes");
    fireEvent.click(screen.getByRole("button", { name: "Close notes" }));
    expect(notesZone()).not.toBeInTheDocument();
    expect(screen.getByTestId("top-a")).toBeInTheDocument();
    expect(lifecycle.unmounts).toBe(1);
  });

  it("closing both zones closes the coque", async () => {
    renderWorkspace();
    click("open-a");
    click("open-notes");
    click("close-top");
    expect(screen.getByTestId("coque-panel")).toBeInTheDocument();
    click("close-notes");
    // The horizontal Collapse unmounts the panel at the end of its exit.
    await waitFor(() => expect(screen.queryByTestId("coque-panel")).not.toBeInTheDocument());
  });

  it("opening the notes collapses the left menu (exclusivity)", () => {
    renderWorkspace();
    click("open-menu");
    expect(screen.getByTestId("menu-state")).toHaveTextContent("open");
    click("open-notes");
    expect(screen.getByTestId("menu-state")).toHaveTextContent("closed");
  });
});

// ==============================|| ROUTE / MENU CLOSE ALL ||============================== //

describe("two-zone coque — a route change or the menu closes BOTH", () => {
  it("a route change closes both zones (the notes unmount → their flush)", () => {
    const view = renderWorkspace();
    click("open-a");
    click("open-notes");
    usePathname.mockReturnValue("/accounts/2");
    view.rerender(<Trigger />);
    expect(topZone()).not.toBeInTheDocument();
    expect(notesZone()).not.toBeInTheDocument();
    expect(lifecycle.unmounts).toBe(1);
  });

  it("the menu opening closes both zones — notes alone included", () => {
    renderWorkspace();
    click("open-notes");
    click("open-menu");
    expect(notesZone()).not.toBeInTheDocument();
    click("open-a");
    click("open-notes");
    click("open-menu");
    expect(topZone()).not.toBeInTheDocument();
    expect(notesZone()).not.toBeInTheDocument();
  });
});

// ==============================|| 2.2 GUARD UNCHANGED ||============================== //

describe("two-zone coque — the 2.2 guard only asks for the top", () => {
  it("opening / closing the notes over a MODIFIED top never asks", () => {
    renderWorkspace();
    click("open-dirty");
    click("open-notes");
    expect(dialog()).toBeNull();
    click("close-notes");
    expect(dialog()).toBeNull();
    expect(screen.getByTestId("dirty-top")).toBeInTheDocument();
  });

  it("closing a MODIFIED top still asks; « Discard » closes the top only", () => {
    renderWorkspace();
    click("open-dirty");
    click("open-notes");
    fireEvent.click(screen.getByRole("button", { name: "Close drawer" }));
    expect(dialog()).not.toBeNull();
    fireEvent.click(screen.getByTestId("confirm-discard-changes"));
    expect(screen.queryByTestId("dirty-top")).not.toBeInTheDocument();
    expect(screen.getByTestId("notes-body")).toBeInTheDocument();
    expect(lifecycle.unmounts).toBe(0);
  });

  it("the menu over a MODIFIED top asks: « Keep editing » keeps BOTH, « Discard » closes BOTH", () => {
    renderWorkspace();
    click("open-dirty");
    click("open-notes");
    click("open-menu");
    expect(dialog()).not.toBeNull();
    fireEvent.click(screen.getByText("Keep editing"));
    expect(screen.getByTestId("dirty-top")).toBeInTheDocument();
    expect(screen.getByTestId("notes-body")).toBeInTheDocument();
    expect(screen.getByTestId("menu-state")).toHaveTextContent("closed");
    click("open-menu");
    fireEvent.click(screen.getByTestId("confirm-discard-changes"));
    expect(topZone()).not.toBeInTheDocument();
    expect(notesZone()).not.toBeInTheDocument();
  });
});

// ==============================|| OVERLAY (< lg) ||============================== //

describe("two-zone coque — overlay (narrow)", () => {
  beforeEach(() => useMediaQuery.mockReturnValue(true));

  it("notes alone → an overlay with the bottom zone alone", () => {
    renderWorkspace();
    click("open-notes");
    expect(document.querySelector(".MuiBackdrop-root")).not.toBeNull();
    expect(notesZone()).toBeInTheDocument();
    expect(topZone()).not.toBeInTheDocument();
  });

  it("content + notes → the same two zones in the paper, top above notes", () => {
    renderWorkspace();
    click("open-a");
    click("open-notes");
    const paper = document.querySelector(".MuiDrawer-paper");
    expect([...paper.children]).toEqual([topZone(), notesZone()]);
    // MUI's Drawer paper is a flex column: the zones' shares apply.
    expect(rulesForElement(paper)).toMatch(/flex-direction:\s*column/);
    expect(rulesForElement(notesZone())).toContain(`flex:0 0 ${NOTES_ZONE_HEIGHT}`);
  });

  it("the backdrop closes BOTH zones", async () => {
    renderWorkspace();
    click("open-a");
    click("open-notes");
    await act(async () => {
      fireEvent.click(document.querySelector(".MuiBackdrop-root"));
    });
    expect(screen.queryByTestId("top-a")).not.toBeInTheDocument();
    expect(lifecycle.unmounts).toBe(1);
  });

  it("the backdrop over a MODIFIED top asks first (2.2)", async () => {
    renderWorkspace();
    click("open-dirty");
    click("open-notes");
    await act(async () => {
      fireEvent.click(document.querySelector(".MuiBackdrop-root"));
    });
    expect(dialog()).not.toBeNull();
    expect(screen.getByTestId("notes-body")).toBeInTheDocument();
  });
});
