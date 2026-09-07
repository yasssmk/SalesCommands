// frontend/src/__tests__/components/signals/SignalsHaloBox.test.jsx
//
// SIG-HALO — the coloured halo around the Activity Signals band.
//   - >=1 pending signal  → warning (amber) glow
//   - 0 pending, >=1 total → primary glow (all processed)
//   - 0 total              → no halo
// The glow is a themed customShadows token (no hex/px literal), applied on a
// wrapper Box so it shows even when the band is collapsed.

import { render, screen, cleanup } from "@testing-library/react";
import { useTheme } from "@mui/material/styles";
import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => cleanup());

vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import SignalsHaloBox, { getSignalsHalo } from "components/signals/SignalsHaloBox";

// Exposes the live customShadows glow tokens so assertions use the real theme.
function ShadowProbe() {
  const theme = useTheme();
  return (
    <div
      data-testid="cs"
      data-warning={theme.customShadows.warning}
      data-primary={theme.customShadows.primary}
    />
  );
}

function renderBox(props) {
  return render(
    <ThemeCustomization>
      <ShadowProbe />
      <SignalsHaloBox {...props}>
        <div>band body</div>
      </SignalsHaloBox>
    </ThemeCustomization>,
  );
}

describe("getSignalsHalo — predicate", () => {
  it(">=1 pending → 'warning'", () => {
    expect(getSignalsHalo({ pendingCount: 3, totalSignals: 5 })).toBe("warning");
    expect(getSignalsHalo({ pendingCount: 1, totalSignals: 1 })).toBe("warning");
  });

  it("0 pending & >=1 total → 'primary'", () => {
    expect(getSignalsHalo({ pendingCount: 0, totalSignals: 4 })).toBe("primary");
  });

  it("0 total → null (no halo)", () => {
    expect(getSignalsHalo({ pendingCount: 0, totalSignals: 0 })).toBeNull();
    expect(getSignalsHalo({})).toBeNull();
  });
});

describe("SignalsHaloBox — rendering", () => {
  it("applies the WARNING glow token when there is >=1 pending", () => {
    renderBox({ pendingCount: 2, totalSignals: 5 });
    const warning = screen.getByTestId("cs").getAttribute("data-warning");
    expect(screen.getByTestId("signals-halo")).toHaveStyle({ boxShadow: warning });
    // The band body is wrapped and always rendered (halo shows even collapsed).
    expect(screen.getByText("band body")).toBeInTheDocument();
  });

  it("applies the PRIMARY glow token when all signals are processed (0 pending)", () => {
    renderBox({ pendingCount: 0, totalSignals: 4 });
    const primary = screen.getByTestId("cs").getAttribute("data-primary");
    expect(screen.getByTestId("signals-halo")).toHaveStyle({ boxShadow: primary });
  });

  it("applies NO halo (box-shadow none) when there are no signals", () => {
    renderBox({ pendingCount: 0, totalSignals: 0 });
    expect(screen.getByTestId("signals-halo")).toHaveStyle({ boxShadow: "none" });
  });
});
