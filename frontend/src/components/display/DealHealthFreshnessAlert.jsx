// frontend/src/components/display/DealHealthFreshnessAlert.jsx
//
// The freshness of a deal health — sprint « Deal health v2 », step 8 (PO
// decision of 20/11). A WARNING (the theme's warning tone, never red): there
// is new information to analyse since the last analysis, or no analysis at
// all. Nothing when the freshness does not apply (before Technical Fit, a
// closed cycle) or when nothing is new. Never « stale ».
//
// The SignalIncompleteAlert pattern (components/signals/SignalIncompleteAlert.jsx):
// a compact MUI Alert, the severity giving the theme's colours. Labels in
// api/aiPipelines/dealHealth.js (DEAL_HEALTH_FRESHNESS_LABELS). Reusable as is
// wherever the server's freshness is read — the Strategic tab of the DC, the
// Game Plan section of the Activity page (sprint 2).

"use client";

import PropTypes from "prop-types";

// MUI
import Alert from "@mui/material/Alert";

// Project
import { dealHealthFreshnessMessage } from "api/aiPipelines/dealHealth";

export default function DealHealthFreshnessAlert({ freshness, sx }) {
  const message = dealHealthFreshnessMessage(freshness);
  if (!message) return null;

  return (
    <Alert
      severity="warning"
      data-testid="deal-health-freshness"
      sx={{ py: 0, alignItems: "center", ...sx }}
    >
      {message}
    </Alert>
  );
}

DealHealthFreshnessAlert.propTypes = {
  /** The server's freshness: { applies, has_new_info, last_analysis_at, reasons }. */
  freshness: PropTypes.shape({
    applies: PropTypes.bool,
    has_new_info: PropTypes.bool,
    last_analysis_at: PropTypes.string,
    reasons: PropTypes.arrayOf(PropTypes.string),
  }),
  sx: PropTypes.object,
};
