// frontend/src/__tests__/sections/campaigns/CampaignCard.channelChip.test.jsx
//
// The Email Only channel chip on the campaign card. Gated explicitly on
// isOutbound && channel_override === 'EMAIL_ONLY' — a TARGETED campaign in
// EMAIL_ONLY must show nothing (proves the gate is explicit, not incidental).
//
// Real renders, no shared-component mocks. Mirrors CampaignCard.enrichment /
// progressBar tests (mk() factory with the ...overrides spread). Expected label
// comes from the shared CHANNEL_LABELS, not a literal.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";

import CampaignCard from "sections/campaigns/CampaignCard";
import { CHANNEL_LABELS } from "api/campaigns/campaigns";

afterEach(cleanup);

const EMAIL_ONLY_LABEL = CHANNEL_LABELS.EMAIL_ONLY;

function mk(overrides = {}) {
  return {
    id: "c1",
    name: "Q3 Outbound",
    campaign_type: "OUTBOUND",
    status: "DRAFT",
    channel_override: "AUTO",
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

describe("CampaignCard — Email Only channel chip", () => {
  it("renders the chip for an OUTBOUND EMAIL_ONLY campaign", () => {
    render(
      <CampaignCard
        campaign={mk({ campaign_type: "OUTBOUND", channel_override: "EMAIL_ONLY" })}
      />,
    );
    const chip = screen.getByText(EMAIL_ONLY_LABEL);
    expect(chip).toBeInTheDocument();
    // color="info" from the theme (assert the MUI class, never a hex).
    expect(chip.closest(".MuiChip-root").className).toMatch(/MuiChip-colorInfo/);
  });

  it("does NOT render the chip for an OUTBOUND AUTO campaign", () => {
    render(
      <CampaignCard
        campaign={mk({ campaign_type: "OUTBOUND", channel_override: "AUTO" })}
      />,
    );
    expect(screen.queryByText(EMAIL_ONLY_LABEL)).toBeNull();
  });

  it("does NOT render the chip for a TARGETED campaign even when EMAIL_ONLY", () => {
    // channel_override IS 'EMAIL_ONLY' here — the chip is absent purely because
    // the gate is isOutbound, not because the data is missing.
    render(
      <CampaignCard
        campaign={mk({
          campaign_type: "TARGETED",
          name: "My Targets",
          channel_override: "EMAIL_ONLY",
        })}
      />,
    );
    expect(screen.queryByText(EMAIL_ONLY_LABEL)).toBeNull();
  });
});
