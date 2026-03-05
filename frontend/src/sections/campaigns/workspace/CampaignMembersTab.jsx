// frontend/src/sections/campaigns/workspace/CampaignMembersTab.jsx
/**
 * Campaign Members Tab — Members grouped by role.
 *
 * API: useGetCampaignMembers → GET /campaigns/members/by-campaign/?campaign_id=
 * Mutation: addCampaignMember → POST /campaigns/members/
 *           payload: { campaign_id, user_id, role }
 *
 * ListSerializer returns flat fields: user_name, user_email (no nested user object).
 */

"use client";

import PropTypes from "prop-types";
import { useMemo, useState, useCallback } from "react";

// material-ui
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import Grid from "@mui/material/Grid";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Modal from "@mui/material/Modal";
import Select from "@mui/material/Select";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// project imports
import MainCard from "components/MainCard";
import AsyncUserSelect from "components/AsyncSelection/AsyncUserSelect";

// api
import {
  useGetCampaignMembers,
  addCampaignMember,
  MEMBER_ROLE_LABELS,
} from "api/campaigns/campaigns";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// icons
import PlusOutlined from "@ant-design/icons/PlusOutlined";
import CrownOutlined from "@ant-design/icons/CrownOutlined";
import UserOutlined from "@ant-design/icons/UserOutlined";
import EyeOutlined from "@ant-design/icons/EyeOutlined";

// ==============================|| ROLE CONFIG ||============================== //

const ROLE_CONFIG = {
  OWNER: { Icon: CrownOutlined, color: "warning", avatarBg: "warning.main" },
  EXECUTOR: { Icon: UserOutlined, color: "primary", avatarBg: "primary.main" },
  OBSERVER: { Icon: EyeOutlined, color: "default", avatarBg: "grey.500" },
};

const ROLE_ORDER = ["OWNER", "EXECUTOR", "OBSERVER"];

// ==============================|| LOADING SKELETON ||============================== //

function MembersSkeleton() {
  return (
    <Stack spacing={1}>
      {[1, 2, 3].map((i) => (
        <Skeleton
          key={i}
          variant="rectangular"
          height={64}
          sx={{ borderRadius: 1.5 }}
        />
      ))}
    </Stack>
  );
}

// ==============================|| MEMBER CARD ||============================== //

function MemberCard({ member }) {
  const config = ROLE_CONFIG[member.role] || ROLE_CONFIG.OBSERVER;

  // ListSerializer returns flat fields: user_name, user_email (not nested user object)
  const fullName = member.user_name || member.user_email || "Unknown";
  const email = member.user_email || "—";
  const initials =
    fullName
      .split(" ")
      .map((n) => n[0] || "")
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?";

  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 1.5,
        border: "1px solid",
        borderColor: "grey.200",
        bgcolor: "background.paper",
        transition: "all 0.2s ease",
        "&:hover": { borderColor: "grey.300", bgcolor: "grey.50" },
      }}
    >
      <Stack direction="row" spacing={2} alignItems="center">
        <Avatar
          sx={{
            width: 40,
            height: 40,
            bgcolor: config.avatarBg,
            fontSize: "0.875rem",
            fontWeight: 600,
          }}
        >
          {initials}
        </Avatar>

        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="subtitle2" noWrap>
              {fullName}
            </Typography>
            {member.is_primary_owner && (
              <Chip
                label="Primary"
                size="small"
                color="warning"
                variant="outlined"
                sx={{ height: 20, fontSize: "0.675rem" }}
              />
            )}
          </Stack>
          <Typography variant="caption" color="text.secondary" noWrap>
            {email}
          </Typography>
        </Box>

        <Chip
          label={MEMBER_ROLE_LABELS[member.role] || member.role}
          size="small"
          color={config.color}
          variant="outlined"
        />
      </Stack>
    </Box>
  );
}

MemberCard.propTypes = {
  member: PropTypes.object.isRequired,
};

// ==============================|| ROLE GROUP ||============================== //

