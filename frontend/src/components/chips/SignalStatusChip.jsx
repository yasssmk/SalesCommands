// frontend/src/components/chips/SignalStatusChip.jsx

"use client";

import PropTypes from "prop-types";
import Chip from "@mui/material/Chip";

const STATUS_CONFIG = {
  PENDING: { color: "warning", label: "Pending" },
  VALIDATED: { color: "success", label: "Validated" },
  REJECTED: { color: "error", label: "Rejected" },
};

// ==============================|| SIGNAL STATUS CHIP ||============================== //

export default function SignalStatusChip({ status, size = "small", ...rest }) {
  const config = STATUS_CONFIG[status];
  if (!config) return null;

  return (
    <Chip
      label={config.label}
      color={config.color}
      size={size}
      variant="outlined"
      {...rest}
    />
  );
}

SignalStatusChip.propTypes = {
  status: PropTypes.oneOf(["PENDING", "VALIDATED", "REJECTED"]),
  size: PropTypes.oneOf(["small", "medium"]),
};
