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
import Typography from "@mui/material/Typography";

// icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// project imports
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";

// ==============================|| COQUE HEADER ||============================== //

function CoqueHeader({ onClose, title }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <Stack
      direction="row"
      justifyContent="space-between"
      alignItems="center"
      spacing={1}
      sx={{
        px: 2,
        py: 1.5,
        borderBottomStyle: "solid",
        borderBottomWidth: aq.border.width.hairline,
        borderBottomColor: aq.border.color,
      }}
    >
      {/* Optional title (Option A): shares the cross's line. Absent → an empty
          spacer keeps the cross flush-right, identical to the title-less coque. */}
      {title ? (
        <Typography
          variant="h3"
          component="h2"
          noWrap
          sx={{ fontWeight: "bold", minWidth: 0 }}
          data-testid="coque-title"
        >
          {title}
        </Typography>
      ) : (
        <Box />
      )}
      <IconButton size="small" onClick={onClose} aria-label="Close drawer">
        <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
      </IconButton>
    </Stack>
  );
}

CoqueHeader.propTypes = { onClose: PropTypes.func.isRequired, title: PropTypes.string };

// ==============================|| PUSH PANEL (large) ||============================== //

// The push coque body. Extracted so its aphoriQ token reads happen only when it
// actually MOUNTS — the Collapse below mounts it (via unmountOnExit) solely when
// the drawer is open, so a closed coque never touches theme.aphoriQ.
function CoquePanel({ content, onClose, title }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  return (
    <Box
      sx={{
        width: aq.drawer.width,
        backgroundColor: aq.surface.level2,
        // A detached, rounded floating card: the same radius as the page boxes
        // (header, Context card) + a full hairline border, with a bottom/right
        // margin so the rounded corners clear those edges. NO top margin — the
        // coque shares the flex-start row line (DashboardLayout content-coque-row),
        // so its top aligns with the header card top. Left stays near the main
        // column (which carries its own padding).
        border: `${aq.border.width.hairline}px solid ${aq.border.color}`,
        borderRadius: `${aq.radius.lg}px`,
        mb: 1.5,
        mr: 1.5,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <CoqueHeader onClose={onClose} title={title} />
      <Box sx={{ p: 2, overflowY: "auto", flex: 1 }}>{content}</Box>
    </Box>
  );
}

CoquePanel.propTypes = {
  content: PropTypes.node,
  onClose: PropTypes.func.isRequired,
  title: PropTypes.string,
};

// ==============================|| WORKSPACE DRAWER (COQUE) ||============================== //

export default function WorkspaceDrawer() {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const isNarrow = useMediaQuery(theme.breakpoints.down("lg"));
  const { isOpen, content, title, closeDrawer } = useWorkspaceDrawer();

  // ---- Narrow: OVERLAY (temporary Drawer + backdrop) ----
  // The temporary MUI Drawer slides in/out natively via theme.transitions when
  // `open` toggles. PaperProps (and the children) resolve aphoriQ tokens only
  // while open — a closed overlay never touches theme.aphoriQ.
  //
  // disableEnforceFocus: MUI-X pickers (DatePicker/TimePicker) render their
  // calendar in a Popper portaled to <body>, OUTSIDE this temporary Drawer's
  // focus trap. With the default enforceFocus the trap yanks focus back and the
  // calendar clicks never register (it appears to stay open / not commit). We
  // relax focus enforcement so the portaled picker is usable; closing via the
  // backdrop or the cross is unaffected.
  if (isNarrow) {
    return (
      <Drawer
        anchor="right"
        open={isOpen}
        variant="temporary"
        onClose={closeDrawer}
        disableEnforceFocus
        PaperProps={
          isOpen
            ? {
                sx: {
                  width: { xs: "100%", sm: aq.drawer.width },
                  backgroundColor: aq.surface.level2,
                  // Match the push card: rounded + full hairline border, detached
                  // with a margin. The paper is full-height, so trim its height by
                  // the top+bottom margin (theme.spacing(3) = 2×1.5) — token math,
                  // no hardcoded px — to keep the rounded corners clear of the edges.
                  border: `${aq.border.width.hairline}px solid ${aq.border.color}`,
                  borderRadius: `${aq.radius.lg}px`,
                  m: 1.5,
                  height: `calc(100% - ${theme.spacing(3)})`,
                },
              }
            : undefined
        }
      >
        <CoqueHeader onClose={closeDrawer} title={title} />
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
      <CoquePanel content={content} onClose={closeDrawer} title={title} />
    </Collapse>
  );
}
