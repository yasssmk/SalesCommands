// frontend/src/__tests__/utils/signalTypes.test.js
//
// SIG-1 — the unified signal-TYPE source of truth: label + colorKey per type,
// with resolver helpers. Mirrors utils/outcomes.js. Slugs align 1:1 with the
// API source of truth (api/signals/signals.js:30-40); colours are NOT stored
// here — colorKey points into theme.aphoriQ.signalColors.

import { describe, it, expect } from "vitest";
import {
  SIGNAL_TYPE_META,
  getSignalTypeLabel,
  getSignalTypeColor,
} from "utils/signalTypes";

// The 9 slugs + their expected V0 English labels (PO-validated).
const EXPECTED_LABELS = {
  pain: "Pain",
  objective: "Objective",
  impact: "Impact",
  "tech-stack": "Tech Stack",
  blockers: "Objection",
  "next-steps": "Next step",
  people: "People",
  constraints: "Constraint",
  competitors: "Competitor",
};

const SIGNAL_SLUGS = Object.keys(EXPECTED_LABELS);

describe("signalTypes — unified meta for the 9 signal types (SIG-1)", () => {
  it("SIGNAL_TYPE_META covers exactly the 9 signal-type slugs", () => {
    expect([...Object.keys(SIGNAL_TYPE_META)].sort()).toEqual(
      [...SIGNAL_SLUGS].sort(),
    );
  });

  it("every type has a label and a colorKey", () => {
    SIGNAL_SLUGS.forEach((slug) => {
      expect(typeof SIGNAL_TYPE_META[slug].label).toBe("string");
      expect(SIGNAL_TYPE_META[slug].label.length).toBeGreaterThan(0);
      expect(typeof SIGNAL_TYPE_META[slug].colorKey).toBe("string");
      expect(SIGNAL_TYPE_META[slug].colorKey.length).toBeGreaterThan(0);
    });
  });

  it("getSignalTypeLabel returns the V0 label for each type", () => {
    SIGNAL_SLUGS.forEach((slug) => {
      expect(getSignalTypeLabel(slug)).toBe(EXPECTED_LABELS[slug]);
    });
  });

  it("getSignalTypeLabel returns null for an unknown type", () => {
    expect(getSignalTypeLabel("nope")).toBeNull();
    expect(getSignalTypeLabel(undefined)).toBeNull();
  });

  it("getSignalTypeColor resolves the dedicated colour from the theme group", () => {
    const theme = {
      aphoriQ: {
        signalColors: {
          pain: "#111111",
          objective: "#222222",
          impact: "#333333",
          "tech-stack": "#444444",
          blockers: "#555555",
          "next-steps": "#666666",
          people: "#777777",
          constraints: "#888888",
          competitors: "#999999",
        },
      },
    };
    SIGNAL_SLUGS.forEach((slug) => {
      const colorKey = SIGNAL_TYPE_META[slug].colorKey;
      expect(getSignalTypeColor(slug, theme)).toBe(
        theme.aphoriQ.signalColors[colorKey],
      );
    });
  });

  it("getSignalTypeColor returns null for an unknown type or missing theme group", () => {
    expect(getSignalTypeColor("nope", { aphoriQ: { signalColors: {} } })).toBeNull();
    expect(getSignalTypeColor("pain", {})).toBeNull();
    expect(getSignalTypeColor("pain", undefined)).toBeNull();
  });
});
