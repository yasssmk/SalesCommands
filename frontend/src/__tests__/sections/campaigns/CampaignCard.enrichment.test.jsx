// frontend/src/__tests__/sections/campaigns/CampaignCard.enrichment.test.jsx
//
// Card enrichment (commit 5b): status-by-date line off the real
// planned_*/actual_* fields, and the owner/executor attribution block.
// Real renders — no shared-component mocks.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import CampaignCard from "sections/campaigns/CampaignCard";

afterEach(cleanup);

function mk(overrides = {}) {
  return {
    id: "c1",
    name: "Q3 Outbound",
    campaign_type: "OUTBOUND",
    status: "DRAFT",
    accounts_count: 3,
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

describe("CampaignCard — status-by-date line", () => {
  it("DRAFT shows 'Starts {planned_start_date}'", () => {
    render(<CampaignCard campaign={mk()} />);
    expect(screen.getByText("Starts 2026-08-01")).toBeInTheDocument();
  });

  it("COMPLETED shows 'Completed the {actual_end_date}'", () => {
    render(
      <CampaignCard
        campaign={mk({ status: "COMPLETED", actual_end_date: "2026-09-10" })}
      />,
    );
    expect(screen.getByText("Completed the 2026-09-10")).toBeInTheDocument();
  });

  it("CANCELLED shows 'Cancelled' with no date", () => {
    render(<CampaignCard campaign={mk({ status: "CANCELLED" })} />);
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
    expect(screen.queryByText(/\d{4}-\d{2}-\d{2}/)).toBeNull();
  });

  it("never shows the old blank/placeholder date copy", () => {
    render(<CampaignCard campaign={mk()} />);
    expect(screen.queryByText("No dates set")).toBeNull();
  });
});

describe("CampaignCard — attribution", () => {
  it("shows owner name and team", () => {
    render(<CampaignCard campaign={mk()} />);
    expect(screen.getByText("Owner: Paul DUPONT — SALES EMEA")).toBeInTheDocument();
  });

  it("hides the executor line when executor is null (defaults to owner)", () => {
    render(<CampaignCard campaign={mk()} />);
    expect(screen.queryByText(/^Executor:/)).toBeNull();
  });

  it("shows a distinct executor with its own team", () => {
    render(
      <CampaignCard
        campaign={mk({
          executor: { id: "u2", full_name: "Jacques PAUL" },
          executor_team: { name: "SDR EMEA" },
        })}
      />,
    );
    expect(
      screen.getByText("Executor: Jacques PAUL — SDR EMEA"),
    ).toBeInTheDocument();
  });

  it("hides the executor line when executor equals the owner", () => {
    render(
      <CampaignCard
        campaign={mk({ executor: { id: "u1", full_name: "Paul DUPONT" } })}
      />,
    );
    // Same id as owner -> redundant -> not rendered.
    expect(screen.queryByText(/^Executor:/)).toBeNull();
  });
});
