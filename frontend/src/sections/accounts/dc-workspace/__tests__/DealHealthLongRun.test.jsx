// frontend/src/sections/accounts/dc-workspace/__tests__/DealHealthLongRun.test.jsx
//
// Sprint « Deal health v2 », sub-step 5c, anomaly 2 — a deal health run lasts
// more than a minute (reasoning model). The POST outlasts the client's bulk
// timeout; the server keeps working and writes the snapshot later.
//
// Expected: from the click, EVERY run trigger of the page (the header button
// and the Strategic tab's) stays « in progress » (disabled) until the new
// snapshot arrives OR the polling window ends; the snapshot shows up WITHOUT
// a reload; at the end of the window with no result → an INFO message (never
// red), the buttons are active again. The client timeout is not an error.
//
// Real components and the real api/aiPipelines/dealHealth.js + SWR; only the
// HTTP client, the auth and the secondary views are mocked.

import { render, screen, cleanup, fireEvent, act } from "@testing-library/react";
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { SWRConfig, mutate as swrMutate } from "swr";

const CYCLE_ID = "11111111-1111-4111-8111-111111111111";
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
import {
  displayErrorSnackbar,
  displayInfoSnackbar,
  displaySuccessSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";
import StrategicTab from "sections/accounts/dc-workspace/StrategicTab";
import DealHealthRunButton from "sections/accounts/dc-workspace/DealHealthRunButton";

const SNAPSHOT_A = { id: "snap-a", diagnostic: { global_reading: "Reading A" } };
const SNAPSHOT_B = { id: "snap-b", diagnostic: { global_reading: "Reading B" } };

const ok = (data) => ({ success: true, data: { success: true, data } });

let start;
let snapshotBAt; // ms after the click when the server has written B (null = never)

function renderPage() {
  return render(
    <SWRConfig
      value={{
        // The app's default cache (app/ProviderWrapper.jsx: no provider), so
        // the global revalidation of api/_swr.js reaches these keys.
        dedupingInterval: 0,
        fetcher: ([url]) => api.get(url).then((r) => r.data),
      }}
    >
      <DealHealthRunButton cycleId={CYCLE_ID} />
      <StrategicTab cycleId={CYCLE_ID} accountId="acc-1" cycle={{}} />
    </SWRConfig>,
  );
}

const runButtons = () => screen.getAllByRole("button");

async function advance(ms) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: false });
  vi.clearAllMocks();
  start = null;
  api.get.mockImplementation(async (url) => {
    if (url === LATEST_URL) {
      const written = start !== null && snapshotBAt !== null && Date.now() - start >= snapshotBAt;
      return ok(written ? SNAPSHOT_B : SNAPSHOT_A);
    }
    return ok([]);
  });
  // The client gives up (bulk-profile timeout) while the server keeps working.
  api.post.mockImplementation(async () => ({
    success: false, isTimeout: true, status: 408, error: "timeout",
  }));
});

afterEach(async () => {
  cleanup();
  vi.useRealTimers();
  await swrMutate(() => true, undefined, { revalidate: false }); // clear the cache
});

async function clickRun() {
  await advance(10); // SWR's first fetch (fake timers: no findBy*)
  expect(screen.getByText("Reading A")).toBeTruthy();
  start = Date.now();
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /re-run/i }));
  });
}

describe("Deal health — a run longer than the client timeout", () => {
  it("keeps every trigger in progress, then shows the new snapshot without a reload", async () => {
    snapshotBAt = 30_000;
    renderPage();
    await clickRun();

    // 25 s: the server is still working — no trigger may start a 2nd run.
    await advance(25_000);
    expect(screen.queryByText("Reading B")).toBeNull();
    expect(runButtons().every((b) => b.disabled)).toBe(true);
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
    expect(displayErrorSnackbar).not.toHaveBeenCalled();

    // The snapshot is written at 30 s: it shows up, no reload.
    await advance(15_000);
    expect(screen.getByText("Reading B")).toBeTruthy();
    expect(runButtons().every((b) => !b.disabled)).toBe(true);
    expect(displaySuccessSnackbar).toHaveBeenCalled();
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
  });

  it("ends the polling window with an INFO message and active buttons", async () => {
    snapshotBAt = null; // never within the window
    renderPage();
    await clickRun();

    await advance(60_000);
    expect(runButtons().every((b) => b.disabled)).toBe(true); // still waiting

    await advance(200_000); // past the window
    expect(displayInfoSnackbar).toHaveBeenCalledTimes(1);
    expect(displayWarningSnackbar).not.toHaveBeenCalled();
    expect(displayErrorSnackbar).not.toHaveBeenCalled();
    expect(runButtons().every((b) => !b.disabled)).toBe(true);
  });
});
