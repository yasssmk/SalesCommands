// frontend/src/utils/nextStepsBand.js
//
// Sprint Next steps 5.8f — the CONSTANTS of the "Next steps" band's data, shared
// by the band (ActivityNextStepsTab: the list) and the workspace page (the band
// halo + the header "N to validate" counter, always mounted). One query shape so
// both reads are the same SWR key (deduped) and can never disagree.

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
