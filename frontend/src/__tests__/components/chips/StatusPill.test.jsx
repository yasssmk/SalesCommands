// frontend/src/__tests__/components/chips/StatusPill.test.jsx
//
// CHIP-1 — StatusPill is a GENERIC 3-part chip: CONTOUR (border) · FOND
// (background) · TEXTE. It takes two colours — colorText (text AND border) and
// colorBg (background) — and knows nothing about statuses. Pill shape, tokens
// only. Rendered under the real ThemeCustomization.

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
import StatusPill from "components/chips/StatusPill";

function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
  const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
  return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
}

function renderPill(props) {
  return render(
    <ThemeCustomization>
      <StatusPill {...props} />
    </ThemeCustomization>,
  );
}

describe("StatusPill — generic 3-part chip", () => {
  it("applies colorText to TEXT and BORDER, colorBg to BACKGROUND, with a pill radius", () => {
    // raw rgb values so the assertion is theme-independent and exact
    renderPill({ label: "Planned", colorText: "rgb(10, 20, 30)", colorBg: "rgb(40, 50, 60)" });
    const pill = screen.getByTestId("status-pill");
    const rule = rulesForElement(pill);

    // pill shape
    expect(rule).toMatch(/border-radius:\s*999px/);
    // a solid border exists
    expect(rule).toMatch(/border-style:\s*solid/);
    // background = colorBg
    expect(rule).toContain("rgb(40, 50, 60)");
    // colorText applied to BOTH text colour and border colour (>= 2 occurrences)
    const n = (rule.match(/rgb\(10, 20, 30\)/g) || []).length;
    expect(n).toBeGreaterThanOrEqual(2);
  });

  it("knows no status — renders whatever label and colours it is given", () => {
    renderPill({ label: "Anything", colorText: "success.main", colorBg: "grey.900" });
    expect(screen.getByText("Anything")).toBeInTheDocument();
  });

  it("passes through extra props (e.g. data-*) onto the pill element", () => {
    renderPill({ label: "X", colorText: "error.main", colorBg: "grey.900", "data-status-color": "error" });
    expect(screen.getByTestId("status-pill").getAttribute("data-status-color")).toBe("error");
  });
});
