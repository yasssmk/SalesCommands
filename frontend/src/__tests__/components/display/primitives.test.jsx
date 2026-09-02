// frontend/src/__tests__/components/display/primitives.test.jsx
//
// B1a — proves the two themed primitives (EmptyState, Surface) render and
// consume theme.aphoriQ.* (no hardcoded hex/px). They render under the REAL
// ThemeCustomization so the emitted CSS is produced from the live theme.

import { render, screen, cleanup } from "@testing-library/react";
import { useTheme } from "@mui/material/styles";
import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => cleanup());

// theme-config.js calls next/font/google at import time — not loadable under vitest.
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));
// emotionCache uses next/navigation's useServerInsertedHTML (unmocked) — stub to passthrough.
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import EmptyState from "components/display/EmptyState";
import Surface from "components/display/Surface";
import BulbOutlined from "@ant-design/icons/BulbOutlined";

// Exposes the live aphoriQ token values so assertions are mode-agnostic.
function TokenProbe() {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <div
      data-testid="tokens"
      data-radius-lg={String(aq.radius.lg)}
      data-hairline={String(aq.border.width.hairline)}
      data-level2={aq.surface.level2}
      data-muted={aq.text.muted}
    />
  );
}

function allStyleText() {
  return Array.from(document.querySelectorAll("style"))
    .map((s) => s.textContent || "")
    .join("");
}

describe("EmptyState (B1a)", () => {
  it("renders title, description and action; uses the muted token", () => {
    render(
      <ThemeCustomization>
        <TokenProbe />
        <EmptyState
          icon={BulbOutlined}
          title="Nothing here yet"
          description="Add the first item to get started."
          action={<button type="button">Do it</button>}
        />
      </ThemeCustomization>,
    );

    expect(screen.getByText("Nothing here yet")).toBeInTheDocument();
    expect(
      screen.getByText("Add the first item to get started."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Do it" })).toBeInTheDocument();

    // muted token from aphoriQ must appear in the emitted CSS (not a raw hex).
    const muted = screen.getByTestId("tokens").getAttribute("data-muted");
    expect(allStyleText()).toContain(muted);
  });
});

describe("Surface (B1a)", () => {
  it("applies aphoriQ surface.level2 + radius.lg + border.hairline", () => {
    render(
      <ThemeCustomization>
        <TokenProbe />
        <Surface>
          <span>content</span>
        </Surface>
      </ThemeCustomization>,
    );

    expect(screen.getByText("content")).toBeInTheDocument();

    const t = screen.getByTestId("tokens");
    const radiusLg = t.getAttribute("data-radius-lg"); // 12
    const hairline = t.getAttribute("data-hairline"); // 0.5
    const level2 = t.getAttribute("data-level2");

    const css = allStyleText();
    // radius.lg (12px) and border.hairline (0.5px) are NOT MUI defaults —
    // their presence uniquely proves aphoriQ consumption.
    expect(css).toContain(`${radiusLg}px`);
    expect(css).toContain(`${hairline}px`);
    // surface.level2 (palette reference) applied as the background.
    expect(css).toContain(level2);
  });
});
