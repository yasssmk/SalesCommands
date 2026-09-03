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

const wrapper = ({ children }) => <ThemeCustomization>{children}</ThemeCustomization>;

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

describe("ActivityHeader V2 — avatar tile + status chip", () => {
  it("avatar is a rounded (non-circular) tile carrying the type icon", () => {
    const { result } = useHeader(base);
    const { container } = render(<div>{result.current.avatar}</div>, { wrapper });
    // type icon present
    expect(container.querySelector(".anticon-phone")).toBeTruthy();
    // rounded tile, not a circle (MUI rounded variant)
    expect(container.querySelector(".MuiAvatar-rounded")).toBeTruthy();
    expect(container.querySelector(".MuiAvatar-circular")).toBeFalsy();
  });

  it("chips = a SINGLE status chip; no type/campaign/outcome chip", () => {
    const { result } = useHeader({ ...base, campaign_detail: { id: "cmp1", name: "Q2" }, outcome: "SUCCESSFUL" });
    const { container } = render(<div>{result.current.chips}</div>, { wrapper });
    const chips = container.querySelectorAll(".MuiChip-root");
    expect(chips.length).toBe(1);
    expect(screen.getByText("Planned")).toBeInTheDocument();
    expect(screen.queryByText(/Campaign:/)).not.toBeInTheDocument();
  });

  it("status chip colour follows the status (Planned neutral, Completed success, Cancelled error)", () => {
    const planned = renderHook(() => useActivityHeaderProps({ activity: { ...base, status: "PLANNED" } }), { wrapper });
    const { container: c1 } = render(<div>{planned.result.current.chips}</div>, { wrapper });
    expect(c1.querySelector(".MuiChip-colorDefault")).toBeTruthy();
    cleanup();

    const done = renderHook(() => useActivityHeaderProps({ activity: { ...base, status: "COMPLETED" } }), { wrapper });
    const { container: c2 } = render(<div>{done.result.current.chips}</div>, { wrapper });
    expect(c2.querySelector(".MuiChip-colorSuccess")).toBeTruthy();
    cleanup();

    const cancelled = renderHook(() => useActivityHeaderProps({ activity: { ...base, status: "CANCELLED" } }), { wrapper });
    const { container: c3 } = render(<div>{cancelled.result.current.chips}</div>, { wrapper });
    expect(c3.querySelector(".MuiChip-colorError")).toBeTruthy();
  });
});

// A real component so hook state (the open menu) re-renders on click — a static
// render of result.current.headerActions would never reflect the state change.
function ActionsHarness({ activity }) {
  const props = useActivityHeaderProps({ activity });
  return <div>{props.headerActions}</div>;
}

describe("ActivityHeader V2 — ⋮ menu offers status change + Edit", () => {
  it("menu shows a status action and an Edit item", async () => {
    render(
      <ThemeCustomization>
        <ActionsHarness activity={base} />
      </ThemeCustomization>,
    );
    await userEvent.click(screen.getByRole("button"));
    // status change (Complete for a planned standalone activity)
    expect(screen.getByText("Complete")).toBeInTheDocument();
    // Edit (inert for now — drawer wired in S2c)
    expect(screen.getByText("Edit")).toBeInTheDocument();
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
