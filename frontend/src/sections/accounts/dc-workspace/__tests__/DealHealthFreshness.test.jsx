// frontend/src/sections/accounts/dc-workspace/__tests__/DealHealthFreshness.test.jsx
//
// Sprint « Deal health v2 », step 8 — the freshness of the deal health on the
// Strategic tab (PO decision of 20/11). The server serves it beside the latest
// snapshot (GET .../health-snapshots/latest/ → freshness), with or without a
// snapshot. When it applies and there is new information, a WARNING sits next
// to Run / Re-run:
//   * « New information to analyse since <date> » (a snapshot exists);
//   * « No deal health yet » (no analysis at all).
// Nothing when it does not apply (before Technical Fit, closed cycle) or when
// nothing is new. Never « stale ».
//
// The real StrategicTab and the real api/aiPipelines/dealHealth.js + SWR; only
// the HTTP client, the auth and the secondary views are mocked.

import { render, screen, cleanup } from "@testing-library/react";
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { SWRConfig, mutate as swrMutate } from "swr";

const CYCLE_ID = "33333333-3333-4333-8333-333333333333";
const LATEST_URL = `/decision_cycles/${CYCLE_ID}/health-snapshots/latest/`;

vi.mock("utils/axiosClient", () => ({ api: { post: vi.fn(), get: vi.fn() } }));
vi.mock("hooks/useAuth", () => ({ useAuth: () => ({ tenantId: "tenant-1" }) }));
vi.mock("api/accounts/decisionCycles", () => ({
  useGetReadiness: () => ({ readiness: null, readinessLoading: false }),
}));
vi.mock("utils/displayError", () => ({
  displaySuccessSnackbar: vi.fn(),
  displayErrorSnackbar: vi.fn(),
  displayWarningSnackbar: vi.fn(),
  displayInfoSnackbar: vi.fn(),
}));
vi.mock("sections/accounts/dc-workspace/DealHealthView", () => ({
  default: ({ snapshot }) => <p>{snapshot.diagnostic.global_reading}</p>,
}));
vi.mock("sections/accounts/dc-workspace/ThemesView", () => ({ default: () => null }));
vi.mock("sections/accounts/dc-workspace/ReadinessScoreGauge", () => ({ default: () => null }));

import { api } from "utils/axiosClient";
import StrategicTab from "sections/accounts/dc-workspace/StrategicTab";

const SNAPSHOT = { id: "snap-a", diagnostic: { global_reading: "Reading A" } };
const LAST_AT = "2026-11-18T10:00:00+00:00";

function serve(snapshot, freshness) {
  api.get.mockImplementation(async (url) => (url === LATEST_URL
    ? { success: true, data: { success: true, data: snapshot, freshness } }
    : { success: true, data: { success: true, data: [] } }));
}

function renderTab() {
  return render(
    <SWRConfig value={{ dedupingInterval: 0, fetcher: ([url]) => api.get(url).then((r) => r.data) }}>
      <StrategicTab cycleId={CYCLE_ID} accountId="acc-1" cycle={{}} />
    </SWRConfig>,
  );
}

const warning = () => screen.queryByTestId("deal-health-freshness");

beforeEach(() => vi.clearAllMocks());
afterEach(async () => {
  cleanup();
  await swrMutate(() => true, undefined, { revalidate: false });
});

describe("Deal health — the freshness warning of the Strategic tab", () => {
  it("(a) new sources since the snapshot → « New information to analyse since <date> », warning", async () => {
    serve(SNAPSHOT, { applies: true, has_new_info: true, last_analysis_at: LAST_AT, reasons: ["NEW_SOURCES"] });
    renderTab();
    await screen.findByText("Reading A");

    const alert = warning();
    expect(alert).not.toBeNull();
    expect(alert).toHaveTextContent("New information to analyse since Nov 18, 2026");
    expect(alert.className).toMatch(/MuiAlert-.*[Ww]arning/);      // the theme's warning
    // Next to Re-run.
    expect(alert.parentElement).toContainElement(screen.getByRole("button", { name: /re-run/i }));
  });

  it("(d) no analysis yet → « No deal health yet », warning, next to Run", async () => {
    serve(null, { applies: true, has_new_info: true, last_analysis_at: null, reasons: ["NO_ANALYSIS_YET"] });
    renderTab();
    await screen.findByText(/No deal health diagnostic has been run yet/);

    const alert = warning();
    expect(alert).not.toBeNull();
    expect(alert).toHaveTextContent("No deal health yet");
    expect(alert.className).toMatch(/MuiAlert-.*[Ww]arning/);
    expect(alert.parentElement).toContainElement(screen.getByRole("button", { name: /run deal health/i }));
  });

  it("(b) nothing new → no warning", async () => {
    serve(SNAPSHOT, { applies: true, has_new_info: false, last_analysis_at: LAST_AT, reasons: [] });
    renderTab();
    await screen.findByText("Reading A");
    expect(warning()).toBeNull();
  });

  it.each([
    ["(c) before Technical Fit", SNAPSHOT],
    ["(f) a closed cycle", SNAPSHOT],
    ["(c) before Technical Fit, no snapshot", null],
  ])("%s → applies false → no warning", async (_case, snapshot) => {
    serve(snapshot, { applies: false, has_new_info: false, last_analysis_at: snapshot ? LAST_AT : null, reasons: [] });
    renderTab();
    await screen.findByText(snapshot ? "Reading A" : /No deal health diagnostic has been run yet/);
    expect(warning()).toBeNull();
  });
});
