// frontend/src/__tests__/sections/campaigns/CampaignPlaylistTab.inactiveBanner.test.jsx
//
// InactB.3 — the playlist inactivity banner is driven solely by the backend
// is_inactive flag and carries NO hardcoded day threshold (the copy stays
// threshold-agnostic so it can never drift from N_INACTIVE_DAYS). Shown when
// is_inactive is true, absent otherwise.

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, cleanup, screen } from "@testing-library/react";

// Same lightweight harness as the completed-accordion test: stub the data
// layer so the tab renders without a real API.
vi.mock("swr", () => ({
  default: () => ({
    data: undefined,
    isLoading: false,
    error: undefined,
    isValidating: false,
    mutate: vi.fn(),
  }),
}));
vi.mock("api/_swr", () => ({ tenantKey: (url) => url, revalidateMultiple: vi.fn() }));
vi.mock("hooks/useAuth", () => ({ useAuth: () => ({ tenantId: "tenant-1" }) }));
vi.mock("utils/axiosClient", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));
vi.mock("components/cards/PlaylistActivityCard", () => ({ default: () => null }));
vi.mock("sections/campaigns/CampaignOutcomeModal", () => ({ default: () => null }));

import CampaignPlaylistTab from "sections/campaigns/workspace/CampaignPlaylistTab";

const CID = "11111111-1111-4111-8111-111111111111";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function renderTab(is_inactive) {
  render(
    <CampaignPlaylistTab
      campaignId={CID}
      campaign={{ id: CID, status: "ACTIVE", campaign_type: "OUTBOUND", is_inactive }}
    />,
  );
}

describe("CampaignPlaylistTab — inactivity banner", () => {
  it("renders the banner when is_inactive is true", () => {
    renderTab(true);
    expect(screen.getByText(/no recent activity/i)).toBeInTheDocument();
    expect(screen.getByText(/may need attention/i)).toBeInTheDocument();
  });

  it("hides the banner when is_inactive is false", () => {
    renderTab(false);
    expect(screen.queryByText(/no recent activity/i)).toBeNull();
  });

  it("carries no hardcoded day threshold in the copy", () => {
    renderTab(true);
    // The old copy read "in the last 30 days" — the number must be gone so it
    // can never drift from the backend threshold.
    expect(screen.queryByText(/\b30\b/)).toBeNull();
    expect(screen.queryByText(/last \d+ days/i)).toBeNull();
  });
});
