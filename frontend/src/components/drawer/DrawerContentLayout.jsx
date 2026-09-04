// frontend/src/components/drawer/DrawerContentLayout.jsx
//
// SE-b — the SHARED scaffold for any drawer's injected content (edit activity
// today, a contact card tomorrow, …). It renders an INVARIANT structure:
//
//   - a bold h3 title at the top (themed);
//   - ONE content box grounded on the page background (background.default) with
//     radius lg + a hairline border — the single box that holds the field groups;
//   - a global Save / Cancel action row, right-aligned.
//
// It does NOT render the coque or the close cross — those belong to
// WorkspaceDrawer (CoqueHeader). The cross sits in that separate top strip
// (WorkspaceDrawer.jsx CoqueHeader, px:2 / py:1.5), so this title shares the same
// horizontal inset (the content box below the cross); pixel-aligning it onto the
// cross's own line would require changing the coque and is out of scope here.
//
// 100% theme tokens (radius / border / typography / spacing) — no hardcoded
// hex/px, no MainCard.

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

export default function DrawerContentLayout({
  title,
  onSave,
  onCancel,
  saveDisabled = false,
  saveLabel = "Save",
  cancelLabel = "Cancel",
  children,
}) {
  const aq = useTheme().aphoriQ;

  return (
    <Stack spacing={2}>
      {/* Title is OPTIONAL: when the coque renders it in its header (Option A),
          the layout omits it to avoid a duplicate. */}
      {title ? (
        <Typography variant="h3" component="h2" sx={{ fontWeight: "bold" }} data-testid="drawer-title">
          {title}
        </Typography>
      ) : null}

      <Box
        data-testid="drawer-content-box"
        sx={{
          backgroundColor: "background.default",
          borderRadius: `${aq.radius.lg}px`,
          border: `${aq.border.width.hairline}px solid ${aq.border.color}`,
          p: 2,
        }}
      >
        {children}
      </Box>

      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
        <Button variant="text" color="inherit" onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button variant="contained" onClick={onSave} disabled={saveDisabled}>
          {saveLabel}
        </Button>
      </Box>
    </Stack>
  );
}

DrawerContentLayout.propTypes = {
  /** Optional bold h3 title. Omit when the coque renders the title (Option A). */
  title: PropTypes.string,
  /** Global save handler. */
  onSave: PropTypes.func.isRequired,
  /** Global cancel handler. */
  onCancel: PropTypes.func.isRequired,
  /** Disable the Save button (e.g. invalid or pristine form). */
  saveDisabled: PropTypes.bool,
  saveLabel: PropTypes.string,
  cancelLabel: PropTypes.string,
  /** The field groups (the single content box's children). */
  children: PropTypes.node,
};
