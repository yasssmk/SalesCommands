// frontend/src/sections/activities/nextSteps/NextStepsFilterBar.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// MUI
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

const FILTERS = [
  { value: "all-active", label: "All Active" },
  { value: "PENDING", label: "Pending" },
  { value: "VALIDATED", label: "Converted" },
];

// ==============================|| NEXT STEPS FILTER BAR ||============================== //

export default function NextStepsFilterBar({
  activeFilter,
  onChange,
  includeRejected,
  onToggleRejected,
  signals = [],
}) {
  const counts = useMemo(() => {
    const c = { "all-active": 0, PENDING: 0, VALIDATED: 0, REJECTED: 0 };
    if (!signals) return c;
    for (const s of signals) {
      if (s.status === "PENDING") {
        c.PENDING += 1;
        c["all-active"] += 1;
      } else if (s.status === "VALIDATED") {
        c.VALIDATED += 1;
        c["all-active"] += 1;
      } else if (s.status === "REJECTED") {
        c.REJECTED += 1;
      }
    }
    return c;
  }, [signals]);

  return (
    <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
      <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5 }}>
        Filter:
      </Typography>
      {FILTERS.map((f) => (
        <Chip
          key={f.value}
          label={`${f.label} (${counts[f.value]})`}
          size="small"
          variant={activeFilter === f.value ? "filled" : "outlined"}
          color={activeFilter === f.value ? "primary" : "default"}
          onClick={() => onChange(f.value)}
          clickable
        />
      ))}
      <FormControlLabel
        control={
          <Checkbox
            size="small"
            checked={includeRejected}
            onChange={(e) => onToggleRejected(e.target.checked)}
          />
        }
        label={
          <Typography variant="caption" color="text.secondary">
            Include rejected ({counts.REJECTED})
          </Typography>
        }
        sx={{ ml: 1 }}
      />
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

NextStepsFilterBar.propTypes = {
  activeFilter: PropTypes.oneOf(["all-active", "PENDING", "VALIDATED"])
    .isRequired,
  onChange: PropTypes.func.isRequired,
  includeRejected: PropTypes.bool.isRequired,
  onToggleRejected: PropTypes.func.isRequired,
  signals: PropTypes.arrayOf(
    PropTypes.shape({
      status: PropTypes.string,
    }),
  ),
};
