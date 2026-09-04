// frontend/src/__tests__/sections/activities/workspace/ActivityHeader.headerV2.test.jsx
//
// HEADER-1 — the Activity surface, rendered at the mockup design:
//   - avatar = a square rounded TILE carrying the activity-type icon
//   - a single DISCREET status chip (Planned neutral · Completed success ·
//     Cancelled error), the only filled chip
//   - a ⋮ menu offering status changes (Complete/Cancel/Reopen/Delete) + Edit
//   - the date/Overdue flag READ from the backend boolean activity.is_overdue
//     (never recomputed client-side), and the date shown without a −1-day shift.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, renderHook, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));
vi.mock("sections/campaigns/CampaignOutcomeModal", () => ({ default: () => null }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

// Spy the coque so we can assert the ⋮ Edit item opens the edit content.
const openDrawer = vi.fn();
vi.mock("contexts/WorkspaceDrawerContext", () => ({
  useWorkspaceDrawer: () => ({ isOpen: false, content: null, openDrawer, closeDrawer: vi.fn() }),
}));
vi.mock("sections/activities/workspace/EditActivityContent", () => ({
  default: () => <div data-testid="edit-activity-content" />,
}));
vi.mock("sections/activities/workspace/OutcomeDrawerContent", () => ({
  default: () => <div data-testid="outcome-drawer-content" />,
}));

import ThemeCustomization from "themes/index";
import StatusPill from "components/chips/StatusPill";
import useActivityHeaderProps from "sections/activities/workspace/ActivityHeader";
import {
  ACTIVITY_STATUS_COLORS,
  ACTIVITY_STATUS_CHIP_COLORS,
} from "api/accounts/activities";

// Pull the three colour properties out of the pill's emotion rule (theme-
// independent — we compare them to each other, not to a re-built palette).
function pillColors(rule) {
  const pick = (re) => (rule.match(re) || [])[1]?.trim();
  return {
    text: pick(/[;{]color:\s*([^;}]+)/),
    border: pick(/border-color:\s*([^;}]+)/),
    background: pick(/background-color:\s*([^;}]+)/),
  };
}

const wrapper = ({ children }) => <ThemeCustomization>{children}</ThemeCustomization>;

// The emotion rule text for an element's own css-* classes (scoped, avoids
// cross-test <style> contamination).
function rulesForElement(el) {
  const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent || "").join("");
  const classes = (el.getAttribute("class") || "").split(/\s+/).filter((c) => c.startsWith("css-"));
  return classes.map((c) => (css.match(new RegExp(`\\.${c}\\s*\\{[^}]*\\}`, "g")) || []).join("")).join("");
}

const base = {
  id: "act-1",
  activity_type: "CALL",
  status: "PLANNED",
  title: "Discovery call",
  account_detail: { id: "acc-1", company_name: "ACME" },
};

function useHeader(activity, extra = {}) {
  return renderHook(() => useActivityHeaderProps({ activity, ...extra }), { wrapper });
}

describe("ActivityHeader V2 — avatar tile sized from theme.iconSizes", () => {
  it("avatar is a rounded tile with the type icon, dimensioned from iconSizes (not 56px)", () => {
    const { result } = useHeader(base);
    const { container } = render(<div>{result.current.avatar}</div>, { wrapper });
    // type icon present, rounded (not circular)
    expect(container.querySelector(".anticon-phone")).toBeTruthy();
    expect(container.querySelector(".MuiAvatar-rounded")).toBeTruthy();
    // reduced: the old hardcoded 56px tile is gone
    const avatar = container.querySelector(".MuiAvatar-root");
    const rule = rulesForElement(avatar);
    expect(rule).not.toMatch(/56px/);
    // sized from the theme's iconSizes scale (px integers <= xxl-derived tile)
    expect(rule).toMatch(/width:\s*\d+px/);
  });
});

