// frontend/src/sections/accounts/signals/AlertSignalReject.jsx
/**
 * AlertSignalReject — confirmation dialog for rejecting a PENDING signal.
 *
 * Body (optional sent to backend): { reason: string }
 *
 * Follows the same pattern as AlertActivityCancel / AlertActivityDelete
 * in the activities module: small Dialog with a destructive confirm button
 * and an optional free-text reason field.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useEffect } from "react";

// material-ui
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// ant-design icons
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";

// project imports
import { rejectSignal } from "api/accounts/signals";
import { displayErrorSnackbar } from "utils/displayError";

// ==============================|| ALERT SIGNAL REJECT ||============================== //

/**
 * AlertSignalReject
 *
 * @param {boolean}               open       - Dialog open state
 * @param {Function}              onClose    - Called on cancel / backdrop click
 * @param {Function}              onSuccess  - Called after successful rejection
 * @param {Object|null}           signal     - Signal to reject
 * @param {'qualification'|'tech-stack'} signalType
 */
export default function AlertSignalReject({
  open,
  onClose,
  onSuccess,
  signal,
  signalType,
}) {
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // ==============================|| RESET ON OPEN ||============================== //

  useEffect(() => {
    if (open) {
      setReason("");
      setSubmitting(false);
    }
  }, [open]);

  // ==============================|| HANDLERS ||============================== //

  const handleConfirm = async () => {
    if (!signal || !signalType) return;

    setSubmitting(true);

    const result = await rejectSignal(
      signalType,
      signal.id,
      reason.trim() || null,
    );

    setSubmitting(false);

    if (result.success) {
      onSuccess();
    } else {
      displayErrorSnackbar(result.error || "Failed to reject signal");
    }
  };

  const handleClose = () => {
    if (submitting) return;
    onClose();
  };

  // ==============================|| DERIVED ||============================== //

  const fieldLabel =
    signal?.field_name_display || signal?.field_name || "this signal";
  const techSuffix = signal?.tech_name ? ` · ${signal.tech_name}` : "";

  // ==============================|| RENDER ||============================== //

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="xs"
      fullWidth
      aria-labelledby="signal-reject-dialog-title"
    >
      <DialogTitle id="signal-reject-dialog-title">
        <Stack direction="row" spacing={1.5} alignItems="center">
          <CloseCircleOutlined style={{ fontSize: 20, color: "#ff4d4f" }} />
          <Typography variant="h5">Reject Signal</Typography>
        </Stack>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2.5 }}>
        <Stack spacing={2}>
          {/* Confirmation message */}
          <Typography variant="body2" color="text.secondary">
            You are about to reject{" "}
            <Typography
              component="span"
              variant="body2"
              fontWeight={600}
              color="text.primary"
            >
              {fieldLabel}
              {techSuffix}
            </Typography>
            . The signal will be marked as <strong>Rejected</strong> and removed
            from active signal lists.
          </Typography>

          {/* Optional reason */}
          <TextField
            fullWidth
            size="small"
            id="reject-reason"
            name="reason"
            label="Reason (optional)"
            placeholder="Why is this signal being rejected?"
            multiline
            minRows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={submitting}
            inputProps={{ maxLength: 500 }}
            helperText={`${reason.length}/500`}
          />
        </Stack>
      </DialogContent>

      <Divider />

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button onClick={handleClose} disabled={submitting} color="inherit">
          Cancel
        </Button>
        <Button
          variant="contained"
          color="error"
          onClick={handleConfirm}
          disabled={submitting}
          startIcon={
            submitting ? (
              <CircularProgress size={14} color="inherit" />
            ) : (
              <CloseCircleOutlined />
            )
          }
        >
          {submitting ? "Rejecting…" : "Reject Signal"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ==============================|| PROP TYPES ||============================== //

AlertSignalReject.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    field_name: PropTypes.string,
    field_name_display: PropTypes.string,
    tech_name: PropTypes.string,
  }),
  signalType: PropTypes.oneOf(["qualification", "tech-stack"]),
};
