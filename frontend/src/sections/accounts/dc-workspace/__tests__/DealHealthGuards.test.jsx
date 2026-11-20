// frontend/src/sections/accounts/dc-workspace/__tests__/DealHealthGuards.test.jsx
//
// Sprint « Deal health v2 », step 6 — the guards of a deal health run, front.
//   * Layer 1 (Redis, TD-50): runDealHealth sends a DETERMINISTIC
//     Idempotency-Key, sha256(cycleId::latestSnapshotId) — a double click or
//     a second tab on the same state is the same operation server side.
//   * A10, « nothing new since the last analysis » (200 + INFO code): an
//     INFORMATION with the date of the last analysis — never red.
//   * A10, a closed decision cycle (WON / LOST / NOT_QUALIFIED): every
//     trigger is disabled, with an info on hover; the server's CYCLE_CLOSED
//     code (the server stays the guard) is an INFORMATION too. 6c (PO): an
//     ON_HOLD cycle is NOT closed — the triggers stay active.
//   * 6b, the right to run (admin, manager, the cycle's owner — served by the
//     server as can_run_deal_health): without it, every trigger is disabled
//     with an info on hover.
//
// Real components (StrategicTab + DealHealthRunButton) and the real
// api/aiPipelines/dealHealth.js + SWR; only the HTTP client, the auth and the
// secondary views are mocked.

import { createHash } from "node:crypto";
import { render, screen, cleanup, fireEvent, act, waitFor } from "@testing-library/react";
import { describe, it, expect, afterEach, beforeEach, vi } from "vitest";
import { SWRConfig, mutate as swrMutate } from "swr";

const CYCLE_ID = "22222222-2222-4222-8222-222222222222";
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
import {
  DEAL_HEALTH_CLOSED_OUTCOMES,
  DEAL_HEALTH_RUN_LABELS,
  isDealHealthClosed,
} from "api/aiPipelines/dealHealth";
import StrategicTab from "sections/accounts/dc-workspace/StrategicTab";
import DealHealthRunButton from "sections/accounts/dc-workspace/DealHealthRunButton";

const SNAPSHOT_A = { id: "snap-a", diagnostic: { global_reading: "Reading A" } };
const ok = (data) => ({ success: true, data: { success: true, data } });
const info = (code, lastAt) => ({
  success: true,
  data: {
    success: true,
    code,
    message: "server message",
    data: { run: null, snapshot: null, last_analysis_at: lastAt },
  },
});

function renderPage(cycle = {}) {
  // The DC header's rules (DCWorkspaceHeader passes isDealHealthClosed and
  // the server's can_run_deal_health, 6b).
  const closed = isDealHealthClosed(cycle);
  const allowed = cycle.can_run_deal_health !== false;
  return render(
    <SWRConfig value={{ dedupingInterval: 0, fetcher: ([url]) => api.get(url).then((r) => r.data) }}>
      <DealHealthRunButton cycleId={CYCLE_ID} closed={closed} allowed={allowed} />
      <StrategicTab cycleId={CYCLE_ID} accountId="acc-1" cycle={cycle} />
    </SWRConfig>,
  );
}

const noRedNorWarning = () => {
  expect(displayErrorSnackbar).not.toHaveBeenCalled();
  expect(displayWarningSnackbar).not.toHaveBeenCalled();
  expect(displaySuccessSnackbar).not.toHaveBeenCalled();
};

beforeEach(() => {
  vi.clearAllMocks();
  api.get.mockImplementation(async (url) => (url === LATEST_URL ? ok(SNAPSHOT_A) : ok([])));
});

afterEach(async () => {
  cleanup();
  await swrMutate(() => true, undefined, { revalidate: false });
});

async function clickReRun() {
  await screen.findByText("Reading A");
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /re-run/i }));
  });
}

