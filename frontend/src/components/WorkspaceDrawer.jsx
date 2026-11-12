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
//
// « Source / Notes » notes panel, N3 — the coque is a column of TWO zones
// (CoqueZones, both modes): TOP = the injected content, its header and its own
// scroll (unchanged); BOTTOM = the notes panel (NOTES_ZONE_HEIGHT of the
// coque, no resize), its own « Notes » header with its own ×, its own scroll.
// Notes alone → the bottom zone alone, over the whole coque. Each zone reuses
// the coque's CoqueHeader and its scroll pattern (flex child, min-height 0,
// overflow-y auto).

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
import StatusPill from "components/chips/StatusPill";
import ConfirmDialog from "components/dialogs/ConfirmDialog";

// ==============================|| CONSTANTS ||============================== //

/** N3 — the notes zone's share of the coque's height (PO: ≈ 40 %, no resize). */
export const NOTES_ZONE_HEIGHT = "40%";
/** N3 — the notes zone's header title (PO label). */
export const NOTES_PANEL_TITLE = "Notes";
/** N3 — the accessible name of the notes zone's own cross. */
export const CLOSE_NOTES_LABEL = "Close notes";

// ==============================|| COQUE HEADER ||============================== //

// `closeLabel` (N3, optional): the cross's accessible name — the notes zone
// has its own cross beside the top one's « Close drawer ».
function CoqueHeader({ onClose, title, status, statusMap, hideClose, closeLabel = "Close drawer" }) {
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
          spacer keeps the [pill · ×] group flush-right, identical to the
          title-less coque. */}
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
      {/* Right group: optional status pill (read drawers) + the close cross,
          on the title's line. */}
      <Stack direction="row" spacing={1} alignItems="center" sx={{ flexShrink: 0 }}>
        {status && statusMap && <StatusPill status={status} statusMap={statusMap} />}
        {/* hideClose: the injected content renders its own close (a legacy
            in-content header) — omit the coque's own cross. */}
        {!hideClose && (
          <IconButton size="small" onClick={onClose} aria-label={closeLabel}>
            <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
          </IconButton>
        )}
      </Stack>
    </Stack>
  );
}

CoqueHeader.propTypes = {
  onClose: PropTypes.func.isRequired,
  title: PropTypes.string,
  status: PropTypes.string,
  statusMap: PropTypes.object,
  hideClose: PropTypes.bool,
  closeLabel: PropTypes.string,
};

// ==============================|| COQUE ZONES (N3) ||============================== //

// The coque's column, in BOTH modes: the top zone (content) above the notes
// zone. Each zone = [header] + its own scrolling body — the coque's scroll
// pattern (a flex child with min-height:0 so its overflow actually scrolls,
// the header staying pinned).
function CoqueZones({ top, notesNode, onCloseNotes }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const hasTop = top.content != null;
  const hasNotes = notesNode != null;
  // Skip the top header entirely when there's nothing to show in it (cross
  // suppressed AND no title) — the injected content owns its own header then.
  const showTopHeader = !top.hideClose || Boolean(top.title);
  return (
    <>
      {hasTop && (
        <Box
          data-testid="coque-top-zone"
          sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}
        >
          {showTopHeader && (
            <CoqueHeader
              onClose={top.onClose}
              title={top.title}
              status={top.status}
              statusMap={top.statusMap}
              hideClose={top.hideClose}
            />
          )}
          <Box sx={{ p: 2, overflowY: "auto", flex: 1, minHeight: 0 }}>{top.content}</Box>
        </Box>
      )}
      {hasNotes && (
        <Box
          data-testid="coque-notes-zone"
          sx={{
            display: "flex",
            flexDirection: "column",
            minHeight: 0,
            // Below a content: a fixed share of the coque (no resize). Alone:
            // the whole coque.
            flex: hasTop ? `0 0 ${NOTES_ZONE_HEIGHT}` : 1,
            ...(hasTop && {
              borderTopStyle: "solid",
              borderTopWidth: aq.border.width.hairline,
              borderTopColor: aq.border.color,
            }),
          }}
        >
          <CoqueHeader onClose={onCloseNotes} title={NOTES_PANEL_TITLE} closeLabel={CLOSE_NOTES_LABEL} />
          <Box sx={{ p: 2, overflowY: "auto", flex: 1, minHeight: 0 }}>{notesNode}</Box>
        </Box>
      )}
    </>
  );
}

