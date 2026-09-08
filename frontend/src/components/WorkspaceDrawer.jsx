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

function CoqueHeader({ onClose, title, hideClose }) {
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
      {/* hideClose: the injected content renders its own close (the Objective
          detail carries the × in its header) — omit the coque's own cross. */}
      {!hideClose && (
        <IconButton size="small" onClick={onClose} aria-label="Close drawer">
          <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
        </IconButton>
      )}
    </Stack>
  );
}

CoqueHeader.propTypes = {
  onClose: PropTypes.func.isRequired,
  title: PropTypes.string,
  hideClose: PropTypes.bool,
};

// ==============================|| PUSH PANEL (large) ||============================== //

// The push coque body. Extracted so its aphoriQ token reads happen only when it
// actually MOUNTS — the Collapse below mounts it (via unmountOnExit) solely when
// the drawer is open, so a closed coque never touches theme.aphoriQ.
function CoquePanel({ content, onClose, title, hideClose }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  // Skip the header row entirely when there's nothing to show in it (cross
  // suppressed AND no title) — the injected content owns its own header then.
  const showHeader = !hideClose || Boolean(title);
  // Sticky offset = the height of the FIXED app-bar above the content
  // (theme.mixins.toolbar.minHeight — the same token the layout's Toolbar spacer
  // reserves). The breadcrumb below it is in normal flow (it scrolls away), so it
  // is NOT part of the offset. No magic px: the value comes from the theme token.
  const headerOffset = theme.mixins.toolbar.minHeight;
  return (
    <Box
      data-testid="coque-panel"
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
        // The STICKY pin lives on the wrapper OUTSIDE the Collapse (see the push
        // branch below) — a sticky here is clipped to the Collapse's tight
        // height wrapper and can't move. This panel only bounds its own height to
        // the viewport so a long drawer scrolls INTERNALLY (its body, below).
        maxHeight: `calc(100vh - ${headerOffset}px - ${theme.spacing(3)})`,
      }}
    >
      {showHeader && <CoqueHeader onClose={onClose} title={title} hideClose={hideClose} />}
      {/* min-height:0 lets this flex child shrink below its content so the
          internal overflow actually scrolls (header stays pinned). */}
      <Box sx={{ p: 2, overflowY: "auto", flex: 1, minHeight: 0 }}>{content}</Box>
    </Box>
  );
}

CoquePanel.propTypes = {
  content: PropTypes.node,
  onClose: PropTypes.func.isRequired,
  title: PropTypes.string,
  hideClose: PropTypes.bool,
};

// ==============================|| WORKSPACE DRAWER (COQUE) ||============================== //

export default function WorkspaceDrawer() {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const isNarrow = useMediaQuery(theme.breakpoints.down("lg"));
  const { isOpen, content, title, hideClose, closeDrawer } = useWorkspaceDrawer();

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
        {(!hideClose || Boolean(title)) && (
          <CoqueHeader onClose={closeDrawer} title={title} hideClose={hideClose} />
        )}
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
  //
  // STICKY lives on this WRAPPER, OUTSIDE the Collapse. The whole page scrolls in
  // the window; this Box is a flex child of the tall content-coque-row, so its
  // containing block is that row → position:sticky has room to pin the drawer
  // under the fixed header while the content scrolls behind it. (A sticky INSIDE
  // the Collapse is clipped by its height:100% wrapper — the earlier bug.)
  const headerOffset = theme.mixins.toolbar.minHeight;
  return (
    <Box
      sx={{
        position: "sticky",
        top: headerOffset,
        alignSelf: "flex-start",
        flexShrink: 0,
      }}
    >
      <Collapse orientation="horizontal" in={isOpen} unmountOnExit>
        <CoquePanel content={content} onClose={closeDrawer} title={title} hideClose={hideClose} />
      </Collapse>
    </Box>
  );
}
