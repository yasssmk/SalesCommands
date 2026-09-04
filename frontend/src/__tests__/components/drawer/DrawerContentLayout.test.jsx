// frontend/src/__tests__/components/drawer/DrawerContentLayout.test.jsx
//
// SE-b — the shared drawer content scaffold: a bold h3 title, ONE content box
// (page background ground + radius lg + hairline border) holding the field
// groups, and a global Save/Cancel action row. It is the injected node — it does
// NOT render the coque or the close cross (those are the WorkspaceDrawer's).

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import { useTheme } from "@mui/material/styles";
import ThemeCustomization from "themes/index";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";

function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
  const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
  return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
}

let probed = {};
function ThemeProbe() {
  const t = useTheme();
  probed = { bgDefault: t.palette.background.default, radiusLg: t.aphoriQ.radius.lg };
  return null;
}

function renderLayout(props = {}) {
  return render(
    <ThemeCustomization>
      <ThemeProbe />
      <DrawerContentLayout title="Edit activity" onSave={() => {}} onCancel={() => {}} {...props}>
        <div data-testid="group">groups here</div>
      </DrawerContentLayout>
    </ThemeCustomization>,
  );
}

describe("DrawerContentLayout — title + content box + global actions", () => {
  it("renders the title as a bold h3", () => {
    renderLayout();
    const title = screen.getByText("Edit activity");
    expect(title).toHaveClass("MuiTypography-h3");
  });

  it("wraps children in ONE box grounded on background.default with radius lg", () => {
    renderLayout();
    const box = screen.getByTestId("drawer-content-box");
    expect(box).toContainElement(screen.getByTestId("group"));
    const rule = rulesForElement(box);
    expect(rule).toContain(`background-color:${probed.bgDefault}`);
    expect(rule).toContain(`border-radius:${probed.radiusLg}px`);
  });

  it("renders a global Save and Cancel", () => {
    renderLayout();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });

  it("calls onSave / onCancel; saveDisabled disables Save", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    renderLayout({ onSave, onCancel, saveDisabled: false });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onCancel).toHaveBeenCalledTimes(1);

    cleanup();
    renderLayout({ onSave, saveDisabled: true });
    expect(screen.getByRole("button", { name: /save/i })).toBeDisabled();
  });

  it("honors custom saveLabel / cancelLabel", () => {
    renderLayout({ saveLabel: "Apply", cancelLabel: "Discard" });
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Discard" })).toBeInTheDocument();
  });
});
