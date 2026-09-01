"use client";

// ==============================|| ELIGIBILITY ||============================== //

const PREP_ELIGIBLE_TYPES = new Set(['CALL', 'MEETING', 'DEMO']);

// ==============================|| TAB CONFIGURATION ||============================== //

export const ACTIVITY_TABS = [
  { id: "overview", label: "Overview" },
  { id: "preparation", label: "Preparation", eligibleTypes: PREP_ELIGIBLE_TYPES },
  { id: "notes", label: "Notes" },
  { id: "signals", label: "Signals" },
  // Next Steps is a DC-ONLY feature: hidden in campaign context (no
  // decision_cycle). Mirrors the backend guard (next step allowed iff
  // decision_cycle is set).
  { id: "next-steps", label: "Next Steps", requiresDecisionCycle: true },
];

export const DEFAULT_TAB = "overview";

export function getVisibleTabs(activityType, hasDecisionCycle = false) {
  return ACTIVITY_TABS.filter((tab) => {
    if (tab.eligibleTypes && !tab.eligibleTypes.has(activityType)) return false;
    if (tab.requiresDecisionCycle && !hasDecisionCycle) return false;
    return true;
  });
}