describe("Deal health — the run guards", () => {
  it("sends a deterministic Idempotency-Key: sha256(cycleId::latestSnapshotId)", async () => {
    api.post.mockResolvedValue(ok({ run: {}, snapshot: SNAPSHOT_A }));
    renderPage();
    await clickReRun();

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [, , config] = api.post.mock.calls[0];
    const expected = createHash("sha256").update(`${CYCLE_ID}::snap-a`).digest("hex");
    expect(config.headers["Idempotency-Key"]).toBe(expected);
  });

  it("nothing new since the last analysis → an INFO with its date, never red", async () => {
    api.post.mockResolvedValue(info("DEAL_HEALTH_NO_NEW_SOURCES", "2026-11-18T10:00:00+00:00"));
    renderPage();
    await clickReRun();

    await waitFor(() => expect(displayInfoSnackbar).toHaveBeenCalledTimes(1));
    expect(displayInfoSnackbar).toHaveBeenCalledWith(
      DEAL_HEALTH_RUN_LABELS.NOTHING_NEW("Nov 18, 2026"),
    );
    expect(DEAL_HEALTH_RUN_LABELS.NOTHING_NEW("Nov 18, 2026")).toBe(
      "Nothing new since the last analysis (Nov 18, 2026)",
    );
    noRedNorWarning();
    // The run is over: the triggers are active again.
    await waitFor(() => expect(screen.getAllByRole("button").every((b) => !b.disabled)).toBe(true));
  });

  it("the server's CYCLE_CLOSED code is an INFO too (the server stays the guard)", async () => {
    api.post.mockResolvedValue(info("DEAL_HEALTH_CYCLE_CLOSED", "2026-11-18T10:00:00+00:00"));
    renderPage();
    await clickReRun();

    await waitFor(() => expect(displayInfoSnackbar).toHaveBeenCalledTimes(1));
    expect(displayInfoSnackbar).toHaveBeenCalledWith(DEAL_HEALTH_RUN_LABELS.CLOSED);
    noRedNorWarning();
  });

  // 6c (PO): ON_HOLD is a pause, not a closure — the deal health runs there.
  it("an ON_HOLD cycle: the triggers stay active, no « closed » info", async () => {
    renderPage({ outcome: "ON_HOLD" });
    await screen.findByText("Reading A");

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
    expect(buttons.every((b) => !b.disabled)).toBe(true);
    expect(isDealHealthClosed({ outcome: "ON_HOLD" })).toBe(false);
    expect(DEAL_HEALTH_CLOSED_OUTCOMES).toEqual(["WON", "LOST", "NOT_QUALIFIED"]);
  });

  it("a closed cycle: every trigger disabled, an info on hover, the diagnostic still shown", async () => {
    renderPage({ outcome: "LOST" });
    await screen.findByText("Reading A");                 // the last diagnostic stays readable

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
    expect(buttons.every((b) => b.disabled)).toBe(true);

    fireEvent.mouseOver(screen.getByRole("button", { name: /re-run/i }).parentElement);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(DEAL_HEALTH_RUN_LABELS.CLOSED);
    expect(api.post).not.toHaveBeenCalled();
  });

  it("can_run_deal_health = false: every trigger disabled, the reason on hover", async () => {
    renderPage({ can_run_deal_health: false });
    await screen.findByText("Reading A");                 // reading is unchanged

    const buttons = screen.getAllByRole("button");
    expect(buttons).toHaveLength(2);
    expect(buttons.every((b) => b.disabled)).toBe(true);

    fireEvent.mouseOver(screen.getByRole("button", { name: /re-run/i }).parentElement);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      DEAL_HEALTH_RUN_LABELS.NOT_ALLOWED,
    );
    cleanup();

    // The header's button too.
    renderPage({ can_run_deal_health: false });
    await screen.findByText("Reading A");
    // DealHealthRunButton is rendered first (renderPage).
    const [headerButton] = screen.getAllByRole("button");
    expect(headerButton).toHaveTextContent(DEAL_HEALTH_RUN_LABELS.HEADER);
    fireEvent.mouseOver(headerButton.parentElement);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(
      DEAL_HEALTH_RUN_LABELS.NOT_ALLOWED,
    );
    expect(api.post).not.toHaveBeenCalled();
  });

  it("can_run_deal_health = true: the triggers are active", async () => {
    renderPage({ can_run_deal_health: true });
    await screen.findByText("Reading A");
    expect(screen.getAllByRole("button").every((b) => !b.disabled)).toBe(true);
  });
});
