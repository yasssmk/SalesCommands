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

  it("omits the title when none is passed (the coque renders it — Option A)", () => {
    render(
      <ThemeCustomization>
        <DrawerContentLayout onSave={() => {}} onCancel={() => {}}>
          <div data-testid="group">g</div>
        </DrawerContentLayout>
      </ThemeCustomization>,
    );
    expect(screen.queryByTestId("drawer-title")).not.toBeInTheDocument();
    // box + actions still render
    expect(screen.getByTestId("drawer-content-box")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();
  });

  it("honors custom saveLabel / cancelLabel", () => {
    renderLayout({ saveLabel: "Apply", cancelLabel: "Discard" });
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Discard" })).toBeInTheDocument();
  });

  // CT-1 — the action bar is OPTIONAL: a read-only content (e.g. the future
  // Contact fiche, whose actions live in the body) passes no onSave/onCancel and
  // gets the content alone, no global Save/Cancel row.
  it("omits the action bar entirely when neither onSave nor onCancel is passed", () => {
    render(
      <ThemeCustomization>
        <DrawerContentLayout title="Contact">
          <div data-testid="group">g</div>
        </DrawerContentLayout>
      </ThemeCustomization>,
    );
    // content still renders…
    expect(screen.getByTestId("drawer-content-box")).toBeInTheDocument();
    expect(screen.getByTestId("group")).toBeInTheDocument();
    // …but NO global action bar / buttons.
    expect(screen.queryByTestId("drawer-actions")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /save/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel/i })).not.toBeInTheDocument();
  });

  // UI-2 — the SAME layout renders the "read signal" action bar when given
  // readActions: Edit (NEUTRE) · Reject (error outline) · Validate (success
  // contained), gated by status, with Reopen for a terminal (validated OR
  // rejected) signal.
  const readActions = (over = {}) => ({
    onEdit: vi.fn(),
    onReject: vi.fn(),
    onValidate: vi.fn(),
    onReopen: vi.fn(),
    status: "PENDING",
    isLocked: false,
    validateDisabled: false,
    ...over,
  });

  function renderRead(over = {}) {
    return render(
      <ThemeCustomization>
        <DrawerContentLayout readActions={readActions(over)} />
      </ThemeCustomization>,
    );
  }

  it("read mode: a PENDING signal shows Edit (neutral) · Reject (error) · Validate (success)", () => {
    renderRead({ status: "PENDING" });
    const edit = screen.getByRole("button", { name: /edit/i });
    const reject = screen.getByRole("button", { name: /reject/i });
    const validate = screen.getByRole("button", { name: /validate/i });
    // Edit is NEUTRAL — not success (the bug), not primary.
    expect(edit).toHaveClass("MuiButton-outlinedInherit");
    expect(edit).not.toHaveClass("MuiButton-outlinedSuccess");
    expect(edit).not.toHaveClass("MuiButton-outlinedPrimary");
    // Reject error outline, Validate success contained.
    expect(reject).toHaveClass("MuiButton-outlinedError");
    expect(validate).toHaveClass("MuiButton-containedSuccess");
  });

  it("read mode: a REJECTED signal shows Reopen (not Reject/Validate)", () => {
    renderRead({ status: "REJECTED" });
    expect(screen.getByRole("button", { name: /reopen/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^validate$/i })).not.toBeInTheDocument();
  });

  it("P3: read mode: a VALIDATED signal shows Edit + Reopen (terminal status), no Reject/Validate", () => {
    renderRead({ status: "VALIDATED" });
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
    // A decision can always be undone: Reopen is offered on validated too, not just rejected.
    expect(screen.getByRole("button", { name: /reopen/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^validate$/i })).not.toBeInTheDocument();
  });

  it("read mode: isLocked hides all read actions; validateDisabled disables Validate", () => {
    const { unmount } = renderRead({ status: "PENDING", isLocked: true });
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    unmount();
    renderRead({ status: "PENDING", validateDisabled: true });
    expect(screen.getByRole("button", { name: /validate/i })).toBeDisabled();
  });

  it("read mode: the read actions fire their handlers", () => {
    const acts = readActions({ status: "PENDING" });
    render(
      <ThemeCustomization>
        <DrawerContentLayout readActions={acts} />
      </ThemeCustomization>,
    );
    fireEvent.click(screen.getByRole("button", { name: /edit/i }));
    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    fireEvent.click(screen.getByRole("button", { name: /validate/i }));
    expect(acts.onEdit).toHaveBeenCalledTimes(1);
    expect(acts.onReject).toHaveBeenCalledTimes(1);
    expect(acts.onValidate).toHaveBeenCalledTimes(1);
  });

  it("renders the action bar as soon as onSave (or onCancel) is provided", () => {
    // onSave only
    render(
      <ThemeCustomization>
        <DrawerContentLayout onSave={() => {}}>
          <div data-testid="group">g</div>
        </DrawerContentLayout>
      </ThemeCustomization>,
    );
    expect(screen.getByTestId("drawer-actions")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /save/i })).toBeInTheDocument();

    cleanup();

    // onCancel only
    render(
      <ThemeCustomization>
        <DrawerContentLayout onCancel={() => {}}>
          <div data-testid="group">g</div>
        </DrawerContentLayout>
      </ThemeCustomization>,
    );
    expect(screen.getByTestId("drawer-actions")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeInTheDocument();
  });
});
