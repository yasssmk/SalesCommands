// frontend/src/__tests__/nextSteps/ExtractionRevalidatesBands.test.jsx
//
// Sprint Next steps 5.10 — after a successful extraction, the data of the
// bands is revalidated: runActivityExtraction (api/aiPipelines/
// activityExtraction.js) revalidates SWR keys by prefix (SIGNAL_LIST_PREFIXES,
// real api/_swr). Real path: the REAL data hooks are mounted in the global SWR
// cache, the extraction runs, the hooks must fetch again.
//   * the Next steps band (and the Signals band) read the aggregated endpoint
//     /module-signals/all/ (useAggregatedSignals, NEXT_STEPS_BAND_QUERY) —
//     never revalidated before 5.10;
//   * a per-type next steps list reads /module-signals/next-steps/ — the list
//     carried the SINGULAR "/module-signals/next-step/", which matches nothing.

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";

vi.mock("utils/axiosClient", () => ({ api: { post: vi.fn(), get: vi.fn() } }));
vi.mock("utils/pollOperationStatus", () => ({ pollOperationStatus: vi.fn() }));
vi.mock("hooks/useAuth", () => ({
  useAuth: () => ({ tenantId: "t-1", user: { id: "u-1" } }),
  default: () => ({ tenantId: "t-1", user: { id: "u-1" } }),
}));

import { api } from "utils/axiosClient";
import { runActivityExtraction } from "api/aiPipelines/activityExtraction";
import useAggregatedSignals from "api/signals/aggregatedSignals";
import { useGetSignalsByActivity } from "api/signals/signals";
import { NEXT_STEPS_BAND_QUERY } from "utils/nextStepsBand";

const TRANSCRIPT = "A".repeat(100);
const SUCCESS = { success: true, data: { data: { status: "SUCCESS" } } };

// The fetcher counts the calls per URL (key = [url, tenantId]).
let calls;
const fetcher = (key) => {
  const url = Array.isArray(key) ? key[0] : key;
  calls.push(url);
  return Promise.resolve({ data: { results: [], count: 0 } });
};
const fetchesOf = (prefix) => calls.filter((u) => u.startsWith(prefix)).length;

function Band({ activityId }) {
  useAggregatedSignals({ activityId, ...NEXT_STEPS_BAND_QUERY });
  return null;
}

function SignalsList({ activityId, signalType }) {
  useGetSignalsByActivity(activityId, signalType);
  return null;
}

function NextStepsList({ activityId }) {
  useGetSignalsByActivity(activityId, "next-steps");
  return null;
}

const mount = (ui) => render(<SWRConfig value={{ fetcher, dedupingInterval: 0 }}>{ui}</SWRConfig>);

beforeEach(() => {
  calls = [];
  api.post.mockResolvedValue(SUCCESS);
});

describe("a successful extraction revalidates the bands' data (5.10)", () => {
  it("the Next steps band (aggregated /module-signals/all/) fetches again", async () => {
    const activityId = "11111111-1111-4111-8111-111111111111";
    mount(<Band activityId={activityId} />);
    await waitFor(() => expect(fetchesOf("/module-signals/all/")).toBe(1));

    const result = await runActivityExtraction(activityId, TRANSCRIPT);
    expect(result.success).toBe(true);

    await waitFor(() => expect(fetchesOf("/module-signals/all/")).toBe(2));
  });

  it("a per-type next steps list (/module-signals/next-steps/) fetches again", async () => {
    const activityId = "22222222-2222-4222-8222-222222222222";
    mount(<NextStepsList activityId={activityId} />);
    await waitFor(() => expect(fetchesOf("/module-signals/next-steps/")).toBe(1));

    await runActivityExtraction(activityId, TRANSCRIPT);

    await waitFor(() => expect(fetchesOf("/module-signals/next-steps/")).toBe(2));
  });

  // 5.10b (1) — the list is derived from the endpoint map: the blockers list
  // (route blockers/, the list carried the singular "blocker/") and the types
  // that were missing (people, constraints, competitors) are revalidated too.
  it.each(["blockers", "people", "constraints", "competitors"])(
    "a per-type %s list fetches again",
    async (signalType) => {
      const activityId = `33333333-3333-4333-8333-${String(signalType.length).padStart(12, "0")}`;
      const prefix = `/module-signals/${signalType}/`;
      mount(<SignalsList activityId={activityId} signalType={signalType} />);
      await waitFor(() => expect(fetchesOf(prefix)).toBe(1));

      await runActivityExtraction(activityId, TRANSCRIPT);

      await waitFor(() => expect(fetchesOf(prefix)).toBe(2));
    },
  );
});

