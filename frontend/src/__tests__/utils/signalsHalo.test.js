// frontend/src/__tests__/utils/signalsHalo.test.js
//
// SIG-HALO-arch — the signal-halo colour mapping + thresholds live as CONSTANTS
// (tunable in one place), and getSignalsHaloColor derives the colour FROM them.

import { describe, it, expect } from "vitest";
import {
  SIGNALS_HALO_COLORS,
  SIGNALS_HALO_THRESHOLDS,
  getSignalsHaloColor,
} from "utils/signalsHalo";

describe("signalsHalo — constants", () => {
  it("exposes the state→colour mapping as constants (customShadows/palette roles)", () => {
    expect(SIGNALS_HALO_COLORS.pending).toBe("warning");
    expect(SIGNALS_HALO_COLORS.done).toBe("primary");
  });

  it("exposes the thresholds as constants", () => {
    expect(SIGNALS_HALO_THRESHOLDS.pending).toBe(1);
    expect(SIGNALS_HALO_THRESHOLDS.total).toBe(1);
  });
});

describe("getSignalsHaloColor — derives colour from the constants", () => {
  it(">= pending threshold → the 'pending' colour", () => {
    expect(getSignalsHaloColor({ pendingCount: 2, totalSignals: 5 })).toBe(
      SIGNALS_HALO_COLORS.pending,
    );
  });

  it("0 pending & >= total threshold → the 'done' colour", () => {
    expect(getSignalsHaloColor({ pendingCount: 0, totalSignals: 3 })).toBe(
      SIGNALS_HALO_COLORS.done,
    );
  });

  it("below thresholds → null (no halo)", () => {
    expect(getSignalsHaloColor({ pendingCount: 0, totalSignals: 0 })).toBeNull();
    expect(getSignalsHaloColor({})).toBeNull();
  });
});
