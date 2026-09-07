// frontend/src/components/signals/SignalsHaloBox.jsx
//
// SIG-HALO — a coloured GLOW ("halo") wrapper for the Activity Signals band.
// The band signals its global validation state at a glance, VISIBLE EVEN WHEN
// THE BAND IS COLLAPSED, because the glow lives on this wrapper (always mounted)
// rather than inside the collapsible band body.
//
//   - >=1 pending signal        → warning (amber) glow → "still to validate"
//   - 0 pending, >=1 total       → primary glow         → "all processed"
//   - 0 signal                   → no glow
//
// The glow is a themed customShadows token (a soft coloured box-shadow, NOT a
// thick border, NO inner fill) — no hex / px literal lives here. Activity-only:
// wired at the Activity band mount; it does NOT touch the shared CollapsibleStrip
// (so other bands / DC / Account never inherit a halo).

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";

// ==============================|| HALO PREDICATE ||============================== //

/**
 * Resolve the halo colour role from the (complete) signal counts.
 * @returns {"warning"|"primary"|null} a customShadows key, or null for no halo.
 */
export function getSignalsHalo({ pendingCount = 0, totalSignals = 0 } = {}) {
  if (pendingCount >= 1) return "warning"; // something still to validate
  if (totalSignals >= 1) return "primary"; // all signals processed
  return null; // nothing to validate → no halo
}

// ==============================|| SIGNALS HALO BOX ||============================== //

export default function SignalsHaloBox({
  pendingCount = 0,
  totalSignals = 0,
  children,
  ...rest
}) {
  const theme = useTheme();

  const key = getSignalsHalo({ pendingCount, totalSignals });
  const boxShadow = key ? theme.customShadows[key] : "none";

  return (
    <Box
      data-testid="signals-halo"
      sx={{
        boxShadow,
        borderRadius: `${theme.aphoriQ.radius.md}px`,
        transition: theme.transitions.create("box-shadow", {
          duration: theme.transitions.duration.shorter,
        }),
      }}
      {...rest}
    >
      {children}
    </Box>
  );
}

SignalsHaloBox.propTypes = {
  /** Number of PENDING signals across all validable types shown in the band. */
  pendingCount: PropTypes.number,
  /** Total number of signals across those types. */
  totalSignals: PropTypes.number,
  children: PropTypes.node,
};
