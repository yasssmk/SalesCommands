// frontend/src/utils/signalTypes.js
//
// SIG-1 — the UNIFIED front source of truth for signal TYPE presentation
// (label + dedicated colour), mirroring utils/outcomes.js. One META table plus
// resolver helpers so a type's label and colour are defined ONCE and read by
// every signal surface (group header, line, drawer).
//
// (Lives under utils/ because that path is aliased project-wide; `constants/`
// is not — same reason as outcomes.js.)
//
// The 9 slugs align 1:1 with the API source of truth (api/signals/signals.js:30-40):
//   pain, objective, impact, tech-stack, blockers (= "Objection"), next-steps,
//   people, constraints, competitors.
//
// Colours are NOT stored here: `colorKey` points into the dedicated theme group
// theme.aphoriQ.signalColors (themes/aphoriq.js), which is the single place any
// signal-type colour is defined. getSignalTypeColor() resolves it from a theme.

// ==============================|| META (9 signal types) ||============================== //

export const SIGNAL_TYPE_META = {
  pain: { label: "Pain", colorKey: "pain" },
  objective: { label: "Objective", colorKey: "objective" },
  impact: { label: "Impact", colorKey: "impact" },
  "tech-stack": { label: "Tech Stack", colorKey: "tech-stack" },
  blockers: { label: "Objection", colorKey: "blockers" },
  "next-steps": { label: "Next step", colorKey: "next-steps" },
  people: { label: "People", colorKey: "people" },
  constraints: { label: "Constraint", colorKey: "constraints" },
  competitors: { label: "Competitor", colorKey: "competitors" },
};

// Canonical slug list (stable order — same as the API vocabulary).
export const SIGNAL_TYPE_SLUGS = Object.keys(SIGNAL_TYPE_META);

// ==============================|| RESOLVERS ||============================== //

/**
 * The V0 English label for a signal type.
 * @param {string} signalType - frontend slug (e.g. "pain", "tech-stack")
 * @returns {string|null} the label, or null for an unknown type.
 */
export function getSignalTypeLabel(signalType) {
  return SIGNAL_TYPE_META[signalType]?.label ?? null;
}

/**
 * The dedicated colour for a signal type, resolved from the theme's
 * aphoriQ.signalColors group (the single source of truth).
 * @param {string} signalType - frontend slug
 * @param {object} theme - the MUI theme (must carry theme.aphoriQ.signalColors)
 * @returns {string|null} the colour, or null for an unknown type / missing group.
 */
export function getSignalTypeColor(signalType, theme) {
  const meta = SIGNAL_TYPE_META[signalType];
  const group = theme?.aphoriQ?.signalColors;
  if (!meta || !group) return null;
  return group[meta.colorKey] ?? null;
}
