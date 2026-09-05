// frontend/src/components/signals/SignalTypeHeader.jsx
//
// SIG-1 — the per-type GROUP HEADER for the signal validation list. Renders the
// type's LABEL as COLOURED TEXT in its dedicated signal-type colour (subtitle2,
// medium) — NOT a Chip/pill (PO rule: the type is coloured text, not a
// decorative pill). Label + colour come from the single source of truth
// (utils/signalTypes.js → theme.aphoriQ.signalColors).
//
// This is the reusable brick only; wiring it into the list (and replacing the
// SignalTypeChip pill in the rows) is S-2.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Typography from "@mui/material/Typography";

// Project imports
import { getSignalTypeLabel, getSignalTypeColor } from "utils/signalTypes";

// ==============================|| SIGNAL TYPE HEADER ||============================== //

export default function SignalTypeHeader({ signalType, ...rest }) {
  const theme = useTheme();

  const label = getSignalTypeLabel(signalType);
  if (!label) return null;

  const color = getSignalTypeColor(signalType, theme);

  return (
    <Typography
      variant="subtitle2"
      component="div"
      sx={{ color, fontWeight: 500 }}
      {...rest}
    >
      {label}
    </Typography>
  );
}

SignalTypeHeader.propTypes = {
  signalType: PropTypes.oneOf([
    "pain",
    "objective",
    "impact",
    "tech-stack",
    "blockers",
    "next-steps",
    "people",
    "constraints",
    "competitors",
  ]),
};
