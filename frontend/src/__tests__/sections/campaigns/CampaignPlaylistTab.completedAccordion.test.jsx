// frontend/src/__tests__/sections/campaigns/CampaignPlaylistTab.completedAccordion.test.jsx
//
// TD-126 — the completed accordion must obey the product rule at the REAL call
// point. The masking of completed activities whose sequence reached a final
// state is TARGETED-only: OUTBOUND keeps ALL completed activities visible.
//
// The masking is a server-side filter (`active_sequence=true`), opted in by the
// frontend hook `useGetCompletedActivities`. This test captures the SWR key the
// hook actually produces when CampaignPlaylistTab mounts it — not an isolated
// URL builder — by mocking `swr` at the bottom and recording every key:
//
//   OUTBOUND → completed key has NO `active_sequence=true`  (show everything)
//   TARGETED → completed key HAS  `active_sequence=true`    (hide finished seqs)
//
// The accordion auto-expands for a COMPLETED campaign (component useEffect), so
// the completed fetch fires without any interaction; campaign_type — not status
// — is what drives the flag. The two campaign types produce DIFFERENT keys, which
// also proves the flag enters the SWR key (no cross-type cache sharing).

import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

// Record every SWR key the component graph subscribes to. Hoisted so the
// vi.mock factory (evaluated before the module body) can close over it.
const swrState = vi.hoisted(() => ({ keys: [] }));

vi.mock("swr", () => ({
  default: (key) => {
    swrState.keys.push(key);
    return {
      data: undefined,
      isLoading: false,
      error: undefined,
      isValidating: false,
      mutate: vi.fn(),
    };
  },
}));

// tenantKey passes the URL through unchanged, so the captured key IS the URL.
vi.mock("api/_swr", () => ({
  tenantKey: (url) => url,
  revalidateMultiple: vi.fn(),
}));

vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ tenantId: "tenant-1" }),
}));

vi.mock("utils/axiosClient", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
}));

// Presentational children — theme-heavy and irrelevant to URL capture; stub out.
vi.mock("components/cards/PlaylistActivityCard", () => ({ default: () => null }));
vi.mock("sections/campaigns/workspace/PlaylistProgressBar", () => ({
  default: () => null,
}));
vi.mock("sections/campaigns/CampaignOutcomeModal", () => ({
  default: () => null,
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import CampaignPlaylistTab from "sections/campaigns/workspace/CampaignPlaylistTab";

// Must be a real UUID — the hook drops non-UUID ids and would build no key.
const CID = "11111111-1111-4111-8111-111111111111";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  swrState.keys = [];
});

// The completed accordion's key is the only one hitting the activities endpoint
// with status=COMPLETED. COMPLETED status auto-expands the accordion so the fetch
// fires on mount.
function renderTab(campaignType) {
  render(
    <CampaignPlaylistTab
      campaignId={CID}
      campaign={{ id: CID, status: "COMPLETED", campaign_type: campaignType }}
    />,
  );
}

const completedKey = () =>
  swrState.keys.find(
    (k) => typeof k === "string" && k.includes("status=COMPLETED"),
  );

// ==============================|| TESTS ||============================== //

describe("CampaignPlaylistTab — completed accordion active_sequence gating", () => {
  it("OUTBOUND: completed fetch omits active_sequence=true (all completed stay visible)", () => {
    renderTab("OUTBOUND");

    const key = completedKey();
    // Non-vacuity: the completed fetch actually fired.
    expect(key).toBeTruthy();
    expect(key).not.toContain("active_sequence=true");
  });

  it("TARGETED: completed fetch keeps active_sequence=true (finished sequences hidden)", () => {
    renderTab("TARGETED");

    const key = completedKey();
    expect(key).toBeTruthy();
    expect(key).toContain("active_sequence=true");
  });

  it("the two types produce different keys — the flag enters the SWR key", () => {
    renderTab("OUTBOUND");
    const outboundKey = completedKey();

    cleanup();
    swrState.keys = [];

    renderTab("TARGETED");
    const targetedKey = completedKey();

    expect(outboundKey).toBeTruthy();
    expect(targetedKey).toBeTruthy();
    expect(outboundKey).not.toEqual(targetedKey);
  });
});
