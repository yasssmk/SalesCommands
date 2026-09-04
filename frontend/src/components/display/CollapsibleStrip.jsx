// frontend/src/components/display/CollapsibleStrip.jsx
//
// Shared themed collapsible band ("strip") for stacked adaptive workspaces
// (UX Activity: Preparation / Source / Signals / Next step).
//
// Collapsed = a themed strip header: aphoriQ surface.level2 background, hairline
// border, radius.md, a rotating chevron + a section icon + a muted title, and an
// optional right-aligned meta. Expanded = the same clickable header (chevron
// pivoted) followed by the body inside a Surface(level2). Open/close is component
// state; the open transition uses theme.transitions (no hardcoded duration).
//
// Consumes ONLY theme.aphoriQ.* for colors/border/radius — no hardcoded hex or
// px (the only px suffix is applied to the aphoriQ radius/border tokens, exactly
// as the Surface primitive does). Spacing uses MUI spacing units.

import { useState } from "react";
import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Collapse from "@mui/material/Collapse";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import RightOutlined from "@ant-design/icons/RightOutlined";

// Primitive
import Surface from "components/display/Surface";

// ==============================|| COLLAPSIBLE STRIP ||============================== //

export default function CollapsibleStrip({
  title,
  icon: Icon,
  defaultExpanded = false,
  disableUnmount = false,
  meta,
  children,
}) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const [expanded, setExpanded] = useState(defaultExpanded);

  const toggle = () => setExpanded((v) => !v);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggle();
    }
  };

  const mutedIconStyle = {
    color: aq.text.muted,
    display: "flex",
    fontSize: theme.iconSizes.sm,
  };

  return (
    <Box>
      {/* Strip header — clickable, themed via aphoriQ tokens only. */}
      <Stack
        direction="row"
        alignItems="center"
        gap={1.25}
        onClick={toggle}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        sx={{
          px: 2,
          py: 1.25,
          cursor: "pointer",
          backgroundColor: aq.surface.level2,
          borderStyle: "solid",
          borderWidth: aq.border.width.hairline,
          borderColor: aq.border.color,
          borderRadius: `${aq.radius.md}px`,
        }}
      >
        <RightOutlined
          style={{
            ...mutedIconStyle,
            transform: expanded ? "rotate(90deg)" : "rotate(0deg)",
            transition: theme.transitions.create("transform", {
              duration: theme.transitions.duration.shorter,
            }),
          }}
        />
        {Icon && <Icon style={mutedIconStyle} />}
        <Typography variant="body2" sx={{ color: aq.text.muted }}>
          {title}
        </Typography>
        {meta != null && (
          <Typography variant="caption" sx={{ color: aq.text.subtle, ml: "auto" }}>
            {meta}
          </Typography>
        )}
      </Stack>

      {/* Body — themed Surface, revealed with the theme's transition. */}
      <Collapse
        in={expanded}
        timeout={theme.transitions.duration.standard}
        unmountOnExit={!disableUnmount}
      >
        <Surface level="level2" sx={{ mt: 1 }}>
          {children}
        </Surface>
      </Collapse>
    </Box>
  );
}

CollapsibleStrip.propTypes = {
  /** Strip title (muted). */
  title: PropTypes.string.isRequired,
  /** Section icon component (e.g. an ant-design icon). Rendered muted. */
  icon: PropTypes.elementType,
  /** Whether the strip starts expanded. */
  defaultExpanded: PropTypes.bool,
  /** Keep the body mounted while collapsed (default: unmount to drop cost). */
  disableUnmount: PropTypes.bool,
  /** Optional right-aligned meta (e.g. a count). */
  meta: PropTypes.node,
  children: PropTypes.node,
};
