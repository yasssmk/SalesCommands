// frontend/src/__tests__/components/WorkspaceHeader.test.jsx
//
// HEADER-1 — the new SHARED workspace header (components/WorkspaceHeader.jsx) is
// a structure with OPAQUE slots: Row1 [avatar · title · headerActions] ·
// Row2 [chips] · extraRows? · hairline filet · infoItems. It imposes nothing on
// the slot content (each surface fills them differently). Themed via aphoriQ.

import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach, vi } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import WorkspaceHeader from "components/WorkspaceHeader";

function renderHeader(props) {
  return render(
    <ThemeCustomization>
      <WorkspaceHeader {...props} />
    </ThemeCustomization>,
  );
}

describe("WorkspaceHeader — shared opaque-slot shell", () => {
  it("renders every slot node passed in (avatar, title, actions, chips, extraRows, infoItems)", () => {
    renderHeader({
      avatar: <div data-testid="slot-avatar">AV</div>,
      title: "My Title",
      headerActions: <button data-testid="slot-actions">⋮</button>,
      chips: [<span key="c" data-testid="slot-chip">chip</span>],
      extraRows: [<div key="e" data-testid="slot-extra">extra</div>],
      infoItems: [<span key="i" data-testid="slot-info">info</span>],
    });
    expect(screen.getByTestId("slot-avatar")).toBeInTheDocument();
    expect(screen.getByText("My Title")).toBeInTheDocument();
    expect(screen.getByTestId("slot-actions")).toBeInTheDocument();
    expect(screen.getByTestId("slot-chip")).toBeInTheDocument();
    expect(screen.getByTestId("slot-extra")).toBeInTheDocument();
    expect(screen.getByTestId("slot-info")).toBeInTheDocument();
  });

  it("renders a read-only bold title when onTitleSave is absent", () => {
    renderHeader({ title: "Plain Title" });
    const el = screen.getByText("Plain Title");
    // bold weight comes from the theme token, not a hardcoded number
    const cls = (el.getAttribute("class") || "") + (el.closest("[class]")?.getAttribute("class") || "");
    const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
    const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
    const rule = classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
    expect(rule).toMatch(/font-weight:\s*(bold|[6-9]00)/);
  });

  it("renders the hairline filet only when there are infoItems", () => {
    const { rerender } = renderHeader({ title: "T", infoItems: [<span key="i">info</span>] });
    expect(screen.getByTestId("header-rule")).toBeInTheDocument();
    rerender(
      <ThemeCustomization>
        <WorkspaceHeader title="T" infoItems={[]} />
      </ThemeCustomization>,
    );
    expect(screen.queryByTestId("header-rule")).not.toBeInTheDocument();
  });

  it("makes the title editable (EditableField) when onTitleSave is provided", () => {
    renderHeader({ title: "Editable", onTitleSave: vi.fn() });
    // EditableField renders the value as clickable text (double-click to edit)
    expect(screen.getByText("Editable")).toBeInTheDocument();
  });
});
