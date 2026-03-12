// frontend/src/sections/campaigns/workspace/CampaignCompletionModal.jsx
/**
 * CampaignCompletionModal — shown after completeCampaign() returns requires_confirmation=true.
 *
 * Displays contacts that still have PLANNED activities.
 * User can select contacts to transfer to the TARGETED campaign (singleton).
 *
 * TODO: "Add to Follow-up Campaign" button will bulk-add selected contacts
 *       to the client's singleton TARGETED campaign once that feature is implemented.
 *       For now it renders a disabled button with an explanatory tooltip.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useEffect } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// icons
import { InfoCircleOutlined } from "@ant-design/icons";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CAMPAIGN COMPLETION MODAL ||============================== //

export default function CampaignCompletionModal({
  open,
  onClose,
  openContacts,
  onCompleteWithoutFollowup,
}) {
  const [selectedIds, setSelectedIds] = useState([]);

  useEffect(() => {
    if (open) {
      setSelectedIds(openContacts.map((c) => c.campaign_contact_id));
    }
  }, [open, openContacts]);

  const [submitting, setSubmitting] = useState(false);

  const allSelected =
    selectedIds.length === openContacts.length && openContacts.length > 0;

  const handleToggleAll = useCallback(() => {
    setSelectedIds(
      allSelected ? [] : openContacts.map((c) => c.campaign_contact_id),
    );
  }, [allSelected, openContacts]);

  const handleToggle = useCallback((id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }, []);

  const handleCompleteWithoutFollowup = useCallback(async () => {
    setSubmitting(true);
    try {
      await onCompleteWithoutFollowup();
      displaySuccessSnackbar("Campaign completed");
      onClose();
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setSubmitting(false);
    }
  }, [onCompleteWithoutFollowup, onClose]);

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <Typography variant="h5">Complete campaign</Typography>
          <Chip
            label={`${openContacts.length} open contact${openContacts.length !== 1 ? "s" : ""}`}
            size="small"
            color="warning"
            variant="outlined"
          />
        </Stack>
      </DialogTitle>

      <DialogContent dividers sx={{ p: 0 }}>
        {/* Header info */}
        <Box sx={{ px: 3, py: 2, bgcolor: "warning.lighter" }}>
          <Typography variant="body2" color="warning.dark">
            The following contacts still have planned activities. You can add
            them to the Follow-up Campaign to continue outreach, or complete
            without follow-up.
          </Typography>
        </Box>

        {/* Select all */}
        <Box sx={{ px: 3, pt: 1.5, pb: 0.5 }}>
          <FormControlLabel
            control={
              <Checkbox
                checked={allSelected}
                indeterminate={
                  selectedIds.length > 0 &&
                  selectedIds.length < openContacts.length
                }
                onChange={handleToggleAll}
                size="small"
              />
            }
            label={
              <Typography variant="body2" fontWeight={600}>
                Select all
              </Typography>
            }
          />
        </Box>

        <Divider />

        {/* Contact list */}
        <Stack divider={<Divider />}>
          {openContacts.map((contact) => {
            const isSelected = selectedIds.includes(
              contact.campaign_contact_id,
            );
            return (
              <Box
                key={contact.campaign_contact_id}
                sx={{
                  px: 3,
                  py: 1.5,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  bgcolor: isSelected ? "action.hover" : "transparent",
                  transition: "background-color 0.15s",
                }}
              >
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={isSelected}
                      onChange={() => handleToggle(contact.campaign_contact_id)}
                      size="small"
                    />
                  }
                  label={
                    <Stack spacing={0.25}>
                      <Typography variant="body2" fontWeight={500}>
                        {contact.contact_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {contact.account_name}
                      </Typography>
                    </Stack>
                  }
                  sx={{ m: 0 }}
                />

                {/* Callback date badge if present */}
                {contact.callback_date && (
                  <Chip
                    label={`CB ${contact.callback_date}`}
                    size="small"
                    color="info"
                    variant="outlined"
                    sx={{ fontSize: "0.7rem" }}
                  />
                )}
              </Box>
            );
          })}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2, gap: 1 }}>
        {/* Complete without follow-up */}
        <Button
          onClick={handleCompleteWithoutFollowup}
          color="inherit"
          size="small"
          disabled={submitting}
        >
          Complete without follow-up
        </Button>

        <Box sx={{ flex: 1 }} />

        {/* TODO: TARGETED singleton — implement when TARGETED campaign feature lands */}
        <Tooltip
          title="Follow-up Campaign feature coming soon. Select contacts and they will be added to your ongoing Follow-up Campaign."
          placement="top"
          arrow
        >
          <span>
            <Button
              variant="contained"
              size="small"
              disabled
              endIcon={<InfoCircleOutlined />}
            >
              Add to Follow-up Campaign
              {selectedIds.length > 0 && ` (${selectedIds.length})`}
            </Button>
          </span>
        </Tooltip>
      </DialogActions>
    </Dialog>
  );
}

CampaignCompletionModal.propTypes = {
  /** Whether the modal is open */
  open: PropTypes.bool.isRequired,
  /** Close handler */
  onClose: PropTypes.func.isRequired,
  /** Contacts with remaining planned activities */
  openContacts: PropTypes.arrayOf(
    PropTypes.shape({
      campaign_contact_id: PropTypes.string,
      contact_id: PropTypes.string,
      contact_name: PropTypes.string,
      account_id: PropTypes.string,
      account_name: PropTypes.string,
      callback_date: PropTypes.string,
    }),
  ).isRequired,
  /** Called when user clicks "Complete without follow-up" */
  onCompleteWithoutFollowup: PropTypes.func.isRequired,
};
