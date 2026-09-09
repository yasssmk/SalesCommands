// frontend/src/components/signals/ObjectiveScopePill.jsx
//
// SIG-5b / SIG-5d-fix — the shared Objective "scope pill". A UI surcouche over
// the EXISTING backend field scope_level — zero backend.
//
// Two offered states: Company (scope_level=BUSINESS) · Department
// (scope_level=DEPARTMENT). One active, derived from `value.scope_level`.
// Clicking a pill raises a DRAFT scope patch via onChange (the widget never
// saves). The DEPARTMENT department picker is NOT here — the caller renders the
// project's standard department Select next to the pill (SIG-5d-fix: reuse the
// original InlineObjectiveForm Select instead of an ad-hoc one).
//
// PERSONAL is legacy: an objective already stored PERSONAL is shown as a third,
// read-only (non-clickable) pill so its data is neither hidden nor forced to
// change; PERSONAL is never offered. Backend enum keeps PERSONAL.
//
// Theme tokens only (StatusPill + palette paths from constants), no hex/px.

"use client";

import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
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

export default function ObjectiveScopePill({ value, onChange, sx }) {
  const active = deriveScopeState(value?.scope_level);
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

        {/* Legacy PERSONAL — read-only, never offered. */}
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

      {isLegacyPersonal && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
          Legacy personal objective — scope kept as recorded.
        </Typography>
      )}
    </Box>
  );
}

ObjectiveScopePill.propTypes = {
  /** The objective's current scope fields — only scope_level is read. */
  value: PropTypes.shape({
    scope_level: PropTypes.string,
  }),
  /** Raised with a draft patch of scope fields — the widget never saves. */
  onChange: PropTypes.func,
  sx: PropTypes.object,
};
