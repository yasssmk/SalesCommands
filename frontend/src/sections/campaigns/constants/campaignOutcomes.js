// frontend/src/sections/campaigns/constants/campaignOutcomes.js
/**
 * Campaign outcome constants — single source of truth.
 *
 * Mirrors backend ActivityOutcome enum (app_modules/activities/constants.py).
 * Import from here instead of defining locally in components.
 */

// ── Per-outcome display config ──────────────────────────────────────────────
export const OUTCOME_CONFIG = {
  SUCCESSFUL: { color: "success", label: "Successful", category: "positive" },
  MEETING_SCHEDULED: {
    color: "success",
    label: "Meeting Scheduled",
    category: "positive",
  },
  NO_ANSWER: { color: "warning", label: "No Answer", category: "neutral" },
  CALLBACK_REQUESTED: {
    color: "info",
    label: "Callback Requested",
    category: "neutral",
  },
  FOLLOW_UP_NEEDED: {
    color: "warning",
    label: "Follow-up Needed",
    category: "neutral",
  },
  OTHER: { color: "default", label: "Other", category: "neutral" },
  NOT_INTERESTED: {
    color: "error",
    label: "Not Interested",
    category: "negative",
  },
  WRONG_CONTACT: {
    color: "error",
    label: "Wrong Contact",
    category: "negative",
  },
  UNSUBSCRIBE_OPTOUT: {
    color: "error",
    label: "Unsubscribe / Opt-out",
    category: "negative",
  },
  WRONG_EMAIL: { color: "error", label: "Wrong Email", category: "negative" },
  INVALID_PHONE_NUMBER: {
    color: "error",
    label: "Invalid Phone Number",
    category: "negative",
  },
};

// Display order for outcome chip selectors (positive → neutral → negative)
export const OUTCOME_KEYS_ORDERED = [
  "SUCCESSFUL",
  "MEETING_SCHEDULED",
  "NO_ANSWER",
  "CALLBACK_REQUESTED",
  "FOLLOW_UP_NEEDED",
  "OTHER",
  "NOT_INTERESTED",
  "WRONG_CONTACT",
  "UNSUBSCRIBE_OPTOUT",
  "WRONG_EMAIL",
  "INVALID_PHONE_NUMBER",
];

// ── Outcome sets ─────────────────────────────────────────────────────────────

/**
 * Outcomes that require a confirmation dialog in the card
 * (sequence chain will be cancelled for this contact).
 */
export const CONFIRM_DIALOG_OUTCOMES = new Set([
  "NOT_INTERESTED",
  "WRONG_CONTACT",
  "UNSUBSCRIBE_OPTOUT",
  "WRONG_EMAIL",
  "INVALID_PHONE_NUMBER",
]);

/**
 * Outcomes that trigger cancel-planned after completion
 * (backend already cancelled the contact chain — frontend may cancel at
 * account/department scope via the scope dialog or auto-cancel if single contact).
 */
export const CANCEL_TRIGGER_OUTCOMES = new Set([
  "SUCCESSFUL",
  "MEETING_SCHEDULED",
  "NOT_INTERESTED",
  "WRONG_CONTACT",
  "UNSUBSCRIBE_OPTOUT",
  "WRONG_EMAIL",
  "INVALID_PHONE_NUMBER",
]);

// ── Convenience helpers ───────────────────────────────────────────────────────

/** Returns the display category for an outcome key. */
export function getOutcomeCategory(outcomeKey) {
  return OUTCOME_CONFIG[outcomeKey]?.category ?? "neutral";
}
