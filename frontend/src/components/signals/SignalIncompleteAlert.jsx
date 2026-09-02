// frontend/src/components/signals/SignalIncompleteAlert.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Alert from "@mui/material/Alert";

// ==============================|| SIGNAL INCOMPLETE ALERT ||============================== //

export default function SignalIncompleteAlert({ missingFields }) {
  if (!missingFields || missingFields.length === 0) return null;

  const labels = missingFields.map((f) => f.label).join(", ");

  return (
    <Alert severity="warning" sx={{ mb: 2 }}>
      This signal is missing: <strong>{labels}</strong>. Complete before
      validating.
    </Alert>
  );
}

SignalIncompleteAlert.propTypes = {
  missingFields: PropTypes.arrayOf(
    PropTypes.shape({
      key: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired,
    }),
  ),
};
