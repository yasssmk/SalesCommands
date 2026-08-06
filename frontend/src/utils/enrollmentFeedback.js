// frontend/src/utils/enrollmentFeedback.js

/**
 * Enrollment feedback notifications (centralized).
 *
 * Turns an enroll_target response (E4/E5 contract) into a single snackbar:
 *   - GREEN  (displaySuccessSnackbar) when at least one contact was enrolled.
 *   - ORANGE (displayWarningSnackbar) when nothing was enrolled — the message
 *     names the cause from the counters.
 * RED is never produced here: a "zero enrolled" outcome is information, not an
 * error. Red stays for genuine technical failures (result.success === false),
 * handled by the caller.
 *
 * Mirrors utils/csvImportNotifications.js: read a response summary, pick the
 * tone, emit the snackbar, return { shown, kind, message }.
 *
 * Fields consumed (both response exits carry them):
 *   contacts_enrolled, no_channel_count, opted_out_count, already_active_count,
 *   account_empty (bool), strict (bool).
 *
 * @module utils/enrollmentFeedback
 */

import { displaySuccessSnackbar, displayWarningSnackbar } from "utils/displayError";

// ------------------------------ Helpers ------------------------------ //

/**
 * Tolerant extraction of the enrollment counters. Accepts either the unwrapped
 * data object or a { data: {...} } envelope.
 */
function extractOutcome(data) {
  const d = data && data.data ? data.data : data || {};
  return {
    enrolled: Number(d.contacts_enrolled ?? 0),
    noChannel: Number(d.no_channel_count ?? 0),
    optedOut: Number(d.opted_out_count ?? 0),
    alreadyActive: Number(d.already_active_count ?? 0),
    accountEmpty: Boolean(d.account_empty),
    strict: Boolean(d.strict),
  };
}

/**
 * Green message: success, with a "N skipped" tail when some were ignored.
 * N = no_channel + opted_out + already_active.
 */
function buildGreenMessage({ noChannel, optedOut, alreadyActive }) {
  const skipped = noChannel + optedOut + alreadyActive;
  if (skipped === 0) return "Contact(s) enrolled";
  return `Enrolled. ${skipped} contact${skipped > 1 ? "s" : ""} skipped`;
}

/**
 * Orange message (nothing enrolled): empty first, then generic when several
 * causes are present, then the specific text for a single cause.
 */
function buildOrangeMessage({ noChannel, optedOut, alreadyActive, accountEmpty, strict }) {
  const causeCount =
    (noChannel > 0 ? 1 : 0) + (optedOut > 0 ? 1 : 0) + (alreadyActive > 0 ? 1 : 0);

  // Empty account/department, or CONTACT mode with only phantom ids.
  if (accountEmpty || causeCount === 0) return "No contacts";

  // Several causes at once -> generic message.
  if (causeCount > 1) return "No reachable contact in this account";

  // Exactly one cause.
  if (alreadyActive > 0) return "Already enrolled";
  if (optedOut > 0) {
    return strict ? "This contact has opted out" : "All contacts have opted out";
  }
  // no channel
  return strict
    ? "This contact is not reachable"
    : "No reachable contact in this account";
}

// ------------------------------ Main API ------------------------------ //

/**
 * Emit the enrollment snackbar for an enroll_target response.
 *
 * @param {object} data - enroll_target response data (unwrapped or { data }).
 * @returns {{ shown: boolean, kind: 'success'|'warning', message: string }}
 */
export function notifyEnrollmentOutcome(data) {
  const outcome = extractOutcome(data);

  if (outcome.enrolled > 0) {
    const message = buildGreenMessage(outcome);
    displaySuccessSnackbar(message);
    return { shown: true, kind: "success", message };
  }

  const message = buildOrangeMessage(outcome);
  displayWarningSnackbar(message);
  return { shown: true, kind: "warning", message };
}
