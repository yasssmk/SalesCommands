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
  "tech-stack": [{ key: "tech_name", label: "Tool name" }],
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
  competitors: [
    { key: "competitor_name", label: "Competitor name" },
    { key: "summary", label: "Summary" },
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
 * TechStack note: the only required field is `tech_name`, the tool's
 * free-text identity. S10 removed the tech catalogue, so an extracted
 * signal is complete as it arrives — the rep no longer has to attach a
 * reference entry before validating. This mirrors the backend, where
 * the SignalManager.validate catalogue guard was dropped.
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
