// frontend/src/components/chips/ClickablePill.jsx
//
// The CLICKABLE pill of the surface — the shared StatusPill made a button
// (role, tab stop, Enter / Space), coloured by the scope pill tokens
// (SCOPE_PILL_COLORS: active = primary, inactive = neutral). Extracted from the
// scope pills of ScopeDepartmentsField (Sprint Next steps 5.8e) so every
// clickable pill reads the same: the scope pills, "+ Add next step" and the
// activity type pills.
// `pressed` (optional) makes it a toggle (aria-pressed); absent → a plain
// action. `disabled` (5.12c) — an unavailable action: aria-disabled, out of
// the tab order, no click / key, the theme's disabled opacity. Other props
// (data-testid, sx…) pass through to StatusPill.

"use client";

import PropTypes from "prop-types";

// Project
import StatusPill from "components/chips/StatusPill";
import { SCOPE_PILL_COLORS } from "utils/objectiveScope";

export default function ClickablePill({ label, onClick, active = false, pressed, disabled = false, sx, ...rest }) {
  const c = active ? SCOPE_PILL_COLORS.active : SCOPE_PILL_COLORS.inactive;
  return (
    <StatusPill
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-pressed={pressed}
      aria-disabled={disabled || undefined}
      onClick={disabled ? undefined : onClick}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick?.(e);
        }
      }}
      label={label}
      colorText={c.colorText}
      colorBg={c.colorBg}
      sx={{
        cursor: disabled ? "default" : "pointer",
        ...(disabled && { opacity: (theme) => theme.palette.action.disabledOpacity }),
        ...sx,
      }}
      {...rest}
    />
  );
}

ClickablePill.propTypes = {
  label: PropTypes.node.isRequired,
  onClick: PropTypes.func,
  /** Active (primary) or inactive (neutral) colours. */
  active: PropTypes.bool,
  /** Toggle state (aria-pressed); absent → a plain action. */
  pressed: PropTypes.bool,
  /** An unavailable action (aria-disabled, no click / key). */
  disabled: PropTypes.bool,
  sx: PropTypes.object,
};
