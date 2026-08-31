// frontend/src/__tests__/signals/competitorFront.test.jsx
//
// Sub-step 6.2: CompetitorSignal on the front.
//   * SignalLine renders a competitor row (flat slug 'competitors') with its
//     summary and a MUTED type label — NO decorative icon (deliberate
//     divergence from the Constraint clone, which carries an icon chip), and
//     NO scope chip (competitor has neither scope_level nor target_department).
//   * useDCAllSignals fetches + tags the competitor type (slug 'competitors').

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { renderHook } from "@testing-library/react";

// ==============================|| MOCKS (DC hook) ||============================== //

const _mk = (signals) => ({
  signals,
  signalsLoading: false,
  signalsError: null,
  mutateSignals: vi.fn(),
});

vi.mock("api/signals/signals", () => ({
  useGetSignalsByAccount: vi.fn((accountId, type) => {
    if (type === "competitors") {
      return _mk([
        { id: "cmp1", status: "VALIDATED", competitor_name: "Salesforce", summary: "Weighing Salesforce" },
      ]);
    }
    return _mk([]);
  }),
}));

// ==============================|| IMPORTS (after mocks) ||============================== //

import SignalLine from "components/signals/SignalLine";
import useDCAllSignals from "hooks/useDCAllSignals";

afterEach(() => cleanup());
beforeEach(() => vi.clearAllMocks());

const COMPETITOR = {
  id: "cmp1",
  status: "VALIDATED",
  competitor_name: "Salesforce",
  summary: "Prospect is weighing Salesforce against us",
  created_at: "2026-05-01T10:00:00Z",
  source_context: { contacts: [] },
};

describe("SignalLine — competitor row (muted type, no scope)", () => {
  it("renders the summary and a 'Competitor' type label", () => {
    render(<SignalLine signal={COMPETITOR} signalType="competitors" />);
    expect(
      screen.getByText("Prospect is weighing Salesforce against us"),
    ).toBeInTheDocument();
    expect(screen.getByText("Competitor")).toBeInTheDocument();
  });

  it("shows the type label as a MUTED chip with NO decorative icon", () => {
    render(<SignalLine signal={COMPETITOR} signalType="competitors" />);
    const label = screen.getByText("Competitor");
    const chip = label.closest(".MuiChip-root");
    expect(chip).not.toBeNull();
    // Divergence from Constraint: no icon element inside the chip.
    expect(chip.querySelector(".MuiChip-icon")).toBeNull();
  });

  it("renders NO scope chip (competitor has no scope / department)", () => {
    render(<SignalLine signal={COMPETITOR} signalType="competitors" />);
    expect(screen.queryByText("Business")).not.toBeInTheDocument();
    expect(screen.queryByText(/Department ·/)).not.toBeInTheDocument();
  });
});

describe("useDCAllSignals — competitor type is fetched and tagged", () => {
  it("returns competitorSignals tagged with _signalType 'competitors'", () => {
    const { result } = renderHook(() => useDCAllSignals("acc-1", "dc-1"));

    expect(result.current.signalsByType.competitors).toHaveLength(1);
    expect(result.current.competitorSignals).toHaveLength(1);
    expect(result.current.competitorSignals[0]._signalType).toBe("competitors");
    // And it flows into the merged list.
    expect(
      result.current.allSignals.some((s) => s._signalType === "competitors"),
    ).toBe(true);
  });
});
