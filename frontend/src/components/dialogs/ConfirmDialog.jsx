// frontend/src/components/dialogs/ConfirmDialog.jsx
//
// Sprint « Source / Notes » 2.1 (TD-120) — THE shared confirmation dialog of
// the repo (there was none: confirmations were composed inline). Extracted
// from the Activity header's light cancel confirmation (MUI Dialog, xs,
// fullWidth: a title, a neutral cancel action, a coloured confirm action),
// with an optional message and an optional body.
//
// Reused by:
//   - the Activity header — the cancel confirmation (ActivityHeader);
//   - the workspace coque's « unsaved changes » guard (2.2).
//
// Theme only (MUI palette colours through `confirmColor`); no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";

// MUI
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";

export default function ConfirmDialog({
  open,
  title,
  message,
  children,
  confirmLabel,
  cancelLabel,
  confirmColor = "primary",
  confirmTestId,
  confirmDisabled = false,
  onConfirm,
  onCancel,
}) {
  const hasBody = Boolean(message) || children != null;
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      fullWidth
      maxWidth="xs"
      PaperProps={{ "data-testid": "confirm-dialog" }}
    >
      <DialogTitle>{title}</DialogTitle>
      {hasBody && (
        <DialogContent>
          {message && <DialogContentText>{message}</DialogContentText>}
          {children}
        </DialogContent>
      )}
      <DialogActions>
        <Button color="inherit" onClick={onCancel}>
          {cancelLabel}
        </Button>
        <Button
          color={confirmColor}
          onClick={onConfirm}
          disabled={confirmDisabled}
          data-testid={confirmTestId}
        >
          {confirmLabel}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

ConfirmDialog.propTypes = {
  /** Open state. */
  open: PropTypes.bool.isRequired,
  /** The question asked (dialog title). */
  title: PropTypes.node.isRequired,
  /** Optional explanatory text under the title. */
  message: PropTypes.node,
  /** Optional extra body (rendered after the message). */
  children: PropTypes.node,
  /** Label of the confirm action. */
  confirmLabel: PropTypes.node.isRequired,
  /** Label of the cancel action (also fired by Escape / backdrop). */
  cancelLabel: PropTypes.node.isRequired,
  /** MUI palette colour of the confirm action (e.g. "error", "warning"). */
  confirmColor: PropTypes.string,
  /** Optional data-testid of the confirm action. */
  confirmTestId: PropTypes.string,
  /** Disables the confirm action (e.g. while saving). */
  confirmDisabled: PropTypes.bool,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};