function RoleGroup({ role, members }) {
  const theme = useTheme();
  const config = ROLE_CONFIG[role] || ROLE_CONFIG.OBSERVER;
  const RoleIcon = config.Icon;

  if (members.length === 0) return null;

  return (
    <Box>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
        <RoleIcon
          style={{ fontSize: 16, color: theme.palette.text.secondary }}
        />
        <Typography
          variant="subtitle2"
          color="text.secondary"
          sx={{
            textTransform: "uppercase",
            fontSize: "0.75rem",
            fontWeight: 600,
            letterSpacing: "0.5px",
          }}
        >
          {MEMBER_ROLE_LABELS[role] || role}s ({members.length})
        </Typography>
      </Stack>
      <Grid container spacing={1.5}>
        {members.map((member) => (
          <Grid item xs={12} sm={6} key={member.id}>
            <MemberCard member={member} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}

RoleGroup.propTypes = {
  role: PropTypes.string.isRequired,
  members: PropTypes.array.isRequired,
};

// ==============================|| ADD MEMBER MODAL ||============================== //

/**
 * Inline modal: AsyncUserSelect + role Select + submit.
 * Pattern: DecisionCycleModal (simple Modal + MainCard, no Formik).
 */
function AddMemberModal({
  open,
  onClose,
  campaignId,
  enrolledUserIds,
  onSuccess,
}) {
  const [selectedUser, setSelectedUser] = useState(null);
  const [role, setRole] = useState("EXECUTOR");
  const [submitting, setSubmitting] = useState(false);

  const handleClose = useCallback(() => {
    setSelectedUser(null);
    setRole("EXECUTOR");
    onClose();
  }, [onClose]);

  const handleSubmit = useCallback(async () => {
    if (!selectedUser?.id) {
      displayErrorSnackbar("Please select a user");
      return;
    }

    setSubmitting(true);
    try {
      const result = await addCampaignMember({
        campaign_id: campaignId,
        user_id: selectedUser.id,
        role,
      });

      if (result.success) {
        displaySuccessSnackbar(
          `${selectedUser.first_name || selectedUser.email} added as ${MEMBER_ROLE_LABELS[role]}`,
        );
        onSuccess();
        handleClose();
      } else {
        displayErrorSnackbar(result);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setSubmitting(false);
    }
  }, [selectedUser, role, campaignId, onSuccess, handleClose]);

  if (!open) return null;

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="add-member-modal"
      sx={{ "& .MuiPaper-root:focus": { outline: "none" } }}
    >
      <MainCard
        title="Add Member"
        sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: { xs: "calc(100% - 32px)", sm: 480 },
          maxHeight: "calc(100vh - 48px)",
          overflowY: "auto",
        }}
        modal
      >
        <Stack spacing={3}>
          {/* User search */}
          <Box>
            <InputLabel sx={{ mb: 1 }}>User *</InputLabel>
            <AsyncUserSelect
              value={selectedUser}
              onChange={(event, user) => setSelectedUser(user)}
              label=""
              placeholder="Search by name or email..."
              disabled={submitting}
              filters={{ is_active: true }}
              filterOptions={(options) =>
                enrolledUserIds?.length
                  ? options.filter((u) => !enrolledUserIds.includes(u.id))
                  : options
              }
            />
          </Box>

          {/* Role select */}
          <Box>
            <InputLabel sx={{ mb: 1 }}>Role *</InputLabel>
            <FormControl fullWidth size="small">
              <Select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                disabled={submitting}
              >
                {ROLE_ORDER.map((r) => (
                  <MenuItem key={r} value={r}>
                    {MEMBER_ROLE_LABELS[r] || r}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          <Divider />

          {/* Actions */}
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
              {submitting ? "Adding..." : "Add Member"}
            </Button>
          </Stack>
        </Stack>
      </MainCard>
    </Modal>
  );
}

AddMemberModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  campaignId: PropTypes.string.isRequired,
  enrolledUserIds: PropTypes.array,
  onSuccess: PropTypes.func.isRequired,
};

// ==============================|| CAMPAIGN MEMBERS TAB ||============================== //

export default function CampaignMembersTab({ campaignId, campaign }) {
  const [modalOpen, setModalOpen] = useState(false);

  // ==============================|| DATA ||============================== //

  const { members, membersLoading, membersError, mutateMembers } =
    useGetCampaignMembers(campaignId);

  // Group by role
  const groupedMembers = useMemo(
    () =>
      ROLE_ORDER.reduce((acc, role) => {
        acc[role] = members.filter((m) => m.role === role);
        return acc;
      }, {}),
    [members],
  );

  // Exclude already-enrolled users from the selector
  // ListSerializer exposes `user` field (UUID)
  const enrolledUserIds = useMemo(
    () => members.map((m) => m.user).filter(Boolean),
    [members],
  );

  const isFinalStatus =
    campaign?.status === "COMPLETED" || campaign?.status === "CANCELLED";

  // ==============================|| LOADING STATE ||============================== //

  if (membersLoading) return <MembersSkeleton />;

  // ==============================|| ERROR STATE ||============================== //

  if (membersError) {
    return (
      <Box sx={{ py: 6, textAlign: "center" }}>
        <Typography variant="h5" color="error">
          Failed to load members
        </Typography>
        <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
          Please try refreshing the page.
        </Typography>
      </Box>
    );
  }

  // ==============================|| EMPTY STATE ||============================== //

  if (members.length === 0) {
    return (
      <>
        <Box sx={{ py: 6, textAlign: "center" }}>
          <Typography variant="h5" color="text.secondary">
            No members in this campaign
          </Typography>
          <Typography variant="body2" color="text.disabled" sx={{ mt: 1 }}>
            Add team members to collaborate on this campaign.
          </Typography>
          {!isFinalStatus && (
            <Button
              variant="contained"
              size="small"
              startIcon={<PlusOutlined />}
              onClick={() => setModalOpen(true)}
              sx={{ mt: 2 }}
            >
              Add First Member
            </Button>
          )}
        </Box>

        <AddMemberModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          campaignId={campaignId}
          enrolledUserIds={enrolledUserIds}
          onSuccess={mutateMembers}
        />
      </>
    );
  }

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <Box>
        {/* Header */}
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{ mb: 3 }}
        >
          <Typography variant="body2" color="text.secondary">
            {members.length} member{members.length !== 1 ? "s" : ""} in this
            campaign
          </Typography>
          {!isFinalStatus && (
            <Button
              variant="outlined"
              size="small"
              startIcon={<PlusOutlined />}
              onClick={() => setModalOpen(true)}
            >
              Add Member
            </Button>
          )}
        </Stack>

        {/* Role Groups */}
        <Stack spacing={3}>
          {ROLE_ORDER.map((role) => (
            <RoleGroup
              key={role}
              role={role}
              members={groupedMembers[role] || []}
            />
          ))}
        </Stack>
      </Box>

      <AddMemberModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        campaignId={campaignId}
        enrolledUserIds={enrolledUserIds}
        onSuccess={mutateMembers}
      />
    </>
  );
}

CampaignMembersTab.propTypes = {
  campaignId: PropTypes.string,
  campaign: PropTypes.object,
};
