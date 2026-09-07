// frontend/src/__tests__/components/display/HaloBox.test.jsx
//
// SIG-HALO-arch — HaloBox is a GENERIC, project-reusable state-halo primitive:
// given a customShadows colour role key it wraps its children in that soft glow;
// a falsy colour → no halo. Not signal-specific — any screen can reuse it.

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
import HaloBox from "components/display/HaloBox";

function ShadowProbe() {
  const theme = useTheme();
  return (
    <div
      data-testid="cs"
      data-warning={theme.customShadows.warning}
      data-error={theme.customShadows.error}
    />
  );
}

function renderHalo(props) {
  return render(
    <ThemeCustomization>
      <ShadowProbe />
      <HaloBox {...props}>
        <div>content</div>
      </HaloBox>
    </ThemeCustomization>,
  );
}

describe("HaloBox — generic state-halo primitive", () => {
  it("applies the given colour role's glow token", () => {
    renderHalo({ color: "warning" });
    const warning = screen.getByTestId("cs").getAttribute("data-warning");
    expect(screen.getByTestId("halo-box")).toHaveStyle({ boxShadow: warning });
    expect(screen.getByText("content")).toBeInTheDocument();
  });

  it("is reusable for ANY role — e.g. error (not signal-specific)", () => {
    renderHalo({ color: "error" });
    const error = screen.getByTestId("cs").getAttribute("data-error");
    expect(screen.getByTestId("halo-box")).toHaveStyle({ boxShadow: error });
  });

  it("no colour → no halo (box-shadow none)", () => {
    renderHalo({ color: null });
    expect(screen.getByTestId("halo-box")).toHaveStyle({ boxShadow: "none" });
  });

  it("lets a caller override the test id (so wrappers can name it)", () => {
    render(
      <ThemeCustomization>
        <HaloBox color="warning" data-testid="custom-halo">
          <div>x</div>
        </HaloBox>
      </ThemeCustomization>,
    );
    expect(screen.getByTestId("custom-halo")).toBeInTheDocument();
  });
});
