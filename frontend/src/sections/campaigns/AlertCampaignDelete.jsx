// frontend/src/sections/campaigns/AlertCampaignDelete.jsx
/**
 * Alert Campaign Delete Component
 *
 * Confirmation dialog for deleting a campaign.
 * Follows AlertActivityDelete pattern.
 */

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// material-ui
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import CircularProgress from "@mui/material/CircularProgress";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";

// icons
import WarningFilled from "@ant-design/icons/WarningFilled";

// project imports
import { deleteCampaign } from "api/campaigns/campaigns";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

// ==============================|| ALERT CAMPAIGN DELETE ||============================== //

/**
 * AlertCampaignDelete Component
 *
 * @param {boolean} open - Dialog open state
 * @param {Function} onClose - Close dialog callback
 * @param {Object} campaign - Campaign to delete
 * @param {Function} onSuccess - Success callback after deletion
 */
export default function AlertCampaignDelete({
  open,
  onClose,
  campaign,
  onSuccess,
}) {
  const [deleting, setDeleting] = useState(false);

  const handleDelete = async () => {
    if (!campaign?.id) return;

    setDeleting(true);

    try {
      const result = await deleteCampaign(campaign.id);

      if (result.success) {
        displaySuccessSnackbar("Campaign deleted successfully");
        onSuccess?.(campaign);
        onClose();
      } else {
        displayErrorSnackbar({
          message: result.error || "Failed to delete campaign",
          status: result.status,
        });
      }
    } catch (err) {
      displayErrorSnackbar({
        message: err?.message || "An unexpected error occurred",
        status: 500,
      });
    } finally {
      setDeleting(false);
    }
  };

  const handleClose = () => {
    if (!deleting) {
      onClose();
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="xs"
      fullWidth
      aria-labelledby="alert-campaign-delete-title"
      aria-describedby="alert-campaign-delete-description"
    >
      <DialogTitle id="alert-campaign-delete-title">
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <WarningFilled style={{ fontSize: 24, color: "#faad14" }} />
          <Typography variant="h5">Delete Campaign</Typography>
        </Box>
      </DialogTitle>

      <DialogContent>
        <DialogContentText id="alert-campaign-delete-description">
          Are you sure you want to delete the campaign{" "}
          <Typography component="span" fontWeight={600} color="text.primary">
            &quot;{campaign?.name}&quot;
          </Typography>
          ?
        </DialogContentText>
        <DialogContentText sx={{ mt: 1.5, color: "text.secondary" }}>
          This action cannot be undone. All associated accounts and activities
          will be removed.
        </DialogContentText>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2.5 }}>
        <Button color="secondary" onClick={handleClose} disabled={deleting}>
          Cancel
        </Button>
        <Button
          variant="contained"
          color="error"
          onClick={handleDelete}
          disabled={deleting}
          startIcon={
            deleting ? <CircularProgress size={16} color="inherit" /> : null
          }
        >
          {deleting ? "Deleting..." : "Delete"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

AlertCampaignDelete.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  campaign: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
  }),
  onSuccess: PropTypes.func,
};
