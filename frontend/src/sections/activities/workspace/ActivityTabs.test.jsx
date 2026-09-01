// frontend/src/sections/activities/workspace/ActivityTabs.test.jsx
//
// Unit tests for getVisibleTabs — the conditional tab visibility helper.
//
// PO decision: the "Next Steps" tab is a DC-ONLY feature. It must be
// HIDDEN when the activity has no decision_cycle (campaign context) and
// VISIBLE when the activity has one. Same rule as the backend guard
// (next step allowed iff decision_cycle is set).

import { describe, it, expect } from "vitest";

import { getVisibleTabs, ACTIVITY_TABS } from "./ActivityTabs";

const idsOf = (tabs) => tabs.map((t) => t.id);

describe("getVisibleTabs — Next Steps DC-only visibility", () => {
  it("HIDES 'next-steps' when the activity has no decision cycle", () => {
    const visible = getVisibleTabs("MEETING", false);
    expect(idsOf(visible)).not.toContain("next-steps");
  });

  it("SHOWS 'next-steps' when the activity has a decision cycle", () => {
    const visible = getVisibleTabs("MEETING", true);
    expect(idsOf(visible)).toContain("next-steps");
  });
});

describe("getVisibleTabs — existing preparation eligibility (non-regression)", () => {
  it("keeps 'preparation' for CALL/MEETING/DEMO", () => {
    expect(idsOf(getVisibleTabs("CALL", true))).toContain("preparation");
  });

  it("drops 'preparation' for non-eligible types (e.g. EMAIL)", () => {
    expect(idsOf(getVisibleTabs("EMAIL", true))).not.toContain("preparation");
  });

  it("always exposes the unconditional tabs", () => {
    const ids = idsOf(getVisibleTabs("EMAIL", true));
    expect(ids).toEqual(expect.arrayContaining(["overview", "notes", "signals"]));
  });

  it("ACTIVITY_TABS still declares the next-steps tab", () => {
    expect(ACTIVITY_TABS.map((t) => t.id)).toContain("next-steps");
  });
});
