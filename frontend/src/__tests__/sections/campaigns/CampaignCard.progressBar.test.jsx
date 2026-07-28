// frontend/src/__tests__/sections/campaigns/CampaignCard.progressBar.test.jsx
//
// Commit 5c: the campaign card target-progress bar. Per-status color + label +
// fill, the two edge cases (total===0 short-circuit, total==null → no bar), the
// empty Objective placeholder, and the TARGETED "no bars at all" rule.
//
// Real renders, no shared-component mocks (project rule: mocking shared
// components hides contract bugs). Mirrors CampaignCard.enrichment.test.jsx.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, within, cleanup } from "@testing-library/react";
import { createTheme } from "@mui/material/styles";

import CampaignCard from "sections/campaigns/CampaignCard";

afterEach(cleanup);

// The card uses the MUI default theme when no ThemeProvider is mounted (as
// here), so the per-status label colours resolve against this same palette.
const theme = createTheme();

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

// OUTBOUND card with a partially-worked target set (7 / 10 → 70%, 3 remaining).
function mk(overrides = {}) {
  return {
    id: "c1",
    name: "Q3 Outbound",
    campaign_type: "OUTBOUND",
    status: "ACTIVE",
    accounts_count: 3,
    targets_total: 10,
    targets_worked: 7,
    planned_start_date: "2026-08-01",
    planned_end_date: "2026-09-01",
    actual_start_date: "2026-08-02",
    actual_end_date: null,
    owner: { id: "u1", full_name: "Paul DUPONT" },
    owner_team: { name: "SALES EMEA" },
    ...overrides,
  };
}

const bar = () => screen.getByRole("progressbar");
const fill = () => bar().getAttribute("aria-valuenow");
// The progress label lives in the same Box as the bar. Scope to it so the
// "Cancelled" label never collides with the schedule line's "Cancelled".
const progressZone = () => within(bar().parentElement);

// ==========================================================================
// PROGRESS BAR — per status: color + fill + label
// ==========================================================================

describe("CampaignCard progress bar — per status", () => {
  it("DRAFT → secondary, 0% fill, 'Drafted' (ignores worked)", () => {
    render(<CampaignCard campaign={mk({ status: "DRAFT" })} />);
    expect(bar().className).toMatch(/MuiLinearProgress-colorSecondary/);
    expect(fill()).toBe("0"); // forced 0 even though worked=7
    expect(progressZone().getByText("Drafted")).toBeInTheDocument();
  });

  it("ACTIVE → '{total - worked} left to contact' with real fill", () => {
    render(<CampaignCard campaign={mk({ status: "ACTIVE" })} />);
    expect(bar().className).toMatch(/MuiLinearProgress-colorPrimary/);
    expect(fill()).toBe("70");
    expect(progressZone().getByText("3 left to contact")).toBeInTheDocument();
  });

  it("PAUSED → warning, '{pct}% Paused', label coloured warning", () => {
    render(<CampaignCard campaign={mk({ status: "PAUSED" })} />);
    expect(bar().className).toMatch(/MuiLinearProgress-colorWarning/);
    expect(fill()).toBe("70");
    const label = progressZone().getByText("70% Paused");
    expect(getComputedStyle(label).color).toBe(hexToRgb(theme.palette.warning.main));
  });

  it("COMPLETED → success, REAL pct (NOT forced 100%), '{pct}% completed'", () => {
    // Regression guard: a completed-but-not-fully-worked campaign must show its
    // true percentage. worked=7 / total=10 → 70%, never 100%.
    render(<CampaignCard campaign={mk({ status: "COMPLETED" })} />);
    expect(bar().className).toMatch(/MuiLinearProgress-colorSuccess/);
    expect(fill()).toBe("70");
    expect(fill()).not.toBe("100");
    expect(progressZone().getByText("70% completed")).toBeInTheDocument();
    expect(screen.queryByText("100% completed")).toBeNull();
    expect(screen.queryByText(/100\s*%/)).toBeNull();
  });

  it("CANCELLED → error, real fill, 'Cancelled' (scoped to the bar)", () => {
    render(<CampaignCard campaign={mk({ status: "CANCELLED" })} />);
    expect(bar().className).toMatch(/MuiLinearProgress-colorError/);
    expect(fill()).toBe("70");
    const label = progressZone().getByText("Cancelled");
    expect(getComputedStyle(label).color).toBe(hexToRgb(theme.palette.error.main));
  });

  it("colours the %/label text by status, not just the bar", () => {
    render(<CampaignCard campaign={mk({ status: "COMPLETED" })} />);
    // bar carries the status colour class...
    expect(bar().className).toMatch(/MuiLinearProgress-colorSuccess/);
    // ...AND so does the label text (would fail if only the bar were coloured).
    const label = progressZone().getByText("70% completed");
    expect(getComputedStyle(label).color).toBe(hexToRgb(theme.palette.success.main));
  });
});