CoqueZones.propTypes = {
  top: PropTypes.shape({
    content: PropTypes.node,
    onClose: PropTypes.func.isRequired,
    title: PropTypes.string,
    status: PropTypes.string,
    statusMap: PropTypes.object,
    hideClose: PropTypes.bool,
  }).isRequired,
  notesNode: PropTypes.node,
  onCloseNotes: PropTypes.func.isRequired,
};

// ==============================|| PUSH PANEL (large) ||============================== //

// The push coque body. Extracted so its aphoriQ token reads happen only when it
// actually MOUNTS — the Collapse below mounts it (via unmountOnExit) solely when
// the drawer is open, so a closed coque never touches theme.aphoriQ.
function CoquePanel({ top, notesNode, onCloseNotes }) {
  const theme = useTheme();
  const aq = theme.aphoriQ;
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
        // N3 — with the notes zone the coque takes that whole height, so the
        // zones' shares resolve against it.
        ...(notesNode != null && { height: `calc(100vh - ${headerOffset}px - ${theme.spacing(3)})` }),
      }}
    >
      <CoqueZones top={top} notesNode={notesNode} onCloseNotes={onCloseNotes} />
    </Box>
  );
}

CoquePanel.propTypes = {
  top: CoqueZones.propTypes.top,
  notesNode: PropTypes.node,
  onCloseNotes: PropTypes.func.isRequired,
};

// ==============================|| UNSAVED CHANGES CONFIRMATION (2.2) ||============================== //

// « Source / Notes » 2.2 — the coque's guard asks before discarding a MODIFIED
// content (WorkspaceDrawerContext.pendingDiscard), with the shared
// ConfirmDialog (2.1). Rendered by the always-mounted visual coque, so the
// provider stays state-only.
function DiscardConfirmation() {
  const { pendingDiscard, confirmDiscard, cancelDiscard } = useWorkspaceDrawer();
  return (
    <ConfirmDialog
      open={Boolean(pendingDiscard)}
      title="Discard your changes?"
      message="What you entered in this panel will be lost."
      cancelLabel="Keep editing"
      confirmLabel="Discard"
      confirmColor="error"
      confirmTestId="confirm-discard-changes"
      onCancel={cancelDiscard}
      onConfirm={confirmDiscard}
    />
  );
}

// ==============================|| WORKSPACE DRAWER (COQUE) ||============================== //

export default function WorkspaceDrawer() {
  const theme = useTheme();
  const aq = theme.aphoriQ;
  const isNarrow = useMediaQuery(theme.breakpoints.down("lg"));
  const {
    isCoqueOpen, content, title, status, statusMap, hideClose, closeDrawer,
    notesPanel, closeNotesPanel, closeCoque,
  } = useWorkspaceDrawer();
  const top = { content, onClose: closeDrawer, title, status, statusMap, hideClose };
  const notesNode = notesPanel?.node ?? null;

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
      <>
      <DiscardConfirmation />
      <Drawer
        anchor="right"
        open={isCoqueOpen}
        variant="temporary"
        // N3: the backdrop closes the WHOLE coque (the top's guard applies).
        onClose={closeCoque}
        disableEnforceFocus
        PaperProps={
          isCoqueOpen
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
                  // N3: the two zones share the paper's column — MUI's
                  // Drawer paper is already a flex column.
                },
              }
            : undefined
        }
      >
        <CoqueZones top={top} notesNode={notesNode} onCloseNotes={closeNotesPanel} />
      </Drawer>
      </>
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
    <>
    <DiscardConfirmation />
    <Box
      sx={{
        position: "sticky",
        top: headerOffset,
        alignSelf: "flex-start",
        flexShrink: 0,
      }}
    >
      <Collapse orientation="horizontal" in={isCoqueOpen} unmountOnExit>
        <CoquePanel top={top} notesNode={notesNode} onCloseNotes={closeNotesPanel} />
      </Collapse>
    </Box>
    </>
  );
}
