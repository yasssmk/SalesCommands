// frontend/src/utils/outcomes.js
//
// O-1 — the UNIFIED front source of truth for activity outcomes. (Lives under
// utils/ because that path is aliased project-wide; `constants/` is not.) Aligns with the
// 11 backend ActivityOutcome values (app_modules/activities/constants.py:48-59):
// value + label + palette role (MUI role that has both .main and .contrastText),
// plus the PO-validated type→outcomes map consumed by getOutcomesForType().
//
// This is a NEW dedicated module on purpose: the legacy `ACTIVITY_OUTCOMES` (8
// values) in api/accounts/activities.js is left untouched so its only consumer
// (ActivityCompleteModal) is unchanged; new surfaces read from here instead.
//
// No colours are hardcoded — `role` is a MUI palette role; consumers resolve
// `${role}.main` / `${role}.contrastText` / a neutral background token.

// ==============================|| META (11 outcomes) ||============================== //

export const OUTCOME_META = {
  SUCCESSFUL: { label: "Successful", role: "success" },
  MEETING_SCHEDULED: { label: "Meeting Scheduled", role: "success" },
  CALLBACK_REQUESTED: { label: "Callback Requested", role: "info" },
  FOLLOW_UP_NEEDED: { label: "Follow-up Needed", role: "warning" },
  NO_ANSWER: { label: "No Answer", role: "warning" },
  NOT_INTERESTED: { label: "Not Interested", role: "error" },
  WRONG_CONTACT: { label: "Wrong Contact", role: "error" },
  WRONG_EMAIL: { label: "Wrong Email", role: "error" },
  INVALID_PHONE_NUMBER: { label: "Invalid Phone Number", role: "error" },
  UNSUBSCRIBE_OPTOUT: { label: "Unsubscribe / Opt-out", role: "error" },
  OTHER: { label: "Other", role: "secondary" },
};

// Canonical display order (positive → neutral → negative → other).
export const OUTCOME_ORDER = [
  "SUCCESSFUL",
  "MEETING_SCHEDULED",
  "CALLBACK_REQUESTED",
  "FOLLOW_UP_NEEDED",
  "NO_ANSWER",
  "WRONG_CONTACT",
  "WRONG_EMAIL",
  "INVALID_PHONE_NUMBER",
  "NOT_INTERESTED",
  "UNSUBSCRIBE_OPTOUT",
  "OTHER",
];

export const OUTCOME_VALUES = OUTCOME_ORDER;

// ==============================|| TYPE → OUTCOMES (PO-validated table) ||============================== //

const ALL_REAL_TYPES = ["CALL", "MEETING", "EMAIL", "LINKEDIN", "TASK", "DEMO"];

// Per-outcome: which activity types offer it (transcribed 1:1 from the PO table).
const OUTCOME_TYPES = {
  SUCCESSFUL: ALL_REAL_TYPES,
  NOT_INTERESTED: ALL_REAL_TYPES,
  MEETING_SCHEDULED: ALL_REAL_TYPES,
  FOLLOW_UP_NEEDED: ALL_REAL_TYPES,
  OTHER: ALL_REAL_TYPES,
  NO_ANSWER: ALL_REAL_TYPES,
  CALLBACK_REQUESTED: ["CALL", "EMAIL", "LINKEDIN", "DEMO"],
  WRONG_CONTACT: ["CALL", "MEETING", "EMAIL", "LINKEDIN", "DEMO"],
  WRONG_EMAIL: ["EMAIL", "DEMO"],
  INVALID_PHONE_NUMBER: ["CALL", "DEMO"],
  UNSUBSCRIBE_OPTOUT: ["CALL", "EMAIL", "LINKEDIN"],
};

// Fallback for the OTHER activity type (and any unknown/empty type): the common
// base only, without NO_ANSWER (per PO).
const FALLBACK_OUTCOMES = [
  "SUCCESSFUL",
  "MEETING_SCHEDULED",
  "FOLLOW_UP_NEEDED",
  "NOT_INTERESTED",
  "OTHER",
];

/**
 * Ordered list of the outcomes valid for a given activity type.
 * Real types (CALL/MEETING/EMAIL/LINKEDIN/TASK/DEMO) filter the canonical order
 * by the PO table; OTHER and unknown/empty fall back to the common base.
 */
export function getOutcomesForType(activityType) {
  if (!ALL_REAL_TYPES.includes(activityType)) {
    return OUTCOME_ORDER.filter((o) => FALLBACK_OUTCOMES.includes(o));
  }
  return OUTCOME_ORDER.filter((o) => (OUTCOME_TYPES[o] || []).includes(activityType));
}
