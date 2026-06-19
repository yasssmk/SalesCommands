"use client";

// ==============================|| ELIGIBILITY ||============================== //

const PREP_ELIGIBLE_TYPES = new Set(['CALL', 'MEETING', 'DEMO']);

// ==============================|| TAB CONFIGURATION ||============================== //

export const ACTIVITY_TABS = [
  { id: "overview", label: "Overview" },
  { id: "preparation", label: "Preparation", eligibleTypes: PREP_ELIGIBLE_TYPES },
  { id: "notes", label: "Notes" },
  { id: "signals", label: "Signals" },
  { id: "next-steps", label: "Next Steps" },
];

export const DEFAULT_TAB = "overview";

export function getVisibleTabs(activityType) {
  return ACTIVITY_TABS.filter(
    (tab) => !tab.eligibleTypes || tab.eligibleTypes.has(activityType),
  );
}
