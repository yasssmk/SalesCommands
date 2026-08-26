// frontend/src/__tests__/signals/useAggregatedSignals.test.js
//
// Unit test for the aggregated-signals SWR hook. Proves the hook:
//   - builds the /module-signals/all/ URL with exactly one scope key plus
//     repeated status + signal_type, ordering, page and page_size,
//   - maps the endpoint's `signal_type` onto `_signalType` (what SignalLine
//     reads) for every returned item,
//   - exposes count / pageCount from the paginated envelope,
//   - disables itself (null SWR key) when no valid scope is supplied.

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";

const swrMock = vi.fn(() => ({
  data: undefined,
  isLoading: false,
  error: null,
  isValidating: false,
  mutate: vi.fn(),
}));
vi.mock("swr", () => ({ default: (key, opts) => swrMock(key, opts) }));

// useAuth is globally mocked in vitest.setup.js → tenantId "test-tenant-id".
vi.mock("api/_swr", () => ({
  tenantKey: (url, tenantId) => (url && tenantId ? [url, tenantId] : null),
}));

import useAggregatedSignals from "api/signals/aggregatedSignals";

const ACCOUNT = "11111111-1111-4111-8111-111111111111";
const CYCLE = "22222222-2222-4222-8222-222222222222";
const ACTIVITY = "33333333-3333-4333-8333-333333333333";

function lastKeyUrl() {
  const key = swrMock.mock.calls.at(-1)[0];
  // tenantKey → [url, tenantId]
  return Array.isArray(key) ? key[0] : key;
}

beforeEach(() => {
  vi.clearAllMocks();
  swrMock.mockImplementation(() => ({
    data: undefined,
    isLoading: false,
    error: null,
    isValidating: false,
    mutate: vi.fn(),
  }));
});
afterEach(() => cleanup());

describe("useAggregatedSignals — URL building", () => {
  it("builds account scope with statuses, signal_type, ordering, page, page_size", () => {
    renderHook(() =>
      useAggregatedSignals({
        accountId: ACCOUNT,
        statuses: ["PENDING", "VALIDATED"],
        signalTypes: ["pain", "tech-stack"],
        ordering: "date-desc",
        page: 2,
        pageSize: 20,
      }),
    );

    const url = lastKeyUrl();
    expect(url).toContain("/module-signals/all/?");
    expect(url).toContain(`account_id=${ACCOUNT}`);
    expect(url).toContain("status=PENDING");
    expect(url).toContain("status=VALIDATED");
    expect(url).toContain("signal_type=pain");
    // URLSearchParams encodes the hyphen slug literally.
    expect(url).toContain("signal_type=tech-stack");
    expect(url).toContain("ordering=date-desc");
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=20");
  });

  it("appends department when set (StandardDepartment id)", () => {
    renderHook(() =>
      useAggregatedSignals({ accountId: ACCOUNT, department: 7 }),
    );
    expect(lastKeyUrl()).toContain("department=7");
  });

  it("appends contact when set (contact id)", () => {
    const CONTACT = "44444444-4444-4444-8444-444444444444";
    renderHook(() =>
      useAggregatedSignals({ accountId: ACCOUNT, contact: CONTACT }),
    );
    expect(lastKeyUrl()).toContain(`contact=${CONTACT}`);
  });

  it("appends scope when set (BUSINESS | DEPARTMENT)", () => {
    renderHook(() =>
      useAggregatedSignals({ accountId: ACCOUNT, scope: "DEPARTMENT" }),
    );
    expect(lastKeyUrl()).toContain("scope=DEPARTMENT");
  });

  it("omits department / contact / scope when not set", () => {
    renderHook(() => useAggregatedSignals({ accountId: ACCOUNT }));
    const url = lastKeyUrl();
    expect(url).not.toContain("department=");
    expect(url).not.toContain("contact=");
    expect(url).not.toContain("scope=");
  });

  it("combines type + status + department into a single query", () => {
    renderHook(() =>
      useAggregatedSignals({
        accountId: ACCOUNT,
        statuses: ["PENDING"],
        signalTypes: ["pain"],
        department: 3,
      }),
    );
    const url = lastKeyUrl();
    expect(url).toContain("signal_type=pain");
    expect(url).toContain("status=PENDING");
    expect(url).toContain("department=3");
  });

  it("uses decision_cycle_id when scoped to a cycle", () => {
    renderHook(() => useAggregatedSignals({ decisionCycleId: CYCLE }));
    const url = lastKeyUrl();
    expect(url).toContain(`decision_cycle_id=${CYCLE}`);
    expect(url).not.toContain("account_id=");
  });

  it("uses activity_id when scoped to an activity", () => {
    renderHook(() => useAggregatedSignals({ activityId: ACTIVITY }));
    const url = lastKeyUrl();
    expect(url).toContain(`activity_id=${ACTIVITY}`);
  });

  it("disables the hook (null SWR key) when no valid scope is given", () => {
    renderHook(() => useAggregatedSignals({ accountId: "not-a-uuid" }));
    expect(swrMock.mock.calls.at(-1)[0]).toBeNull();
  });
});

describe("useAggregatedSignals — response shaping", () => {
  it("tags every item with _signalType copied from signal_type", () => {
    swrMock.mockImplementation(() => ({
      data: {
        results: [
          { id: "a", status: "PENDING", signal_type: "pain" },
          { id: "b", status: "VALIDATED", signal_type: "tech-stack" },
          { id: "c", status: "REJECTED", signal_type: "blockers" },
        ],
        count: 42,
        next: "http://x/?page=3",
        previous: null,
      },
      isLoading: false,
      error: null,
      isValidating: false,
      mutate: vi.fn(),
    }));

    const { result } = renderHook(() =>
      useAggregatedSignals({ accountId: ACCOUNT, pageSize: 20 }),
    );

    expect(result.current.signals.map((s) => s._signalType)).toEqual([
      "pain",
      "tech-stack",
      "blockers",
    ]);
    // Original signal_type is preserved alongside the mapped field.
    expect(result.current.signals[0].signal_type).toBe("pain");
    expect(result.current.count).toBe(42);
    expect(result.current.pageCount).toBe(Math.ceil(42 / 20)); // 3
    expect(result.current.next).toBe("http://x/?page=3");
  });

  it("reads the envelope whether nested under data or at the top level", () => {
    swrMock.mockImplementation(() => ({
      data: { data: { results: [{ id: "z", signal_type: "objective" }], count: 1 } },
      isLoading: false,
      error: null,
      isValidating: false,
      mutate: vi.fn(),
    }));

    const { result } = renderHook(() =>
      useAggregatedSignals({ accountId: ACCOUNT }),
    );
    expect(result.current.signals[0]._signalType).toBe("objective");
    expect(result.current.count).toBe(1);
  });
});
