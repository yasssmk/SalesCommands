// frontend/src/components/display/Surface.jsx
//
// Centralized themed "surface" primitive. Replaces the 2nd surface the pages
// fabricate by hand (sx bgcolor:'grey.50' + border:'1px solid' +
// borderColor:'grey.200' + borderRadius:1). Consumes ONLY theme.aphoriQ.*:
// surface.level2 + border.hairline + radius.lg by default, all overridable.
// No hardcoded hex or px value — the only unit suffix is applied to the
// aphoriQ radius token.

import { forwardRef } from "react";
import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";

// ==============================|| SURFACE ||============================== //

const Surface = forwardRef(function Surface(
  {
    level = "level2",
    radius = "lg",
    borderWidth = "hairline",
    bordered = true,
    p = 2,
    sx,
    children,
    ...rest
  },
  ref,
) {
  const theme = useTheme();
  const aq = theme.aphoriQ;

  return (
    <Box
      ref={ref}
      sx={{
        backgroundColor: aq.surface[level],
        borderRadius: `${aq.radius[radius]}px`,
        ...(bordered && {
          borderStyle: "solid",
          borderWidth: aq.border.width[borderWidth],
          borderColor: aq.border.color,
        }),
        p,
        ...sx,
      }}
      {...rest}
    >
      {children}
    </Box>
  );
});

Surface.propTypes = {
  /** Surface elevation token: level1 | level2 | level3 (theme.aphoriQ.surface). */
  level: PropTypes.oneOf(["level1", "level2", "level3"]),
  /** Key into theme.aphoriQ.radius (sm/md/lg/xl…). */
  radius: PropTypes.string,
  /** Key into theme.aphoriQ.border.width (hairline/thin/thick). */
  borderWidth: PropTypes.string,
  /** Whether to draw the aphoriQ border. */
  bordered: PropTypes.bool,
  /** Padding, in MUI spacing units. */
  p: PropTypes.oneOfType([PropTypes.number, PropTypes.object]),
  sx: PropTypes.object,
  children: PropTypes.node,
};

export default Surface;