// ==========================================================================
// EDGE CASES
// ==========================================================================

describe("CampaignCard progress bar — edges", () => {
  // total===0 is checked BEFORE the status map, for every status. Prove the
  // short-circuit on two different statuses.
  it("total === 0 → 'No targets yet', no fill (DRAFT)", () => {
    render(<CampaignCard campaign={mk({ status: "DRAFT", targets_total: 0, targets_worked: 0 })} />);
    expect(screen.getByText("No targets yet")).toBeInTheDocument();
    expect(fill()).toBe("0");
    expect(screen.queryByText("Drafted")).toBeNull();
  });

  it("total === 0 → 'No targets yet', no fill (ACTIVE)", () => {
    render(<CampaignCard campaign={mk({ status: "ACTIVE", targets_total: 0, targets_worked: 0 })} />);
    expect(screen.getByText("No targets yet")).toBeInTheDocument();
    expect(fill()).toBe("0");
    expect(screen.queryByText(/left to contact/)).toBeNull();
  });

  it("total == null → NO bar at all (not 'No targets yet') — null ≠ 0", () => {
    render(<CampaignCard campaign={mk({ targets_total: null, targets_worked: null })} />);
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByText("No targets yet")).toBeNull();
  });

  it("total undefined (field absent) → NO bar at all", () => {
    const c = mk();
    delete c.targets_total;
    delete c.targets_worked;
    render(<CampaignCard campaign={c} />);
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByText("No targets yet")).toBeNull();
  });
});

// ==========================================================================
// OBJECTIVE BAR (bottom) — empty placeholder, no progress data
// ==========================================================================

describe("CampaignCard objective bar", () => {
  it("OUTBOUND shows the empty 'Objective' placeholder with '—'", () => {
    render(<CampaignCard campaign={mk({ status: "COMPLETED" })} />);
    expect(screen.getByText("Objective")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("carries NO progress data (it is not a second bar, no duplicated values)", () => {
    render(<CampaignCard campaign={mk({ status: "COMPLETED" })} />);
    // Exactly one progressbar: the Objective placeholder is a static box, so it
    // cannot duplicate the Progress bar's figures.
    expect(screen.getAllByRole("progressbar")).toHaveLength(1);
    // The completed % appears once (the Progress label), never echoed below.
    expect(screen.getAllByText("70% completed")).toHaveLength(1);
  });

  it("renders the objective advancement when primary_objective carries progress", () => {
    render(
      <CampaignCard
        campaign={mk({
          status: "ACTIVE",
          primary_objective: {
            objective_type: "DECISION_CYCLES",
            target_value: 4,
            current_value: 2,
            progress_percentage: 50,
          },
        })}
      />,
    );
    // The objective label (mapped) + "current / target" text are shown...
    expect(screen.getByText("Decision Cycles Created")).toBeInTheDocument();
    expect(screen.getByText("2 / 4")).toBeInTheDocument();
    // ...and now there are TWO bars: the target Progress bar + the objective bar.
    const bars = screen.getAllByRole("progressbar");
    expect(bars).toHaveLength(2);
    // The objective bar is filled to progress_percentage (50).
    expect(bars.some((b) => b.getAttribute("aria-valuenow") === "50")).toBe(true);
  });
});

// ==========================================================================
// TARGETED — neither bar renders
// ==========================================================================

describe("CampaignCard TARGETED — no bars at all", () => {
  it("renders neither the Progress bar nor the Objective placeholder", () => {
    // targets_total is set, to prove the gate is on campaign_type, not on data.
    render(
      <CampaignCard
        campaign={mk({
          campaign_type: "TARGETED",
          name: "My Targets",
          status: "ACTIVE",
          targets_total: 10,
          targets_worked: 7,
        })}
      />,
    );
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.queryByText("Objective")).toBeNull();
    expect(screen.queryByText("Progress")).toBeNull();
  });
});
