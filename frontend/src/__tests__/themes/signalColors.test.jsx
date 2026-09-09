// frontend/src/__tests__/themes/signalColors.test.jsx
//
// SIG-1 — proves the DEDICATED signal-type colour group is attached to the
// aphoriQ namespace with one distinct, legible colour per signal type.
//
// Unlike the rest of aphoriQ (palette references that invert light<->dark),
// this group is a DELIBERATE exception: signal-type colours are semantic type
// identities, so they are FIXED hex values, identical in light and dark, the
// single source of truth for the 9 types. See themes/aphoriq.js.

import { describe, it, expect, vi } from "vitest";

// themes/palette pulls the preset chain → config/theme-config.js calls
// next/font/google at import time (not loadable under vitest); mock it (same
// pattern as themes/aphoriq.test.jsx).
vi.mock("next/font/google", () => ({
  Public_Sans: () => ({ className: "mock", style: { fontFamily: "mock" } }),
}));

import Palette from "themes/palette";
import AphoriQ from "themes/aphoriq";
import { ThemeMode } from "config";

// The 9 signal-type slugs — the API source of truth (api/signals/signals.js:30-40).
const SIGNAL_SLUGS = [
  "pain",
  "objective",
  "impact",
  "tech-stack",
  "blockers",
  "next-steps",
  "people",
  "constraints",
  "competitors",
];

describe("aphoriQ.signalColors — dedicated signal-type colour group (SIG-1)", () => {
  const light = AphoriQ(Palette(ThemeMode.LIGHT, "theme3"));

  it("exposes exactly one colour for each of the 9 signal types", () => {
    expect(light.signalColors).toBeTruthy();
    expect([...Object.keys(light.signalColors)].sort()).toEqual(
      [...SIGNAL_SLUGS].sort(),
    );
  });

  it("every type colour is a non-empty string", () => {
    SIGNAL_SLUGS.forEach((slug) => {
      expect(typeof light.signalColors[slug]).toBe("string");
      expect(light.signalColors[slug].length).toBeGreaterThan(0);
    });
  });

  it("the 9 colours are DISTINCT (no two types share a colour)", () => {
    const values = SIGNAL_SLUGS.map((s) => light.signalColors[s].toLowerCase());
    expect(new Set(values).size).toBe(SIGNAL_SLUGS.length);
  });

  it("is FIXED — identical in light and dark mode (documented exception)", () => {
    const dark = AphoriQ(Palette(ThemeMode.DARK, "theme3"));
    SIGNAL_SLUGS.forEach((slug) => {
      expect(dark.signalColors[slug]).toBe(light.signalColors[slug]);
    });
  });
});
