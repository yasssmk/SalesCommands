// frontend/src/__tests__/sections/campaigns/CampaignHeader.dates.test.jsx
//
// The workspace header used to read campaign.start_date / end_date — fields no
// serializer emits — so the date row was always blank. Commit 5b points it at
// the same status→date rule as the card (planned_*/actual_*). We render the
// hook's infoItems and assert the date line now appears.

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { ThemeProvider, createTheme } from "@mui/material/styles";

import useCampaignHeaderProps from "sections/campaigns/workspace/CampaignHeader";

afterEach(cleanup);

// Render just the infoItems the hook produces (avoids mounting the action
// split-button, which is irrelevant to the date row).
function Harness({ campaign }) {
  const { infoItems } = useCampaignHeaderProps({ campaign });
  return <div>{infoItems}</div>;
}

const renderHeader = (campaign) =>
  render(
    <ThemeProvider theme={createTheme()}>
      <Harness campaign={campaign} />
    </ThemeProvider>,
  );

const baseCampaign = {
  id: "c1",
  name: "Q3 Outbound",
  campaign_type: "OUTBOUND",
  status: "ACTIVE",
  actual_start_date: "2026-08-05",
  planned_start_date: "2026-08-01",
  planned_end_date: "2999-09-01",
  members: [],
};

describe("CampaignHeader — date row reads the real fields", () => {
  it("renders the active schedule from actual_start_date → planned_end_date", () => {
    renderHeader(baseCampaign);
    expect(screen.getByText("2026-08-05 → 2999-09-01")).toBeInTheDocument();
  });

  it("DRAFT renders 'Starts {planned_start_date}'", () => {
    renderHeader({ ...baseCampaign, status: "DRAFT", actual_start_date: null });
    expect(screen.getByText("Starts 2026-08-01")).toBeInTheDocument();
  });

  it("does not silently blank the row when only planned/actual fields exist", () => {
    // The old code keyed on start_date/end_date (absent) -> nothing. Guard it.
    renderHeader({ ...baseCampaign, status: "COMPLETED", actual_end_date: "2026-09-10" });
    expect(screen.getByText("Completed the 2026-09-10")).toBeInTheDocument();
  });
});
