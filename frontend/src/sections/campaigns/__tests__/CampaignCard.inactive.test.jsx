// frontend/src/sections/campaigns/__tests__/CampaignCard.inactive.test.jsx
//
// InactB.3 — the inactivity signal on the campaign LIST card: a warning
// "Inactive" chip plus a subtle warning highlight (data-inactive marker),
// shown only when the backend flags campaign.is_inactive. The goal is to spot
// sleeping campaigns at a glance (prompt-to-act), so both must appear together
// and vanish when the campaign is active.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import CampaignCard from "sections/campaigns/CampaignCard";

afterEach(cleanup);

function mk(overrides = {}) {
  return {
    id: "c1",
    name: "Q3 Outbound",
    campaign_type: "OUTBOUND",
    channel_override: "AUTO",
    status: "ACTIVE",
    description: "",
    planned_start_date: "2026-01-01",
    planned_end_date: "2026-12-31",
    actual_start_date: null,
    actual_end_date: null,
    accounts_count: 3,
    activities_today: 0,
    targets_total: 10,
    targets_worked: 2,
    primary_objective: null,
    owner: { id: "u1", first_name: "Sam", last_name: "K" },
    owner_team: null,
    executor: null,
    executor_team: null,
    is_inactive: false,
    ...overrides,
  };
}

describe("CampaignCard — inactivity signal", () => {
  it("shows the Inactive chip and the highlight when is_inactive is true", () => {
    const { container } = render(<CampaignCard campaign={mk({ is_inactive: true })} />);
    expect(screen.getByText("Inactive")).toBeInTheDocument();
    expect(container.querySelector('[data-inactive="true"]')).not.toBeNull();
  });

  it("shows neither chip nor highlight when is_inactive is false", () => {
    const { container } = render(<CampaignCard campaign={mk({ is_inactive: false })} />);
    expect(screen.queryByText("Inactive")).not.toBeInTheDocument();
    expect(container.querySelector('[data-inactive="true"]')).toBeNull();
  });

  it("shows neither when is_inactive is absent (e.g. non-annotated payload)", () => {
    const c = mk();
    delete c.is_inactive;
    const { container } = render(<CampaignCard campaign={c} />);
    expect(screen.queryByText("Inactive")).not.toBeInTheDocument();
    expect(container.querySelector('[data-inactive="true"]')).toBeNull();
  });
});
