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

// The successful outcomes of a campaign activity — the mirror of the backend
// SUCCESSFUL_OUTCOMES (campaigns/constants.py): they open the conversion and,
// 5.14b, the next steps.
export const CAMPAIGN_CONVERSION_OUTCOMES = ["SUCCESSFUL", "MEETING_SCHEDULED"];

// The suggested next steps (extracted by the AI) — the mirror of the backend
// predicate next_steps_enabled (5.14b): an activity in a decision cycle, or a
// campaign activity whose outcome is successful (PO: the goal of a campaign
// is to create decision cycles). Anywhere else they are neither proposed nor
// counted.
export function hasSuggestedNextSteps(activity) {
  if (activity?.decision_cycle) return true;
  return (
    Boolean(activity?.campaign_detail) &&
    CAMPAIGN_CONVERSION_OUTCOMES.includes(activity?.outcome)
  );
}

// The decision cycle born from a campaign activity ({ id, name }), read from
// the server's next planned step (BORN_DECISION_CYCLE — the backend
// born_decision_cycle), else null.
export function bornDecisionCycle(activity) {
  const next = activity?.next_planned_step;
  return next?.source === "BORN_DECISION_CYCLE" ? next.decision_cycle || null : null;
}

// The decision cycle the band's creations go into (5.14b): the activity's own,
// else the one born from it — null while none (a campaign activity: its next
// steps then convert, a NEW cycle inline).
export function nextStepsCycleId(activity) {
  return activity?.decision_cycle || bornDecisionCycle(activity)?.id || null;
}

// The campaign → Decision Cycle conversion block (« Successful outcome — ready
// to convert » + Start Decision Cycle) applies — the conditions it always had
// (5.12 B, moved unchanged): a campaign activity (no decision_cycle), no DC
// born from it yet, a converting outcome, the band not locked.
export function showsCampaignConversion(activity) {
  const isCampaignActivity = Boolean(activity?.campaign_detail) && !activity?.decision_cycle;
  return (
    isCampaignActivity &&
    !bornDecisionCycle(activity) &&
    CAMPAIGN_CONVERSION_OUTCOMES.includes(activity?.outcome) &&
    !isActivitySignalsLocked(activity)
  );
}

// The band is rendered only when it has something to show (5.12 B, the
// Preparation model): the next steps, or the conversion block.
export function hasNextStepsBand(activity) {
  return hasSuggestedNextSteps(activity) || showsCampaignConversion(activity);
}
