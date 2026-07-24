// frontend/src/__tests__/sections/campaigns/CampaignCard.activitiesToday.test.jsx
//
// The TARGETED card's "N activities to do today" — the count the rep also sees
// on the playlist's "To do today" chip (activities_today from the list payload).
// It fills the gap the two OUTBOUND progress bars leave, in the big count's
// typographic variant (h2) and the warning tone.
//
// Real renders, no shared-component mocks (project rule: mocking shared
// components hides contract bugs). Mirrors CampaignCard.toChase.test.jsx —
// mk() factory with the ...overrides spread.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { createTheme } from "@mui/material/styles";

import CampaignCard from "sections/campaigns/CampaignCard";

afterEach(cleanup);

// The card uses the MUI default theme when no ThemeProvider is mounted (as
// here), so color="warning.main" resolves against this same palette. Never a
// hard-coded hex — the convention from CampaignCard.progressBar.test.jsx.
const theme = createTheme();

function hexToRgb(hex) {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

// Default OUTBOUND. On a TARGETED override the big count shows
// contactsToChase = targets_total - targets_worked = 12 - 5 = 7, deliberately
// distinct from the activities_today values asserted below so "5" / "1" / "0"
// are unambiguous.
function mk(overrides = {}) {
  return {
    id: "c1",
    name: "Q3 Outbound",
    campaign_type: "OUTBOUND",
    status: "ACTIVE",
    channel_override: "AUTO",
    accounts_count: 42,
    targets_total: 12,
    targets_worked: 5,
    activities_today: 5,
    planned_start_date: "2026-08-01",
    planned_end_date: "2026-09-01",
    actual_start_date: null,
    actual_end_date: null,
    owner: { id: "u1", full_name: "Paul DUPONT" },
    owner_team: { name: "SALES EMEA" },
    executor: null,
    executor_team: null,
    ...overrides,
  };
}

describe("CampaignCard — activities to do today", () => {
  it("TARGETED renders the count and the pluralised label", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "TARGETED", activities_today: 5 })} />);

    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("activities to do today")).toBeInTheDocument();
  });

  it("OUTBOUND does NOT render the block — its two bars show instead", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "OUTBOUND", activities_today: 5 })} />);

    // The block is gated on isTargeted, so nothing "to do today" on OUTBOUND.
    expect(screen.queryByText(/to do today/)).toBeNull();
    // The two OUTBOUND bars are present: the target Progress bar + the empty
    // Objective placeholder.
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(screen.getByText("Progress")).toBeInTheDocument();
    expect(screen.getByText("Objective")).toBeInTheDocument();
  });

  it("the count is coloured warning.main (theme-resolved, not a hex)", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "TARGETED", activities_today: 5 })} />);

    const count = screen.getByText("5");
    expect(getComputedStyle(count).color).toBe(hexToRgb(theme.palette.warning.main));
  });

  it("singular at 1 — 'activity', not 'activities'", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "TARGETED", activities_today: 1 })} />);

    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("activity to do today")).toBeInTheDocument();
    expect(screen.queryByText("activities to do today")).toBeNull();
  });

  it("0 renders 'the 0 activities to do today' state (plural)", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "TARGETED", activities_today: 0 })} />);

    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("activities to do today")).toBeInTheDocument();
  });

  it("null renders nothing — the null != 0 distinction", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "TARGETED", activities_today: null })} />);

    // No number, no label — an un-annotated view shows no stray zero.
    expect(screen.queryByText(/to do today/)).toBeNull();
  });
});
