// frontend/src/utils/signalsHalo.js
//
// SIG-HALO-arch — the single source of truth for the Activity Signals band halo:
// the state→colour mapping and the count thresholds. Tune the halo here (one
// place), the component imports it — no colour role or threshold is hardcoded in
// the component. Mirrors the project pattern (utils/outcomes.js, signalTypes.js).
//
// The colours are customShadows / palette ROLE keys (resolved by the generic
// HaloBox primitive against the theme) — never a hex literal.

// State → colour role. `pending` = signals still to validate; `done` = every
// signal processed (validated or rejected).
export const SIGNALS_HALO_COLORS = {
  pending: "warning", // amber
  done: "primary",
};

// How many signals trigger each state.
export const SIGNALS_HALO_THRESHOLDS = {
  pending: 1, // >= this many PENDING → the "pending" halo
  total: 1, // >= this many total (and 0 pending) → the "done" halo
};

/**
 * Resolve the halo colour role from the (complete) signal counts, using the
 * constants above.
 *
 * @param {Object} args
 * @param {number} [args.pendingCount=0] PENDING signals across the validable types.
 * @param {number} [args.totalSignals=0] Total signals across those types.
 * @returns {"warning"|"primary"|null} a colour role key, or null for no halo.
 */
export function getSignalsHaloColor({ pendingCount = 0, totalSignals = 0 } = {}) {
  if (pendingCount >= SIGNALS_HALO_THRESHOLDS.pending) {
    return SIGNALS_HALO_COLORS.pending;
  }
  if (totalSignals >= SIGNALS_HALO_THRESHOLDS.total) {
    return SIGNALS_HALO_COLORS.done;
  }
  return null;
}
