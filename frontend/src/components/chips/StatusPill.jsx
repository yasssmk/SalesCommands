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

export default function StatusPill({ label, colorText, colorBg, sx, ...rest }) {
  const aq = useTheme().aphoriQ;

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
        borderColor: colorText, // CONTOUR = colorText
        bgcolor: colorBg, // FOND = colorBg
        color: colorText, // TEXTE = colorText
        typography: "caption",
        fontWeight: "medium",
        lineHeight: 1.6,
        whiteSpace: "nowrap",
        ...sx,
      }}
    >
      {label}
    </Box>
  );
}

StatusPill.propTypes = {
  /** Pill label. */
  label: PropTypes.node,
  /** Colour of the TEXT and the BORDER (a theme token / palette path or raw value). */
  colorText: PropTypes.string,
  /** Colour of the BACKGROUND (a theme token / palette path or raw value). */
  colorBg: PropTypes.string,
  /** Extra sx overrides (merged last). */
  sx: PropTypes.object,
};
