// frontend/src/sections/campaigns/workspace/AddTargetToCampaignModal.jsx

import { useState, useCallback, useMemo } from "react";
import PropTypes from "prop-types";

// MUI
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Modal from "@mui/material/Modal";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";

// Icons
import UserAddOutlined from "@ant-design/icons/UserAddOutlined";

// Project
import MainCard from "components/MainCard";
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";
import { enrollTarget } from "api/campaigns/campaigns";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
  displayWarningSnackbar,
} from "utils/displayError";

// ==============================|| ADD TARGET TO CAMPAIGN MODAL ||============================== //

/**
 * AddTargetToCampaignModal
 *
 * Simple single-contact enrollment modal for Campaign Workspace > Targets tab.
 * Resolves account_id from the selected contact object — no backend changes needed.
 *
 * @param {string}   campaignId         - UUID of the campaign
 * @param {Array}    enrolledContactIds - Already-active contact IDs to exclude from search
 * @param {boolean}  open               - Modal visibility
 * @param {Function} onClose            - Close callback
 * @param {Function} onSuccess          - Called after successful enrollment (triggers revalidation)
 */
export default function AddTargetToCampaignModal({
  campaignId,
  enrolledContactIds = [],
  open,
  onClose,
  onSuccess,
}) {
  const theme = useTheme();

  // ==============================|| STATE ||============================== //

  const [selectedContact, setSelectedContact] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // ==============================|| HANDLERS ||============================== //

  const handleClose = useCallback(() => {
    if (submitting) return;
    setSelectedContact(null);
    onClose();
  }, [submitting, onClose]);

  const handleContactChange = useCallback((_event, contact) => {
    setSelectedContact(contact);
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!selectedContact) return;

    const accountId = selectedContact.account?.id;
    if (!accountId) {
      displayErrorSnackbar({
        message: "Contact has no associated account",
        status: 400,
      });
      return;
    }

    setSubmitting(true);
    try {
      const result = await enrollTarget(campaignId, {
        type: "CONTACT",
        account_id: accountId,
        contact_ids: [selectedContact.id],
        strict: true,
      });

      if (result.success) {
        const contactsEnrolled =
          result.data?.data?.contacts_enrolled ??
          result.data?.contacts_enrolled ??
          0;

        // Nothing was actually enrolled (the single contact is already active in
        // the campaign — a genuinely unreachable/opted-out contact raises 4xx
        // upstream, handled by the error branch below). Never claim success; a
        // "nothing happened" outcome is a warning. The signal is the real
        // contacts_enrolled count, not skip_reason (which the backend only sets
        // when not strict — the modal always sends strict:true).
        if (contactsEnrolled === 0) {
          displayWarningSnackbar(
            "This contact is already active in the campaign",
          );
          setSelectedContact(null);
          onClose();
          return;
        }

        displaySuccessSnackbar("Contact added to campaign");
        setSelectedContact(null);
        onSuccess?.();
        onClose();
      } else {
        displayErrorSnackbar(result);
      }
    } finally {
      setSubmitting(false);
    }
  }, [campaignId, selectedContact, onSuccess, onClose]);

  // ==============================|| CUSTOM RENDER OPTION ||============================== //

  /**
   * Rich dropdown option: name + company · email
   * Keeps getOptionLabel (input display) unchanged globally.
   */
  const renderContactOption = useCallback((props, contact) => {
    const name =
      `${contact.first_name || ""} ${contact.last_name || ""}`.trim() ||
      contact.email ||
      "—";
    const company =
      contact.account?.company_name || contact.account_name || null;
    const email = contact.email || null;

    const meta = [company, email].filter(Boolean).join(" · ");

    return (
      <Box component="li" {...props} key={contact.id}>
        <Stack spacing={0.25}>
          <Typography variant="body2" fontWeight={500} lineHeight={1.3}>
            {name}
          </Typography>
          {meta && (
            <Typography
              variant="caption"
              color="text.secondary"
              lineHeight={1.3}
            >
              {meta}
            </Typography>
          )}
        </Stack>
      </Box>
    );
  }, []);

  // ==============================|| DERIVED ||============================== //

  const isValid = Boolean(selectedContact);

  // Contact preview shown after selection
  const contactPreview = useMemo(() => {
    if (!selectedContact) return null;
    const name =
      `${selectedContact.first_name || ""} ${selectedContact.last_name || ""}`.trim();
    const company =
      selectedContact.account?.company_name ||
      selectedContact.account_name ||
      null;
    const jobTitle = selectedContact.job_title || null;
    const email = selectedContact.email || null;

    return { name, company, jobTitle, email };
  }, [selectedContact]);

  // ==============================|| RENDER ||============================== //

  return (
    <Modal open={open} onClose={handleClose}>
      <MainCard
        title={
          <Stack direction="row" spacing={1} alignItems="center">
            <UserAddOutlined />
            <span>Add Target</span>
          </Stack>
        }
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: { xs: "calc(100% - 32px)", sm: 440 },
          maxHeight: "calc(100vh - 48px)",
          overflowY: "auto",
        }}
        modal
      >
        <Stack spacing={3}>
          {/* Contact search */}
          <Box>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              Search contact
            </Typography>
            <AsyncContactSelect
              value={selectedContact}
              onChange={handleContactChange}
              placeholder="Name, email, job title..."
              excludeIds={enrolledContactIds}
              renderOption={renderContactOption}
              disabled={submitting}
            />
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mt: 0.5, display: "block" }}
            >
              Contacts already enrolled in this campaign are excluded.
            </Typography>
          </Box>

          {/* Selected contact preview */}
          {contactPreview && (
            <Box
              sx={{
                p: 1.5,
                borderRadius: 1,
                border: `1px solid ${theme.palette.divider}`,
                bgcolor: theme.palette.background.default,
              }}
            >
              <Typography variant="subtitle2" fontWeight={600}>
                {contactPreview.name || "—"}
              </Typography>
              {contactPreview.company && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  display="block"
                >
                  {contactPreview.company}
                </Typography>
              )}
              {(contactPreview.jobTitle || contactPreview.email) && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  display="block"
                >
                  {[contactPreview.jobTitle, contactPreview.email]
                    .filter(Boolean)
                    .join(" · ")}
                </Typography>
              )}
            </Box>
          )}

          <Divider />

          {/* Actions */}
          <Stack direction="row" justifyContent="flex-end" spacing={1}>
            <Button
              variant="outlined"
              color="secondary"
              onClick={handleClose}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              variant="contained"
              onClick={handleSubmit}
              disabled={!isValid || submitting}
              startIcon={
                submitting ? (
                  <CircularProgress size={14} color="inherit" />
                ) : (
                  <UserAddOutlined />
                )
              }
            >
              {submitting ? "Adding..." : "Add Target"}
            </Button>
          </Stack>
        </Stack>
      </MainCard>
    </Modal>
  );
}

AddTargetToCampaignModal.propTypes = {
  campaignId: PropTypes.string.isRequired,
  enrolledContactIds: PropTypes.arrayOf(PropTypes.string),
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func,
};
