// frontend/src/sections/activities/signals/signalValidationRules.js

/**
 * Required-field definitions per signal type and helpers to detect
 * incomplete signals. Used by SignalDetailCard, SignalQuickDrawer,
 * and SignalEditDialog to surface "missing fields" alerts and
 * disable the Validate action until the signal is complete.
 */

const REQUIRED_FIELDS = {
  pain: [
    { key: "what", label: "What" },
    { key: "dimension", label: "Dimension" },
    { key: "summary", label: "Summary" },
  ],
  objective: [
    { key: "what", label: "What" },
    { key: "dimension", label: "Dimension" },
    { key: "scope_level", label: "Scope level" },
    { key: "summary", label: "Summary" },
  ],
  impact: [
    { key: "what", label: "What" },
    { key: "dimension", label: "Dimension" },
    { key: "scope_level", label: "Scope level" },
    { key: "impact_type", label: "Impact type" },
    { key: "summary", label: "Summary" },
  ],
  "tech-stack": [{ key: "tech_catalog_entry", label: "Tech catalog entry" }],
  blockers: [{ key: "summary", label: "Summary" }],
  "next-steps": [
    { key: "suggested_title", label: "Suggested title" },
    { key: "suggested_activity_type", label: "Suggested activity type" },
  ],
  people: [
    { key: "role", label: "Role" },
  ],
  constraints: [
    { key: "what", label: "What" },
    { key: "dimension", label: "Dimension" },
    { key: "summary", label: "Summary" },
    { key: "rigidity", label: "Rigidity" },
  ],
};

/**
 * Get the list of required field definitions for a signal type.
 *
 * @param {string} signalType
 * @returns {Array<{key: string, label: string}>}
 */
export function getRequiredFields(signalType) {
  return REQUIRED_FIELDS[signalType] ?? [];
}

/**
 * Determine which required fields are missing on a signal.
 *
 * TechStack note: a signal whose LLM-extracted tool did not match the
 * catalog is persisted PENDING with metadata.pending_tech_name and no
 * tech_catalog_entry. It is NOT complete — the rep must attach a
 * catalog entry (the picker is enabled while PENDING) before it can be
 * validated. This mirrors the backend SignalManager.validate guard.
 *
 * @param {Object} signal
 * @param {string} signalType
 * @returns {Array<{key: string, label: string}>}
 */
export function getMissingFields(signal, signalType) {
  if (!signal || !signalType) return [];

  const required = getRequiredFields(signalType);

  return required.filter((field) => {
    const value = signal[field.key];

    if (value === null || value === undefined || value === "") return true;

    return false;
  });
}

/**
 * Whether a TechStack signal's tech_catalog_entry may be edited.
 *
 * The catalog anchor is settable while the signal is PENDING (so an
 * LLM-extracted signal with no catalog match can be linked before
 * validation) and immutable once VALIDATED — mirrors the backend
 * TechStackSignalUpdateSerializer lock. A falsy signal (create mode,
 * no instance yet) is editable.
 *
 * @param {Object|null|undefined} signal - signal-like object with a `status`
 * @returns {boolean}
 */
export function canEditCatalogEntry(signal) {
  return !signal || signal.status === "PENDING";
}
