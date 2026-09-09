// frontend/src/components/signals/SignalsHaloBox.jsx
//
// SIG-HALO — the Activity Signals band halo. A THIN signal-specific adapter over
// the generic HaloBox primitive: it derives the colour from the (complete)
// signal counts via the utils/signalsHalo CONSTANTS (state→colour + thresholds),
// then renders HaloBox with that colour.
//
//   - >=1 pending signal        → warning (amber) glow → "still to validate"
//   - 0 pending, >=1 total       → primary glow         → "all processed"
//   - 0 signal                   → no glow
//
// Visible EVEN WHEN THE BAND IS COLLAPSED (the wrapper is always mounted). No
// colour role or threshold is hardcoded here — they live in utils/signalsHalo.

"use client";

import PropTypes from "prop-types";

// Project imports
import HaloBox from "components/display/HaloBox";
import { getSignalsHaloColor } from "utils/signalsHalo";

// ==============================|| SIGNALS HALO BOX ||============================== //

export default function SignalsHaloBox({
  pendingCount = 0,
  totalSignals = 0,
  children,
  ...rest
}) {
  const color = getSignalsHaloColor({ pendingCount, totalSignals });

  return (
    <HaloBox color={color} data-testid="signals-halo" {...rest}>
      {children}
    </HaloBox>
  );
}

SignalsHaloBox.propTypes = {
  /** Number of PENDING signals across all validable types shown in the band. */
  pendingCount: PropTypes.number,
  /** Total number of signals across those types. */
  totalSignals: PropTypes.number,
  children: PropTypes.node,
};
