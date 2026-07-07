// frontend/src/__tests__/api/aiPipelines/dealHealth.test.js
//
// Covers pollForNewSnapshot: the client-timeout recovery path for deal
// health. It must resolve as soon as a snapshot newer than the baseline
// appears, ignore a stale (unchanged) snapshot, and give up after the
// configured number of attempts.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ==============================|| MOCKS ||============================== //

const mockGet = vi.fn();
const mockRevalidateMultiple = vi.fn();

vi.mock("utils/axiosClient", () => ({
  api: {
    get: (...args) => mockGet(...args),
  },
}));

vi.mock("api/_swr", () => ({
  tenantKey: (url) => url,
  revalidateMultiple: (...args) => mockRevalidateMultiple(...args),
}));

vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ tenantId: "t1" }),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import { pollForNewSnapshot } from "api/aiPipelines/dealHealth";

const CYCLE_ID = "11111111-1111-4111-8111-111111111111";
const ok = (snapshot) => ({ success: true, data: { data: snapshot } });

// Run all pending timers between awaited steps so the internal setTimeout
// delays resolve without real waiting.
const flush = async () => {
  for (let i = 0; i < 10; i += 1) {
    await Promise.resolve();
    vi.advanceTimersByTime(4000);
  }
};

describe("pollForNewSnapshot", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockGet.mockReset();
    mockRevalidateMultiple.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolves with the snapshot once a newer one appears", async () => {
    mockGet
      .mockResolvedValueOnce(ok({ id: "old" })) // unchanged — keep polling
      .mockResolvedValueOnce(ok({ id: "new" })); // new — resolve

    const p = pollForNewSnapshot(CYCLE_ID, "old", {
      intervalMs: 4000,
      maxAttempts: 5,
    });
    await flush();
    const result = await p;

    expect(result).toEqual({ success: true, data: { id: "new" } });
    expect(mockRevalidateMultiple).toHaveBeenCalledTimes(1);
  });

  it("gives up after maxAttempts when no new snapshot appears", async () => {
    mockGet.mockResolvedValue(ok({ id: "old" }));

    const p = pollForNewSnapshot(CYCLE_ID, "old", {
      intervalMs: 4000,
      maxAttempts: 3,
    });
    await flush();
    const result = await p;

    expect(result).toEqual({ success: false, timedOut: true });
    expect(mockGet).toHaveBeenCalledTimes(3);
    expect(mockRevalidateMultiple).not.toHaveBeenCalled();
  });

  it("treats a first-ever snapshot (baseline null) as new", async () => {
    mockGet.mockResolvedValueOnce(ok({ id: "first" }));

    const p = pollForNewSnapshot(CYCLE_ID, null, {
      intervalMs: 4000,
      maxAttempts: 5,
    });
    await flush();
    const result = await p;

    expect(result).toEqual({ success: true, data: { id: "first" } });
  });

  it("rejects an invalid cycle id without polling", async () => {
    const result = await pollForNewSnapshot("not-a-uuid", null);
    expect(result.success).toBe(false);
    expect(mockGet).not.toHaveBeenCalled();
  });
});
