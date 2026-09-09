// frontend/src/components/chips/StatusPill.jsx
//
// CHIP-1 — the new SHARED standard chip, meant to replace the project's chips
// surface by surface. A chip has THREE visual parts — CONTOUR (border) · FOND
// (background) · TEXTE — driven by TWO colours:
//   - colorText : the TEXT and the BORDER (same value)
//   - colorBg   : the BACKGROUND
// GENERIC: it receives the two colours and knows nothing about statuses. Pill
// shape, caption weight, compact padding. Theme tokens only — no styled(), no
// hardcoded hex/px (radius/border widths come from aphoriQ, spacing from MUI).

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";

export default function StatusPill({ status, statusMap, label, colorText, colorBg, sx, ...rest }) {
  const aq = useTheme().aphoriQ;

  // Status-aware mode: when a `status` + `statusMap` are given, the label and
  // the colours are resolved from the shared mapping ({ label, role }) — text +
  // border on `${role}.main`, background on `${role}.lighter`. An unknown status
  // renders nothing (mirrors SignalStatusChip). Otherwise the generic mode uses
  // the explicit label / colorText / colorBg.
  let resolvedLabel = label;
  let resolvedText = colorText;
  let resolvedBg = colorBg;
  if (status !== undefined) {
    const cfg = statusMap?.[status];
    if (!cfg) return null;
    resolvedLabel = cfg.label;
    resolvedText = `${cfg.role}.main`;
    resolvedBg = `${cfg.role}.lighter`;
  }

  return (
    <Box
      component="span"
      data-testid="status-pill"
      {...rest}
      sx={{
        display: "inline-flex",
        alignItems: "center",
        flexShrink: 0,
        px: 1,
        py: 0.25,
        borderRadius: `${aq.radius.pill}px`,
        borderStyle: "solid",
        borderWidth: aq.border.width.thin,
        borderColor: resolvedText, // CONTOUR = colorText
        bgcolor: resolvedBg, // FOND = colorBg
        color: resolvedText, // TEXTE = colorText
        typography: "caption",
        fontWeight: "medium",
        lineHeight: 1.6,
        whiteSpace: "nowrap",
        ...sx,
      }}
    >
      {resolvedLabel}
    </Box>
  );
}

StatusPill.propTypes = {
  /** Status-aware mode: a key into `statusMap`. When set, label + colours come
      from the map and the generic label/colorText/colorBg are ignored. */
  status: PropTypes.string,
  /** Status → { label, role } mapping (e.g. SIGNAL_STATUS_PILL). Used with `status`. */
  statusMap: PropTypes.object,
  /** Pill label (generic mode). */
  label: PropTypes.node,
  /** Colour of the TEXT and the BORDER (a theme token / palette path or raw value). */
  colorText: PropTypes.string,
  /** Colour of the BACKGROUND (a theme token / palette path or raw value). */
  colorBg: PropTypes.string,
  /** Extra sx overrides (merged last). */
  sx: PropTypes.object,
};
