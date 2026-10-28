// frontend/src/__tests__/nextSteps/ExtractionRevalidatesBands.test.jsx
//
// Sprint Next steps 5.10 — after a successful extraction, the data of the
// bands is revalidated: runActivityExtraction (api/aiPipelines/
// activityExtraction.js) revalidates SWR keys by prefix (SIGNAL_LIST_PREFIXES,
// real api/_swr). Real path: the REAL data hooks are mounted in the global SWR
// cache, the extraction runs, the hooks must fetch again.
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
import { useGetSignalsByActivity } from "api/signals/signals";

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
  it("a per-type next steps list (/module-signals/next-steps/) fetches again", async () => {
    const activityId = "22222222-2222-4222-8222-222222222222";
    mount(<NextStepsList activityId={activityId} />);
    await waitFor(() => expect(fetchesOf("/module-signals/next-steps/")).toBe(1));

    await runActivityExtraction(activityId, TRANSCRIPT);

    await waitFor(() => expect(fetchesOf("/module-signals/next-steps/")).toBe(2));
  });
});
