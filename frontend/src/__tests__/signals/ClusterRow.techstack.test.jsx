// frontend/src/__tests__/signals/ClusterRow.techstack.test.jsx
//
// Sub-step 3 (Cluster Tech Stack): the shared ClusterRow renders a bare tech
// row — tool name + "N signals" + last confirmation only — while the axis-based
// rows (pain/objective/impact) keep their full epurated meta (freshness, period,
// departments). No priority badge on either (ClusterRow never had one).

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import ClusterRow from "sections/accounts/signals/ClusterRow";

const TECH_ROW = {
  canonical_key: "hubspot",
  signal_type: "tech_stack",
  summary: "HubSpot",
  signal_count: 2,
  pending_count: 1,
  freshness_status: "FRESH",
  period_start: "2026-04-01T10:00:00Z",
  period_end: "2026-05-01T10:00:00Z",
  last_confirmed_at: "2026-05-01T10:00:00Z",
  departments: [],
  decision_cycle_ids: ["dc-1"],
};

const PAIN_ROW = {
  canonical_key: "pain:OPS:TIME",
  signal_type: "pain",
  summary: "Reporting is slow",
  signal_count: 3,
  pending_count: 0,
  freshness_status: "FRESH",
  period_start: "2026-04-01T10:00:00Z",
  period_end: "2026-05-01T10:00:00Z",
  last_confirmed_at: "2026-05-01T10:00:00Z",
  departments: [],
  decision_cycle_ids: [],
};

afterEach(() => cleanup());

describe("ClusterRow — TechStack epurated row", () => {
  it("shows tool name + N signals + last confirmation, nothing else", () => {
    render(<ClusterRow cluster={TECH_ROW} surface="account" />);

    expect(screen.getByText("HubSpot")).toBeInTheDocument();
    expect(screen.getByText("2 signals")).toBeInTheDocument();
    expect(screen.getByText(/Last confirmed/)).toBeInTheDocument();

    // Epurated: no freshness chip, no "N to validate", no DC count on tech.
    expect(screen.queryByText("Fresh")).not.toBeInTheDocument();
    expect(screen.queryByText(/to validate/)).not.toBeInTheDocument();
    expect(screen.queryByText(/DC/)).not.toBeInTheDocument();
  });
});

describe("ClusterRow — axis-based rows unchanged (non-regression)", () => {
  it("a pain row keeps its freshness meta and shows no 'Last confirmed' label", () => {
    render(<ClusterRow cluster={PAIN_ROW} surface="account" />);

    expect(screen.getByText("Reporting is slow")).toBeInTheDocument();
    expect(screen.getByText("3 signals")).toBeInTheDocument();
    // The axis-based row keeps its freshness chip.
    expect(screen.getByText("Fresh")).toBeInTheDocument();
    // The "Last confirmed" caption is tech-only.
    expect(screen.queryByText(/Last confirmed/)).not.toBeInTheDocument();
  });
});
