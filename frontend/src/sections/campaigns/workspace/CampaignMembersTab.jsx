// frontend/src/sections/campaigns/workspace/CampaignMembersTab.jsx
/**
 * Campaign Members Tab — Owner + Executor display and management.
 *
 * Data comes directly from the campaign object (no separate API call).
 * Only the executor can be changed via PATCH /campaigns/{id}/.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";

// material-ui
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import InputLabel from "@mui/material/InputLabel";
import Modal from "@mui/material/Modal";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import MainCard from "components/MainCard";
import AsyncUserSelect from "components/AsyncSelection/AsyncUserSelect";

// api
import { updateCampaign } from "api/campaigns/campaigns";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// icons
import CrownOutlined from "@ant-design/icons/CrownOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";
import EditOutlined from "@ant-design/icons/EditOutlined";
import DeleteOutlined from "@ant-design/icons/DeleteOutlined";

// ==============================|| HELPERS ||============================== //

function getInitials(user) {
  if (!user) return "?";
  const name =
    `${user.first_name || ""} ${user.last_name || ""}`.trim() ||
    user.email ||
    "";
  return (
    name
      .split(" ")
      .map((n) => n[0] || "")
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?"
  );
}

function getDisplayName(user) {
  if (!user) return "—";
  return (
    `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.email
  );
}

// ==============================|| MEMBER ROW ||============================== //

function MemberRow({ icon: Icon, label, user, isPrimary, action }) {
  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 1.5,
        border: "1px solid",
        borderColor: "grey.200",
        bgcolor: "background.paper",
      }}
    >
      <Stack direction="row" spacing={2} alignItems="center">
        <Avatar
          sx={{
            width: 40,
            height: 40,
            bgcolor: isPrimary ? "warning.main" : "primary.main",
            fontSize: "0.875rem",
            fontWeight: 600,
          }}
        >
          {user ? getInitials(user) : <Icon style={{ fontSize: 18 }} />}
        </Avatar>

        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="subtitle2" noWrap>
              {user ? (
                getDisplayName(user)
              ) : (
                <Typography
                  component="span"
                  variant="subtitle2"
                  color="text.disabled"
                >
                  Not assigned
                </Typography>
              )}
            </Typography>
            <Chip
              label={label}
              size="small"
              color={isPrimary ? "warning" : "primary"}
              variant="outlined"
              sx={{ height: 20, fontSize: "0.675rem" }}
            />
          </Stack>
          {user?.email && (
            <Typography variant="caption" color="text.secondary" noWrap>
              {user.email}
            </Typography>
          )}
        </Box>

        {action}
      </Stack>
    </Box>
  );
}

MemberRow.propTypes = {
  icon: PropTypes.elementType.isRequired,
  label: PropTypes.string.isRequired,
  user: PropTypes.object,
  isPrimary: PropTypes.bool,
  action: PropTypes.node,
};

// ==============================|| ASSIGN EXECUTOR MODAL ||============================== //

function AssignExecutorModal({
  open,
  onClose,
  campaignId,
  currentExecutor,
  ownerId,
  onSuccess,
}) {
  const [selectedUser, setSelectedUser] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const handleClose = useCallback(() => {
    setSelectedUser(null);
    onClose();
  }, [onClose]);

  const handleSubmit = useCallback(async () => {
    if (!selectedUser?.id) {
      displayErrorSnackbar("Please select a user");
      return;
    }

    setSubmitting(true);
    try {
      const result = await updateCampaign(campaignId, {
        executor_id: selectedUser.id,
      });

      if (result.success) {
        displaySuccessSnackbar(
          `Executor updated to ${getDisplayName(selectedUser)}`,
        );
        onSuccess();
        handleClose();
      } else {
        displayErrorSnackbar(result);
      }
    } finally {
      setSubmitting(false);
    }
  }, [selectedUser, campaignId, onSuccess, handleClose]);

  return (
    <Modal open={open} onClose={handleClose}>
      <MainCard
        title={currentExecutor ? "Change Executor" : "Assign Executor"}
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: { xs: "calc(100% - 32px)", sm: 440 },
        }}
        modal
      >
        <Stack spacing={3}>
          <Box>
            <InputLabel sx={{ mb: 1 }}>Select Executor *</InputLabel>
            <AsyncUserSelect
              value={selectedUser}
              onChange={(_, user) => setSelectedUser(user)}
              placeholder="Search by name or email..."
              disabled={submitting}
              filters={{ is_active: true }}
              filterOptions={(options) =>
                options.filter((u) => u.id !== ownerId)
              }
            />
          </Box>

          <Divider />

          <Stack direction="row" justifyContent="flex-end" spacing={1.5}>
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
              disabled={!selectedUser || submitting}
              startIcon={
                submitting ? (
                  <CircularProgress size={14} color="inherit" />
                ) : null
              }
            >
              {submitting ? "Saving..." : "Confirm"}
            </Button>
          </Stack>
        </Stack>
      </MainCard>
    </Modal>
  );
}

AssignExecutorModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  campaignId: PropTypes.string.isRequired,
  currentExecutor: PropTypes.object,
  ownerId: PropTypes.string,
  onSuccess: PropTypes.func.isRequired,
};

// ==============================|| CAMPAIGN MEMBERS TAB ||============================== //

export default function CampaignMembersTab({
  campaignId,
  campaign,
  onCampaignUpdate,
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const [removingExecutor, setRemovingExecutor] = useState(false);

  const isFinalStatus =
    campaign?.status === "COMPLETED" || campaign?.status === "CANCELLED";
  const isTargeted = campaign?.campaign_type === "TARGETED";

  const handleRemoveExecutor = useCallback(async () => {
    setRemovingExecutor(true);
    try {
      const result = await updateCampaign(campaignId, { executor_id: null });
      if (result.success) {
        displaySuccessSnackbar("Executor removed");
        onCampaignUpdate?.();
      } else {
        displayErrorSnackbar(result);
      }
    } finally {
      setRemovingExecutor(false);
    }
  }, [campaignId, onCampaignUpdate]);

  return (
    <>
      <Stack spacing={2}>
        {/* Header */}
        <Typography variant="body2" color="text.secondary">
          Campaign ownership and execution assignment.
        </Typography>

        {/* Owner — always read-only */}
        <MemberRow
          icon={CrownOutlined}
          label="Owner"
          user={campaign?.owner}
          isPrimary
        />

        {/* Executor — editable (except TARGETED or final status) */}
        <MemberRow
          icon={UserOutlined}
          label="Executor"
          user={campaign?.executor}
          action={
            !isFinalStatus && !isTargeted ? (
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<EditOutlined />}
                  onClick={() => setModalOpen(true)}
                >
                  {campaign?.executor ? "Change" : "Assign"}
                </Button>
                {campaign?.executor && (
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    onClick={handleRemoveExecutor}
                    disabled={removingExecutor}
                    startIcon={
                      removingExecutor ? (
                        <CircularProgress size={12} color="inherit" />
                      ) : (
                        <DeleteOutlined />
                      )
                    }
                  >
                    Remove
                  </Button>
                )}
              </Stack>
            ) : null
          }
        />

        {!campaign?.executor && !isFinalStatus && !isTargeted && (
          <Typography variant="caption" color="text.secondary">
            If no executor is assigned, the owner executes the activities.
          </Typography>
        )}
      </Stack>

      <AssignExecutorModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        campaignId={campaignId}
        currentExecutor={campaign?.executor}
        ownerId={campaign?.owner?.id}
        onSuccess={() => {
          setModalOpen(false);
          onCampaignUpdate?.();
        }}
      />
    </>
  );
}

CampaignMembersTab.propTypes = {
  campaignId: PropTypes.string,
  campaign: PropTypes.object,
  onCampaignUpdate: PropTypes.func,
};
