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
 * Special case: TechStack signals with metadata.pending_tech_name
 * are considered complete even without tech_catalog_entry (the LLM
 * extracted a tool name that couldn't match the catalog).
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

    if (
      signalType === "tech-stack" &&
      field.key === "tech_catalog_entry" &&
      signal.metadata?.pending_tech_name
    ) {
      return false;
    }

    if (value === null || value === undefined || value === "") return true;

    return false;
  });
}