describe("ActivityHeader V2 — status is a PILL in titleAdornment (Row 1)", () => {
  it("the status is NOT in the chips slot (Row 2 is empty)", () => {
    const { result } = useHeader({ ...base, campaign_detail: { id: "cmp1", name: "Q2" }, outcome: "SUCCESSFUL" });
    const { container } = render(<div>{result.current.chips}</div>, { wrapper });
    expect(container.querySelectorAll(".MuiChip-root").length).toBe(0);
  });

  it("the {text, background} table lives in the constants file; bg = the page background token", () => {
    // 2 colours per status: text (=border) + background. The background reuses
    // the theme's page/header background token (background.paper — inverts
    // light/dark), shared by every status; no frozen colour.
    expect(ACTIVITY_STATUS_CHIP_COLORS.PLANNED.text).toBe("text.secondary");
    expect(ACTIVITY_STATUS_CHIP_COLORS.COMPLETED.text).toBe("success.main");
    expect(ACTIVITY_STATUS_CHIP_COLORS.CANCELLED.text).toBe("error.main");
    expect(ACTIVITY_STATUS_CHIP_COLORS.ON_HOLD.text).toBe("warning.main");
    expect(ACTIVITY_STATUS_CHIP_COLORS.PLANNED.background).toBe("background.paper");
    const bg = ACTIVITY_STATUS_CHIP_COLORS.PLANNED.background;
    expect(ACTIVITY_STATUS_CHIP_COLORS.COMPLETED.background).toBe(bg);
    expect(ACTIVITY_STATUS_CHIP_COLORS.CANCELLED.background).toBe(bg);
    expect(ACTIVITY_STATUS_CHIP_COLORS.ON_HOLD.background).toBe(bg);
    // never the removed frozen colour
    expect(bg).not.toBe("common.black");
  });

  it("titleAdornment is a PILL rendered via StatusPill: visible CONTOUR (=text) + dark FOND", () => {
    const { result } = useHeader({ ...base, status: "PLANNED" });
    const { container } = render(<div>{result.current.titleAdornment}</div>, { wrapper });
    const pill = container.querySelector('[data-testid="status-pill"]');
    expect(pill).toBeTruthy();
    expect(pill.textContent).toMatch(/Planned/);
    expect(container.querySelector(".MuiChip-root")).toBeFalsy();
    const rule = rulesForElement(pill);
    // pill shape
    expect(rule).toMatch(/border-radius:\s*999px/);
    // 3 parts: a solid border is now present (was missing before)
    expect(rule).toMatch(/border-style:\s*solid/);
    expect(rule).toMatch(/border-color:/);
    // colour role still sourced from ACTIVITY_STATUS_COLORS
    expect(pill.getAttribute("data-status-color")).toBe(ACTIVITY_STATUS_COLORS.PLANNED);
  });

  it("text = border (both colorText); background = the page bg token (not frozen black)", () => {
    const read = (status) => {
      const { result } = useHeader({ ...base, status });
      const { container } = render(<div>{result.current.titleAdornment}</div>, { wrapper });
      const cols = pillColors(rulesForElement(container.querySelector('[data-testid="status-pill"]')));
      cleanup();
      return cols;
    };
    // reference: resolve the theme's page background token through a real sx probe
    const { container: pc } = render(
      <ThemeCustomization>
        <StatusPill label="x" colorText="rgb(1, 2, 3)" colorBg="background.paper" />
      </ThemeCustomization>,
    );
    const pageBg = pillColors(rulesForElement(pc.querySelector('[data-testid="status-pill"]'))).background;
    cleanup();

    const cancelled = read("CANCELLED");
    const completed = read("COMPLETED");
    const planned = read("PLANNED");

    // 3-part chip: the TEXT colour equals the BORDER colour (both colorText)
    expect(cancelled.text).toBeTruthy();
    expect(cancelled.text).toBe(cancelled.border);
    // BACKGROUND = the theme's page background token (blends in), never #000
    expect(pageBg).toBeTruthy();
    expect(cancelled.background).toBe(pageBg);
    expect(cancelled.background.replace(/\s/g, "")).not.toMatch(/#000(000)?$/i);
    // shared across statuses
    expect(completed.background).toBe(cancelled.background);
    // TEXT colour tracks the status (from the constant): each status differs
    expect(cancelled.text).not.toBe(completed.text);
    expect(cancelled.text).not.toBe(planned.text);
    expect(completed.text).not.toBe(planned.text);
  });

  it("pill colour role tracks the status (Completed→success, Cancelled→error, On hold→warning)", () => {
    for (const status of ["COMPLETED", "CANCELLED", "ON_HOLD"]) {
      const { result } = renderHook(() => useActivityHeaderProps({ activity: { ...base, status } }), { wrapper });
      const { container } = render(<div>{result.current.titleAdornment}</div>, { wrapper });
      const pill = container.querySelector('[data-testid="status-pill"]');
      expect(pill.getAttribute("data-status-color")).toBe(ACTIVITY_STATUS_COLORS[status]);
      cleanup();
    }
  });
});

describe("ActivityHeader V2 — title is read-only", () => {
  it("does not provide onTitleSave (inline edit removed; editing via the drawer, S2c)", () => {
    const { result } = useHeader(base, { onSave: vi.fn() });
    expect(result.current.onTitleSave).toBeUndefined();
  });
});

// A real component so hook state (the open menu) re-renders on click — a static
// render of result.current.headerActions would never reflect the state change.
function ActionsHarness({ activity }) {
  const props = useActivityHeaderProps({ activity });
  return <div>{props.headerActions}</div>;
}

describe("ActivityHeader V2 — ⋮ menu is Edit | Delete only", () => {
  it("PLANNED menu: Complete + Edit + Cancel + Delete (no Reopen) — status actions restored in O-2b", async () => {
    render(
      <ThemeCustomization>
        <ActionsHarness activity={base} />
      </ThemeCustomization>,
    );
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Complete")).toBeInTheDocument();
    expect(screen.getByText("Edit")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();
    expect(screen.getByText("Delete")).toBeInTheDocument();
    // Reopen is Completed/Cancelled-only
    expect(screen.queryByText("Reopen")).not.toBeInTheDocument();
  });

  it("clicking Edit opens the edit content in the coque (openDrawer with EditActivityContent)", async () => {
    openDrawer.mockClear();
    render(
      <ThemeCustomization>
        <ActionsHarness activity={base} />
      </ThemeCustomization>,
    );
    await userEvent.click(screen.getByRole("button"));
    await userEvent.click(screen.getByText("Edit"));
    expect(openDrawer).toHaveBeenCalledTimes(1);
    const node = openDrawer.mock.calls[0][0];
    expect(node).toBeTruthy();
    // the injected node is the EditActivityContent, fed the activity
    expect(node.props.activity).toBe(base);
    // Option A: the coque title is passed via openDrawer's options arg
    expect(openDrawer.mock.calls[0][1]).toEqual({ title: "Edit activity" });
  });
});

describe("ActivityHeader V2 — R2 Overdue from backend is_overdue", () => {
  it("does NOT mark Overdue when is_overdue=false even for a due-today date", () => {
    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD (today)
    const { result } = useHeader({ ...base, due_date: today, is_overdue: false });
    render(<div>{result.current.infoItems}</div>, { wrapper });
    expect(screen.queryByText(/Overdue/)).not.toBeInTheDocument();
  });

  it("marks Overdue when the backend says is_overdue=true", () => {
    const { result } = useHeader({ ...base, due_date: "2020-01-01", is_overdue: true });
    render(<div>{result.current.infoItems}</div>, { wrapper });
    expect(screen.getByText(/Overdue/)).toBeInTheDocument();
  });

  it("renders the scheduled date without a -1 day shift (local parse)", () => {
    const { result } = useHeader({ ...base, scheduled_date: "2026-09-03", is_overdue: false });
    render(<div>{result.current.infoItems}</div>, { wrapper });
    expect(screen.getByText(/Sep 3, 2026/)).toBeInTheDocument();
  });
});
