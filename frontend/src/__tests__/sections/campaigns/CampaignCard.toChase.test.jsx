// frontend/src/__tests__/sections/campaigns/CampaignCard.toChase.test.jsx
//
// The big count on the campaign card. A TARGETED campaign shows the contacts
// still to chase (targets_total − targets_worked, the non-final ones) labelled
// "contacts to chase"; an OUTBOUND campaign keeps its enrolled-account count
// labelled "accounts". A TARGETED campaign with no targets reads "0 contacts to
// chase", not something odd.
//
// Real renders, no shared-component mocks. Mirrors CampaignCard.channelChip
// (mk() factory with the ...overrides spread).

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import CampaignCard from "sections/campaigns/CampaignCard";

afterEach(cleanup);

function mk(overrides = {}) {
  return {
    id: "c1",
    name: "Q3 Outbound",
    campaign_type: "OUTBOUND",
    status: "ACTIVE",
    channel_override: "AUTO",
    accounts_count: 42,
    // null → renderTargetProgress bails (no bar), keeping the OUTBOUND count
    // spot free of stray numbers for the assertions below.
    targets_total: null,
    targets_worked: null,
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

describe("CampaignCard — big count", () => {
  it("TARGETED shows targets_total − targets_worked as 'contacts to chase'", () => {
    render(
      <CampaignCard
        campaign={mk({
          campaign_type: "TARGETED",
          name: "My Targets",
          targets_total: 12,
          targets_worked: 5,
        })}
      />,
    );
    // 12 − 5 = 7 contacts still to chase.
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("contacts to chase")).toBeInTheDocument();
    // The account label is not used on a TARGETED card.
    expect(screen.queryByText("accounts")).toBeNull();
  });

  it("OUTBOUND keeps accounts_count labelled 'accounts'", () => {
    render(<CampaignCard campaign={mk({ campaign_type: "OUTBOUND" })} />);

    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("accounts")).toBeInTheDocument();
    expect(screen.queryByText("contacts to chase")).toBeNull();
  });

  it("TARGETED with no targets reads '0 contacts to chase' (plural at 0)", () => {
    render(
      <CampaignCard
        campaign={mk({
          campaign_type: "TARGETED",
          name: "Empty Chase",
          targets_total: 0,
          targets_worked: 0,
        })}
      />,
    );
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("contacts to chase")).toBeInTheDocument();
  });

  it("TARGETED with exactly one to chase reads '1 contact to chase' (singular)", () => {
    render(
      <CampaignCard
        campaign={mk({
          campaign_type: "TARGETED",
          name: "One Chase",
          targets_total: 1,
          targets_worked: 0,
        })}
      />,
    );
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("contact to chase")).toBeInTheDocument();
    expect(screen.queryByText("contacts to chase")).toBeNull();
  });

  it("OUTBOUND with one account reads '1 account' (singular)", () => {
    render(
      <CampaignCard campaign={mk({ campaign_type: "OUTBOUND", accounts_count: 1 })} />,
    );
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("account")).toBeInTheDocument();
    expect(screen.queryByText("accounts")).toBeNull();
  });
});
