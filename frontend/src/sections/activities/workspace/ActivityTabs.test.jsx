// frontend/src/sections/activities/workspace/ActivityTabs.test.jsx
//
// Unit tests for getVisibleTabs — the conditional tab visibility helper.
//
// PO decision (1-bis): the "Next Steps" TAB is ALWAYS visible (campaign
// AND decision-cycle contexts) — a rep can always create a next step
// manually. The DC-only rule applies to the AI SUGGESTIONS block INSIDE
// the tab, not to the tab itself (see ActivityNextStepsTab tests).

import { describe, it, expect } from "vitest";

import { getVisibleTabs, ACTIVITY_TABS } from "./ActivityTabs";

const idsOf = (tabs) => tabs.map((t) => t.id);

describe("getVisibleTabs — Next Steps tab is always visible", () => {
  it("SHOWS 'next-steps' for a MEETING activity", () => {
    expect(idsOf(getVisibleTabs("MEETING"))).toContain("next-steps");
  });

  it("SHOWS 'next-steps' for an EMAIL activity (campaign-style)", () => {
    expect(idsOf(getVisibleTabs("EMAIL"))).toContain("next-steps");
  });
});

describe("getVisibleTabs — existing preparation eligibility (non-regression)", () => {
  it("keeps 'preparation' for CALL/MEETING/DEMO", () => {
    expect(idsOf(getVisibleTabs("CALL"))).toContain("preparation");
  });

  it("drops 'preparation' for non-eligible types (e.g. EMAIL)", () => {
    expect(idsOf(getVisibleTabs("EMAIL"))).not.toContain("preparation");
  });

  it("always exposes the unconditional tabs", () => {
    const ids = idsOf(getVisibleTabs("EMAIL"));
    expect(ids).toEqual(expect.arrayContaining(["overview", "notes", "signals"]));
  });

  it("ACTIVITY_TABS declares the next-steps tab", () => {
    expect(ACTIVITY_TABS.map((t) => t.id)).toContain("next-steps");
  });
});
