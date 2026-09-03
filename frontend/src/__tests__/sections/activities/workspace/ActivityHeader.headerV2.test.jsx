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

import ThemeCustomization from "themes/index";
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

  it("the {text, background} table lives in the constants file, dark bg shared", () => {
    // 2 colours per status: text (=border) + background; background is one dark
    // token shared by every status (stored per-status to vary later).
    expect(ACTIVITY_STATUS_CHIP_COLORS.PLANNED.text).toBe("text.secondary");
    expect(ACTIVITY_STATUS_CHIP_COLORS.COMPLETED.text).toBe("success.main");
    expect(ACTIVITY_STATUS_CHIP_COLORS.CANCELLED.text).toBe("error.main");
    expect(ACTIVITY_STATUS_CHIP_COLORS.ON_HOLD.text).toBe("warning.main");
    const bg = ACTIVITY_STATUS_CHIP_COLORS.PLANNED.background;
    expect(ACTIVITY_STATUS_CHIP_COLORS.COMPLETED.background).toBe(bg);
    expect(ACTIVITY_STATUS_CHIP_COLORS.CANCELLED.background).toBe(bg);
    expect(ACTIVITY_STATUS_CHIP_COLORS.ON_HOLD.background).toBe(bg);
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

  it("text = border (both colorText), dark background, and text tracks the status", () => {
    const read = (status) => {
      const { result } = useHeader({ ...base, status });
      const { container } = render(<div>{result.current.titleAdornment}</div>, { wrapper });
      const cols = pillColors(rulesForElement(container.querySelector('[data-testid="status-pill"]')));
      cleanup();
      return cols;
    };
    const cancelled = read("CANCELLED");
    const completed = read("COMPLETED");
    const planned = read("PLANNED");

    // 3-part chip: the TEXT colour equals the BORDER colour (both colorText)
    expect(cancelled.text).toBeTruthy();
    expect(cancelled.text).toBe(cancelled.border);
    // dark BACKGROUND (common.black), shared across statuses
    expect(cancelled.background.replace(/\s/g, "")).toMatch(/#000(000)?/i);
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
  it("menu shows only Edit (inert) and Delete — no Complete/Cancel/Reopen", async () => {
    render(
      <ThemeCustomization>
        <ActionsHarness activity={base} />
      </ThemeCustomization>,
    );
    await userEvent.click(screen.getByRole("button"));
    // Edit (inert for now — drawer wired in S2c) + Delete (wired as before)
    expect(screen.getByText("Edit")).toBeInTheDocument();
    expect(screen.getByText("Delete")).toBeInTheDocument();
    // status-change items are gone (status change happens via Edit)
    expect(screen.queryByText("Complete")).not.toBeInTheDocument();
    expect(screen.queryByText("Log Response")).not.toBeInTheDocument();
    expect(screen.queryByText("Cancel")).not.toBeInTheDocument();
    expect(screen.queryByText("Reopen")).not.toBeInTheDocument();
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
