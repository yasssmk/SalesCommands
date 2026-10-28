// frontend/src/utils/nextStepsBand.js
//
// Sprint Next steps 5.8f — the CONSTANTS of the "Next steps" band's data, shared
// by the band (ActivityNextStepsTab: the list) and the workspace page (the band
// halo + the header "N to validate" counter, always mounted). One query shape so
// both reads are the same SWR key (deduped) and can never disagree. And (5.12 B)
// the band's PREDICATES: what it shows, and whether it is rendered at all.

import { isActivitySignalsLocked } from "utils/activitySignalsLock";

// The next steps of the activity, all 3 statuses (To validate / Validated /
// Rejected), in one page — the same aggregated query shape as the Signals band.
export const NEXT_STEPS_BAND_QUERY = {
  statuses: ["PENDING", "VALIDATED", "REJECTED"],
  signalTypes: ["next-steps"],
  ordering: "date-desc",
  page: 1,
  pageSize: 100,
};

// The suggested next steps (extracted by the AI) are a DC-only feature: in a
// campaign context (no decision_cycle) they are neither proposed nor counted.
// Mirrors the backend guard.
export function hasSuggestedNextSteps(activity) {
  return Boolean(activity?.decision_cycle);
}

// The campaign → Decision Cycle conversion block (« Successful outcome — ready
// to convert » + Start Decision Cycle) applies — the conditions it always had
// (5.12 B, moved unchanged): a campaign activity (no decision_cycle), no DC
// born from it yet, a converting outcome, the band not locked.
export const CAMPAIGN_CONVERSION_OUTCOMES = ["SUCCESSFUL", "MEETING_SCHEDULED"];

export function showsCampaignConversion(activity) {
  const isCampaignActivity = Boolean(activity?.campaign_detail) && !activity?.decision_cycle;
  const bornCycle = activity?.next_planned_step?.source === "BORN_DECISION_CYCLE";
  return (
    isCampaignActivity &&
    !bornCycle &&
    CAMPAIGN_CONVERSION_OUTCOMES.includes(activity?.outcome) &&
    !isActivitySignalsLocked(activity)
  );
}

// The band is rendered only when it has something to show (5.12 B, the
// Preparation model): the DC parts, or the conversion block.
export function hasNextStepsBand(activity) {
  return hasSuggestedNextSteps(activity) || showsCampaignConversion(activity);
}
