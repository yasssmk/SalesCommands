// frontend/src/__tests__/signals/useActivityAllSignals.test.js

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";

// ==============================|| MOCKS ||============================== //

const mockPainResult = {
  signals: [{ id: "p1", status: "PENDING", summary: "Pain 1" }],
  signalsLoading: false,
  signalsError: null,
  mutateSignals: vi.fn(),
};

const mockObjectiveResult = {
  signals: [{ id: "o1", status: "VALIDATED", summary: "Obj 1" }],
  signalsLoading: false,
  signalsError: null,
  mutateSignals: vi.fn(),
};

const mockImpactResult = {
  signals: [],
  signalsLoading: false,
  signalsError: null,
  mutateSignals: vi.fn(),
};

const mockTechStackResult = {
  signals: [{ id: "ts1", status: "PENDING", summary: "TS 1" }],
  signalsLoading: false,
  signalsError: null,
  mutateSignals: vi.fn(),
};

const mockBlockerResult = {
  signals: [{ id: "b1", status: "PENDING", summary: "Blocker 1" }],
  signalsLoading: false,
  signalsError: null,
  mutateSignals: vi.fn(),
};

const mockNextStepResult = {
  signals: [{ id: "ns1", status: "PENDING", suggested_title: "NS 1" }],
  signalsLoading: false,
  signalsError: null,
  mutateSignals: vi.fn(),
};

vi.mock("api/signals/signals", () => ({
  useGetSignalsByActivity: vi.fn((activityId, type) => {
    switch (type) {
      case "pain":
        return mockPainResult;
      case "objective":
        return mockObjectiveResult;
      case "impact":
        return mockImpactResult;
      case "tech-stack":
        return mockTechStackResult;
      case "blockers":
        return mockBlockerResult;
      case "next-steps":
        return mockNextStepResult;
      default:
        return { signals: [], signalsLoading: false, signalsError: null, mutateSignals: vi.fn() };
    }
  }),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import useActivityAllSignals from "hooks/useActivityAllSignals";

// ==============================|| TESTS ||============================== //

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup();
});

describe("useActivityAllSignals", () => {
  it("returns signals grouped by type", () => {
    const { result } = renderHook(() => useActivityAllSignals("act-1"));

    expect(result.current.signalsByType.pain).toHaveLength(1);
    expect(result.current.signalsByType.objective).toHaveLength(1);
    expect(result.current.signalsByType.impact).toHaveLength(0);
    expect(result.current.signalsByType["tech-stack"]).toHaveLength(1);
    expect(result.current.signalsByType.blockers).toHaveLength(1);
    expect(result.current.signalsByType["next-steps"]).toHaveLength(1);
  });

  it("returns qualificationSignals with _signalType tag", () => {
    const { result } = renderHook(() => useActivityAllSignals("act-1"));

    expect(result.current.qualificationSignals).toHaveLength(3);
    expect(result.current.qualificationSignals[0]._signalType).toBe("pain");
    expect(result.current.qualificationSignals[1]._signalType).toBe("objective");
    expect(result.current.qualificationSignals[2]._signalType).toBe("tech-stack");
  });

  it("returns blockerSignals with _signalType tag", () => {
    const { result } = renderHook(() => useActivityAllSignals("act-1"));

    expect(result.current.blockerSignals).toHaveLength(1);
    expect(result.current.blockerSignals[0]._signalType).toBe("blockers");
  });

  it("returns nextStepSignals with _signalType tag", () => {
    const { result } = renderHook(() => useActivityAllSignals("act-1"));

    expect(result.current.nextStepSignals).toHaveLength(1);
    expect(result.current.nextStepSignals[0]._signalType).toBe("next-steps");
  });

  it("returns allSignals as union of all types", () => {
    const { result } = renderHook(() => useActivityAllSignals("act-1"));

    expect(result.current.allSignals).toHaveLength(5);
  });

  it("reports loading=false when all hooks are loaded", () => {
    const { result } = renderHook(() => useActivityAllSignals("act-1"));

    expect(result.current.loading).toBe(false);
  });

  it("calls all mutateSignals on mutateAll", () => {
    const { result } = renderHook(() => useActivityAllSignals("act-1"));

    result.current.mutateAll();

    expect(mockPainResult.mutateSignals).toHaveBeenCalled();
    expect(mockObjectiveResult.mutateSignals).toHaveBeenCalled();
    expect(mockImpactResult.mutateSignals).toHaveBeenCalled();
    expect(mockTechStackResult.mutateSignals).toHaveBeenCalled();
    expect(mockBlockerResult.mutateSignals).toHaveBeenCalled();
    expect(mockNextStepResult.mutateSignals).toHaveBeenCalled();
  });
});
