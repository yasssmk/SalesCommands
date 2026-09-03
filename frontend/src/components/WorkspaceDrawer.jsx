// frontend/src/components/WorkspaceDrawer.jsx
//
// B3.5.1 — the visual coque of the single workspace drawer. It reads the
// injected content + open state from useWorkspaceDrawer (B3.5.0) and renders it:
//
//   - large screen: PUSH — an inline flex column BESIDE the main content (the
//     screen splits in two; no overlay/backdrop). Because it is a flex sibling
//     of the main column (in WorkspaceLayout), its top aligns with the top of
//     the workspace header.
//   - narrow screen (down 'lg'): OVERLAY — a temporary MUI Drawer with a
//     backdrop, so a push would leave too little room.
//
// Fully themed via aphoriQ (surface / border) + iconSizes; width = the single
// theme.aphoriQ.drawer.width token. No hardcoded hex/px.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import useMediaQuery from "@mui/material/useMediaQuery";
import Box from "@mui/material/Box";
import Collapse from "@mui/material/Collapse";
import Drawer from "@mui/material/Drawer";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";

// icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// project imports
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";

// ==============================|| COQUE HEADER ||============================== //

function CoqueHeader({ onClose }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <Stack
      direction="row"
      justifyContent="flex-end"
      alignItems="center"
      sx={{
        px: 2,
        py: 1.5,
        borderBottomStyle: "solid",
        borderBottomWidth: aq.border.width.hairline,
        borderBottomColor: aq.border.color,
      }}
    >
      <IconButton size="small" onClick={onClose} aria-label="Close drawer">
        <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
      </IconButton>
    </Stack>
  );
}

CoqueHeader.propTypes = { onClose: PropTypes.func.isRequired };

// ==============================|| PUSH PANEL (large) ||============================== //

// The push coque body. Extracted so its aphoriQ token reads happen only when it
// actually MOUNTS — the Collapse below mounts it (via unmountOnExit) solely when
// the drawer is open, so a closed coque never touches theme.aphoriQ.
function CoquePanel({ content, onClose }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <Box
      sx={{
        width: aq.drawer.width,
        backgroundColor: aq.surface.level2,
        borderLeftStyle: "solid",
        borderLeftWidth: aq.border.width.hairline,
        borderLeftColor: aq.border.color,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <CoqueHeader onClose={onClose} />
      <Box sx={{ p: 2, overflowY: "auto", flex: 1 }}>{content}</Box>
    </Box>
  );
}

CoquePanel.propTypes = {
  content: PropTypes.node,
  onClose: PropTypes.func.isRequired,
};

// ==============================|| WORKSPACE DRAWER (COQUE) ||============================== //

export default function WorkspaceDrawer() {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const isNarrow = useMediaQuery(theme.breakpoints.down("lg"));
  const { isOpen, content, closeDrawer } = useWorkspaceDrawer();

  // ---- Narrow: OVERLAY (temporary Drawer + backdrop) ----
  // The temporary MUI Drawer slides in/out natively via theme.transitions when
  // `open` toggles. PaperProps (and the children) resolve aphoriQ tokens only
  // while open — a closed overlay never touches theme.aphoriQ.
  if (isNarrow) {
    return (
      <Drawer
        anchor="right"
        open={isOpen}
        variant="temporary"
        onClose={closeDrawer}
        PaperProps={
          isOpen
            ? {
                sx: {
                  width: { xs: "100%", sm: aq.drawer.width },
                  backgroundColor: aq.surface.level2,
                },
              }
            : undefined
        }
      >
        <CoqueHeader onClose={closeDrawer} />
        <Box sx={{ p: 2, overflowY: "auto" }}>{content}</Box>
      </Drawer>
    );
  }

  // ---- Large: PUSH (inline flex column, no overlay) ----
  // Slide open/closed instead of mounting sharply: a horizontal MUI Collapse
  // animates the coque's WIDTH (0 ↔ drawer.width), so the main column shrinks
  // smoothly and the panel reveals from the right. Collapse drives the
  // transition from theme.transitions (duration.standard / easing) — no
  // hardcoded duration or easing here. `unmountOnExit` mounts CoquePanel only
  // while open, so a closed coque renders null (and reads no aphoriQ tokens).
  return (
    <Collapse orientation="horizontal" in={isOpen} unmountOnExit sx={{ flexShrink: 0 }}>
      <CoquePanel content={content} onClose={closeDrawer} />
    </Collapse>
  );
}
