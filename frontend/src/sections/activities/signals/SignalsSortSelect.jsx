// frontend/src/sections/activities/signals/SignalsSortSelect.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";

const SORT_OPTIONS = [
  { value: "date-desc", label: "Date (newest)" },
  { value: "date-asc", label: "Date (oldest)" },
  { value: "type", label: "Type" },
  { value: "theme", label: "Theme" },
  { value: "status", label: "Status" },
];

// ==============================|| SIGNALS SORT SELECT ||============================== //

export default function SignalsSortSelect({ value, onChange }) {
  return (
    <FormControl size="small" sx={{ minWidth: 150 }}>
      <InputLabel id="signals-sort-label">Sort</InputLabel>
      <Select
        labelId="signals-sort-label"
        id="signals-sort-select"
        value={value}
        label="Sort"
        onChange={(e) => onChange(e.target.value)}
      >
        {SORT_OPTIONS.map((opt) => (
          <MenuItem key={opt.value} value={opt.value}>
            {opt.label}
          </MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

SignalsSortSelect.propTypes = {
  value: PropTypes.oneOf(["date-desc", "date-asc", "type", "theme", "status"])
    .isRequired,
  onChange: PropTypes.func.isRequired,
};

export { SORT_OPTIONS };
