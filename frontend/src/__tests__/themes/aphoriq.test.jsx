// frontend/src/__tests__/themes/aphoriq.test.jsx
//
// B0 — proves the `aphoriQ` token namespace is attached to the app theme and
// readable by a component via useTheme(), and that its color tokens are
// palette REFERENCES that invert between light and dark (no frozen hex).

import { render, screen } from "@testing-library/react";
import { useTheme } from "@mui/material/styles";
import { describe, it, expect, vi } from "vitest";

// theme-config.js calls next/font/google at import time — not loadable under
// vitest; mock it (same pattern as the other view tests).
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

// emotionCache uses next/navigation's useServerInsertedHTML (not provided by the
// jsdom mock). Stub the cache provider to a passthrough so the REAL
// ThemeCustomization (themes/index.jsx) assembles and provides the theme.
vi.mock("themes/emotionCache", () => ({
  NextAppDirEmotionCacheProvider: ({ children }) => children,
}));

import ThemeCustomization from "themes/index";
import Palette from "themes/palette";
import AphoriQ from "themes/aphoriq";
import { ThemeMode } from "config";

// Probe: reads the live theme and serialises the aphoriQ namespace to the DOM.
function Probe() {
  const theme = useTheme();
  return (
    <div data-testid="aphoriq" data-json={JSON.stringify(theme.aphoriQ ?? null)} />
  );
}

describe("theme.aphoriQ namespace (B0)", () => {
  it("is attached to the app theme and readable via useTheme()", () => {
    render(
      <ThemeCustomization>
        <Probe />
      </ThemeCustomization>,
    );

    const raw = screen.getByTestId("aphoriq").getAttribute("data-json");
    expect(raw).not.toBe("null"); // reddens if index.jsx stops attaching aphoriQ
    const aphoriQ = JSON.parse(raw);

    // radius scale incl. the 12px MD target
    expect(aphoriQ.radius.lg).toBe(12);
    expect(aphoriQ.radius.sm).toBe(4);
    // border scale incl. the 0.5px MD target
    expect(aphoriQ.border.width.hairline).toBe(0.5);
    expect(aphoriQ.border.width.thin).toBe(1);
    expect(typeof aphoriQ.border.color).toBe("string");
    // surfaces (level2 = the fabricated 2nd surface)
    expect(aphoriQ.surface.level1).toBeTruthy();
    expect(aphoriQ.surface.level2).toBeTruthy();
    // references into the existing palette
    expect(aphoriQ.text.muted).toBeTruthy();
    expect(aphoriQ.accent).toBeTruthy();
    expect(aphoriQ.warningTint).toBeTruthy();
  });

  it("color tokens are palette references that invert light <-> dark (no frozen hex)", () => {
    const light = Palette(ThemeMode.LIGHT, "theme3");
    const dark = Palette(ThemeMode.DARK, "theme3");
    const aLight = AphoriQ(light);
    const aDark = AphoriQ(dark);

    // Each color token equals the palette token it references (per mode)…
    expect(aLight.surface.level2).toBe(light.palette.grey[50]);
    expect(aDark.surface.level2).toBe(dark.palette.grey[50]);
    expect(aLight.border.color).toBe(light.palette.divider);
    expect(aLight.text.muted).toBe(light.palette.text.secondary);
    expect(aLight.accent).toBe(light.palette.primary.main);
    expect(aLight.warningTint).toBe(light.palette.warning.lighter);

    // …and the grey-derived surface actually differs between modes (inverts).
    expect(aLight.surface.level2).not.toBe(aDark.surface.level2);

    // Non-color design scales stay mode-independent.
    expect(aLight.radius.lg).toBe(aDark.radius.lg);
    expect(aLight.border.width.hairline).toBe(aDark.border.width.hairline);
  });
});
