// frontend/src/components/signals/ObjectiveScopePill.jsx
//
// SIG-5b — the shared Objective "scope pill". A UI surcouche over the EXISTING
// backend fields (scope_level enum + target_department FK) — zero backend.
//
// Two offered states: Company (scope_level=BUSINESS) · Department
// (scope_level=DEPARTMENT). One active, derived from `value.scope_level`.
// Clicking a pill raises a DRAFT scope patch via onChange (the widget never
// saves). When Department is active, a department select is shown and its choice
// raises a `{ target_department }` patch.
//
// PERSONAL is legacy: an objective already stored PERSONAL is shown as a third,
// read-only (non-clickable) pill so its data is neither hidden nor forced to
// change; PERSONAL is never offered as a choice. Backend enum keeps PERSONAL.
//
// Theme tokens only (StatusPill + palette paths from constants), no hex/px.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// Project imports
import StatusPill from "components/chips/StatusPill";
import {
  OBJECTIVE_SCOPE,
  SCOPE_PILL_OPTIONS,
  PERSONAL_LEGACY_LABEL,
  SCOPE_PILL_COLORS,
  deriveScopeState,
  scopePatch,
} from "utils/objectiveScope";

// ==============================|| OBJECTIVE SCOPE PILL ||============================== //

export default function ObjectiveScopePill({
  value,
  onChange,
  departmentOptions = [],
  sx,
}) {
  const active = deriveScopeState(value?.scope_level);
  const isDepartment = active === OBJECTIVE_SCOPE.DEPARTMENT;
  const isLegacyPersonal = active === OBJECTIVE_SCOPE.PERSONAL;

  const choose = (key) => onChange?.(scopePatch(key));

  const pillColors = (isActive) =>
    isActive ? SCOPE_PILL_COLORS.active : SCOPE_PILL_COLORS.inactive;

  return (
    <Box sx={sx}>
      <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
        {SCOPE_PILL_OPTIONS.map(({ key, label }) => {
          const isActive = active === key;
          return (
            <StatusPill
              key={key}
              data-testid={`scope-pill-${key}`}
              role="button"
              tabIndex={0}
              aria-pressed={isActive}
              onClick={() => choose(key)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  choose(key);
                }
              }}
              label={label}
              colorText={pillColors(isActive).colorText}
              colorBg={pillColors(isActive).colorBg}
              sx={{ cursor: "pointer" }}
            />
          );
        })}

        {/* Legacy PERSONAL — read-only, never offered. Shown active-styled so the
            existing scope is visible; not clickable, marked aria-disabled. */}
        {isLegacyPersonal && (
          <StatusPill
            data-testid={`scope-pill-${OBJECTIVE_SCOPE.PERSONAL}`}
            aria-disabled
            label={PERSONAL_LEGACY_LABEL}
            colorText={SCOPE_PILL_COLORS.active.colorText}
            colorBg={SCOPE_PILL_COLORS.active.colorBg}
          />
        )}
      </Stack>

      {/* Department select — shown only when Department is active. Native select
          for a straightforward, testable value change; its choice is a draft
          target_department patch. */}
      {isDepartment && (
        <Box sx={{ mt: 1 }}>
          <TextField
            select
            fullWidth
            size="small"
            label="Department"
            value={value?.target_department ?? ""}
            onChange={(e) => onChange?.({ target_department: e.target.value })}
            SelectProps={{ native: true }}
            inputProps={{ "data-testid": "scope-department-select" }}
          >
            <option value="" disabled>
              Select a department…
            </option>
            {departmentOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </TextField>
        </Box>
      )}

      {isLegacyPersonal && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
          Legacy personal objective — scope kept as recorded.
        </Typography>
      )}
    </Box>
  );
}

ObjectiveScopePill.propTypes = {
  /** The objective's current scope fields: { scope_level, target_department }. */
  value: PropTypes.shape({
    scope_level: PropTypes.string,
    target_department: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  }),
  /** Raised with a draft patch of scope fields — the widget never saves. */
  onChange: PropTypes.func,
  /** Department options for the Department select: [{ value, label }]. */
  departmentOptions: PropTypes.arrayOf(
    PropTypes.shape({ value: PropTypes.any, label: PropTypes.node }),
  ),
  sx: PropTypes.object,
};
