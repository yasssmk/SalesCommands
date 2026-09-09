// frontend/src/__tests__/components/signals/SignalsHaloBox.test.jsx
//
// SIG-HALO — the Activity Signals band halo. SignalsHaloBox is the thin
// signal-specific adapter: it derives the colour from the signal counts (via the
// utils/signalsHalo constants) and renders the generic HaloBox primitive.
//   - >=1 pending signal  → warning (amber) glow
//   - 0 pending, >=1 total → primary glow (all processed)
//   - 0 total              → no glow

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
import SignalsHaloBox from "components/signals/SignalsHaloBox";

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

describe("SignalsHaloBox — signal adapter over HaloBox", () => {
  it("applies the WARNING glow when there is >=1 pending", () => {
    renderBox({ pendingCount: 2, totalSignals: 5 });
    const warning = screen.getByTestId("cs").getAttribute("data-warning");
    expect(screen.getByTestId("signals-halo")).toHaveStyle({ boxShadow: warning });
    // The band body is wrapped and always rendered (halo shows even collapsed).
    expect(screen.getByText("band body")).toBeInTheDocument();
  });

  it("applies the PRIMARY glow when all signals are processed (0 pending)", () => {
    renderBox({ pendingCount: 0, totalSignals: 4 });
    const primary = screen.getByTestId("cs").getAttribute("data-primary");
    expect(screen.getByTestId("signals-halo")).toHaveStyle({ boxShadow: primary });
  });

  it("applies NO halo (box-shadow none) when there are no signals", () => {
    renderBox({ pendingCount: 0, totalSignals: 0 });
    expect(screen.getByTestId("signals-halo")).toHaveStyle({ boxShadow: "none" });
  });
});
