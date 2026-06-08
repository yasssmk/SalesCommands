// frontend/src/sections/activities/signals/SignalsFilterBar.jsx

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

// MUI
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

const FILTERS = [
  { value: "all", label: "All" },
  { value: "PENDING", label: "Pending" },
  { value: "VALIDATED", label: "Validated" },
  { value: "REJECTED", label: "Rejected" },
];

// ==============================|| SIGNALS FILTER BAR ||============================== //

export default function SignalsFilterBar({ activeFilter, onChange, signals = [] }) {
  const counts = useMemo(() => {
    const c = { all: 0, PENDING: 0, VALIDATED: 0, REJECTED: 0 };
    if (!signals) return c;
    for (const s of signals) {
      c.all += 1;
      if (s.status && c[s.status] !== undefined) {
        c[s.status] += 1;
      }
    }
    return c;
  }, [signals]);

  return (
    <Stack direction="row" spacing={1} alignItems="center">
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
    </Stack>
  );
}

SignalsFilterBar.propTypes = {
  activeFilter: PropTypes.oneOf(["all", "PENDING", "VALIDATED", "REJECTED"])
    .isRequired,
  onChange: PropTypes.func.isRequired,
  signals: PropTypes.arrayOf(
    PropTypes.shape({
      status: PropTypes.string,
    }),
  ),
};

// Default props handled via default parameter in component signature
