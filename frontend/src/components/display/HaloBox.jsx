// frontend/src/components/display/HaloBox.jsx
//
// Generic, project-reusable STATE-HALO primitive: wraps its children in a soft
// coloured glow ("halo") for a given colour ROLE. The glow is a themed
// customShadows token (a soft coloured box-shadow, NOT a thick border, NO inner
// fill) — no hex / px literal lives here. A falsy `color` renders no halo.
//
// Not tied to any feature: any screen can use it for an at-a-glance state cue
// (e.g. <HaloBox color="warning">…</HaloBox>). Feature-specific adapters
// (e.g. components/signals/SignalsHaloBox) decide the colour and build on this.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";

// ==============================|| HALO BOX ||============================== //

export default function HaloBox({ color, children, ...rest }) {
  const theme = useTheme();

  // `color` is a customShadows role key (e.g. "warning" / "primary" / "error").
  // Falsy → no halo.
  const boxShadow = color ? theme.customShadows[color] : "none";

  return (
    <Box
      data-testid="halo-box"
      sx={{
        boxShadow,
        borderRadius: `${theme.aphoriQ.radius.md}px`,
        transition: theme.transitions.create("box-shadow", {
          duration: theme.transitions.duration.shorter,
        }),
      }}
      {...rest}
    >
      {children}
    </Box>
  );
}

HaloBox.propTypes = {
  /** A customShadows colour role key (e.g. "warning", "primary"). Falsy → no halo. */
  color: PropTypes.string,
  children: PropTypes.node,
};
