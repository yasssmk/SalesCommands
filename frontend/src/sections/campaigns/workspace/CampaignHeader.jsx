// frontend/src/sections/campaigns/workspace/CampaignHeader.jsx
/**
 * Campaign Header — Hook version for WorkspaceLayout.
 *
 * Returns layout props:
 *   { avatar, title, chips, infoItems, headerActions }
 *
 * Usage in workspace/index.jsx:
 *   const headerProps = useCampaignHeaderProps({ campaign, stats, onMutate });
 *   <WorkspaceLayout {...headerProps} />
 *
 * Pattern: sections/activities/workspace/ActivityHeader.jsx
 */
"use client";
import { useState, useRef } from "react";

// MUI
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import ButtonGroup from "@mui/material/ButtonGroup";
import ClickAwayListener from "@mui/material/ClickAwayListener";
import Divider from "@mui/material/Divider";
import Grow from "@mui/material/Grow";
import ListItemIcon from "@mui/material/ListItemIcon";
import MenuItem from "@mui/material/MenuItem";
import MenuList from "@mui/material/MenuList";
import Paper from "@mui/material/Paper";
import Popper from "@mui/material/Popper";
import DownOutlined from "@ant-design/icons/DownOutlined";
import MessageOutlined from "@ant-design/icons/MessageOutlined";

// project imports
import CampaignStatusBadge from "sections/campaigns/CampaignStatusBadge";
import CampaignCompletionModal from "./CampaignCompletionModal";
import {
  SEQUENCE_TYPE_LABELS,
  OBJECTIVE_TYPE_LABELS,
  getCampaignProgress,
  startCampaign,
  pauseCampaign,
  resumeCampaign,
  completeCampaign,
} from "api/campaigns/campaigns";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// icons
import AimOutlined from "@ant-design/icons/AimOutlined";
import ThunderboltOutlined from "@ant-design/icons/ThunderboltOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import BankOutlined from "@ant-design/icons/BankOutlined";
import PlayCircleOutlined from "@ant-design/icons/PlayCircleOutlined";
import PauseCircleOutlined from "@ant-design/icons/PauseCircleOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";

// ==============================|| FAMILY CONFIG ||============================== //

const FAMILY_CONFIG = {
  OUTBOUND: {
    Icon: AimOutlined,
    avatarColor: "primary.main",
    chipColor: "primary",
  },
  TARGETED: {
    Icon: ThunderboltOutlined,
    avatarColor: "warning.main",
    chipColor: "warning",
  },
};

// ==============================|| CAMPAIGN ACTION SPLIT BUTTON ||============================== //

/**
 * Single action button that adapts to campaign status.
 *
 * DRAFT     → [Start]  (single contained button)
 * ACTIVE    → [Pause ▾]  dropdown: Complete · Log Response
 * PAUSED    → [Resume ▾] dropdown: Complete · Log Response
 * COMPLETED / CANCELLED → nothing
 */
function CampaignActionButtons({ campaign, onMutate, onLogResponse }) {
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);

  // Completion modal state
  const [confirmDialog, setConfirmDialog] = useState(false);
  const [completionModal, setCompletionModal] = useState(false);
  const [openContacts, setOpenContacts] = useState([]);

  const handleAction = async (actionFn, successMessage) => {
    setLoading(true);
    setOpen(false);
    try {
      const result = await actionFn(campaign.id);
      if (!result.success) {
        displayErrorSnackbar(result);
        return;
      }
      displaySuccessSnackbar(successMessage);
      if (onMutate) onMutate();
    } catch {
      displayErrorSnackbar("An error occurred");
    } finally {
      setLoading(false);
    }
  };

  // Complete — intercept if open contacts exist
  // Step 1 — open confirmation dialog
  const handleCompleteClick = () => {
    setOpen(false);
    setConfirmDialog(true);
  };

  // Step 2 — confirmed: call API
  const handleComplete = async () => {
    setConfirmDialog(false);
    setLoading(true);
    try {
      const result = await completeCampaign(campaign.id);
      if (!result.success) {
        displayErrorSnackbar(result);
        return;
      }
      const data = result.data?.data ?? result.data;
      console.log(data);
      if (data?.requires_confirmation && data?.open_contacts?.length > 0) {
        setOpenContacts(data.open_contacts);
        setCompletionModal(true);
        // Campaign already COMPLETED on backend — modal offers transfer only
      } else {
        displaySuccessSnackbar("Campaign completed");
        if (onMutate) onMutate();
      }
    } catch {
      displayErrorSnackbar("An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteWithoutFollowup = async () => {
    // Campaign is already COMPLETED — just close modal and revalidate
    if (onMutate) await onMutate();
  };

  const handleToggle = () => setOpen((prev) => !prev);
  const handleClose = (e) => {
    if (anchorRef.current?.contains(e.target)) return;
    setOpen(false);
  };

  // TARGETED — only Log Response button, no lifecycle actions
  if (campaign.campaign_type === "TARGETED") {
    return (
      <Button
        variant="outlined"
        size="small"
        startIcon={<MessageOutlined />}
        onClick={() => onLogResponse?.()}
      >
        Log Response
      </Button>
    );
  }

  // DRAFT — single Start button
  if (campaign.status === "DRAFT") {
    return (
      <Button
        variant="contained"
        color="success"
        size="small"
        startIcon={
          loading ? (
            <CircularProgress size={14} color="inherit" />
          ) : (
            <PlayCircleOutlined />
          )
        }
        disabled={loading}
        onClick={() => handleAction(startCampaign, "Campaign started")}
      >
        Start
      </Button>
    );
  }

  // COMPLETED / CANCELLED — nothing
  if (["COMPLETED", "CANCELLED"].includes(campaign.status) && !completionModal)
    return null;

  // ACTIVE or PAUSED — split button
  const isActive = campaign.status === "ACTIVE";
  const primaryLabel = isActive ? "Pause" : "Resume";
  const primaryAction = isActive ? pauseCampaign : resumeCampaign;
  const primaryMessage = isActive ? "Campaign paused" : "Campaign resumed";
  const primaryIcon = isActive ? (
    <PauseCircleOutlined />
  ) : (
    <PlayCircleOutlined />
  );
  const primaryColor = isActive ? "warning" : "success";

  return (
    <>
      <ButtonGroup
        ref={anchorRef}
        variant="contained"
        color={primaryColor}
        size="small"
        disabled={loading}
      >
        {/* Primary action */}
        <Button
          startIcon={
            loading ? (
              <CircularProgress size={14} color="inherit" />
            ) : (
              primaryIcon
            )
          }
          onClick={() => handleAction(primaryAction, primaryMessage)}
        >
          {primaryLabel}
        </Button>

        {/* Dropdown arrow */}
        <Button
          size="small"
          onClick={handleToggle}
          sx={{ px: 0.75, minWidth: 28 }}
        >
          <DownOutlined style={{ fontSize: 10 }} />
        </Button>
      </ButtonGroup>

      <Popper
        open={open}
        anchorEl={anchorRef.current}
        transition
        disablePortal
        placement="bottom-end"
        style={{ zIndex: 1300 }}
      >
        {({ TransitionProps }) => (
          <Grow {...TransitionProps}>
            <Paper elevation={3} sx={{ mt: 0.5, minWidth: 160 }}>
              <ClickAwayListener onClickAway={handleClose}>
                <MenuList dense>
                  <MenuItem onClick={handleCompleteClick}>
                    <ListItemIcon>
                      <CheckCircleOutlined />
                    </ListItemIcon>
                    Complete
                  </MenuItem>
                  <Divider />
                  <MenuItem
                    onClick={() => {
                      setOpen(false);
                      onLogResponse?.();
                    }}
                  >
                    <ListItemIcon>
                      <MessageOutlined />
                    </ListItemIcon>
                    Log Response
                  </MenuItem>
                </MenuList>
              </ClickAwayListener>
            </Paper>
          </Grow>
        )}
      </Popper>

      {/* Confirmation dialog */}
      <Dialog
        open={confirmDialog}
        onClose={() => setConfirmDialog(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Complete campaign?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will mark <strong>{campaign.name}</strong> as completed. This
            action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setConfirmDialog(false)}
            color="inherit"
            size="small"
          >
            Cancel
          </Button>
          <Button
            onClick={handleComplete}
            variant="contained"
            color="success"
            size="small"
            startIcon={<CheckCircleOutlined />}
          >
            Complete
          </Button>
        </DialogActions>
      </Dialog>

      <CampaignCompletionModal
        open={completionModal}
        onClose={() => {
          setCompletionModal(false);
          if (onMutate) onMutate();
        }}
        openContacts={openContacts}
        onCompleteWithoutFollowup={handleCompleteWithoutFollowup}
      />
    </>
  );
}

// ==============================|| CAMPAIGN HEADER HOOK ||============================== //

/**
 * @param {Object} params
 * @param {Object}   params.campaign  - Campaign data from API
 * @param {Object}   params.stats     - Campaign stats
 * @param {Function} params.onMutate  - Callback to revalidate campaign after lifecycle action
 * @returns {Object} Props object spread into <WorkspaceLayout {...props} />
 */
export default function useCampaignHeaderProps({
  campaign,
  stats,
  onMutate,
  onLogResponse,
}) {
  const theme = useTheme();

  if (!campaign) {
    return {
      avatar: null,
      title: "",
      chips: [],
      infoItems: [],
      headerActions: null,
    };
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const familyConfig =
    FAMILY_CONFIG[campaign.campaign_type] || FAMILY_CONFIG.OUTBOUND;
  const FamilyIcon = familyConfig.Icon;
  const progress = stats?.completion_rate || getCampaignProgress(campaign);

  // ==============================|| AVATAR + TITLE ||============================== //

  const avatar = (
    <Avatar
      sx={{
        width: 56,
        height: 56,
        bgcolor: familyConfig.avatarColor,
        fontSize: "1.5rem",
      }}
    >
      <FamilyIcon />
    </Avatar>
  );

  const title = campaign.name || "";

  const headerActions = (
    <CampaignActionButtons
      campaign={campaign}
      onMutate={onMutate}
      onLogResponse={onLogResponse}
    />
  );

  // ==============================|| ROW 2: Chips ||============================== //

  const chips = [
    <CampaignStatusBadge key="status" status={campaign.status} />,
    <Chip
      key="family"
      label={
        SEQUENCE_TYPE_LABELS[campaign.campaign_type] || campaign.campaign_type
      }
      size="small"
      color={familyConfig.chipColor}
      variant="outlined"
    />,
  ].filter(Boolean);

  // ==============================|| ROW 3: Info Items (JSX elements) ||============================== //

  const infoItems = [
    // Territory — DetailSerializer returns territories[] ({id, name, type})
    campaign.territories?.length > 0 && (
      <Stack key="territory" direction="row" spacing={0.75} alignItems="center">
        <BankOutlined
          style={{ fontSize: 14, color: theme.palette.text.secondary }}
        />
        <Typography variant="body2" color="text.secondary">
          {campaign.territories.map((t) => t.name).join(", ")}
        </Typography>
      </Stack>
    ),

    // Objective — DetailSerializer returns primary_objective ({objective_type, ...})
    // ListSerializer returns primary_objective as well — same path works for both
    campaign.primary_objective?.objective_type && (
      <Stack key="objective" direction="row" spacing={0.75} alignItems="center">
        <CheckCircleOutlined
          style={{ fontSize: 14, color: theme.palette.text.secondary }}
        />
        <Typography variant="body2" color="text.secondary">
          {OBJECTIVE_TYPE_LABELS[campaign.primary_objective.objective_type] ||
            campaign.primary_objective.objective_type}
        </Typography>
      </Stack>
    ),
    // Dates
    campaign.start_date && (
      <Stack key="dates" direction="row" spacing={0.75} alignItems="center">
        <CalendarOutlined
          style={{ fontSize: 14, color: theme.palette.text.secondary }}
        />
        <Typography variant="body2" color="text.secondary">
          {campaign.start_date}
          {campaign.end_date ? ` → ${campaign.end_date}` : ""}
        </Typography>
      </Stack>
    ),
    // Members
    <Stack key="members" direction="row" spacing={0.75} alignItems="center">
      <TeamOutlined
        style={{ fontSize: 14, color: theme.palette.text.secondary }}
      />
      <Typography variant="body2" color="text.secondary">
        {campaign.members?.length || stats?.total_members || 0} members
      </Typography>
    </Stack>,
    // Accounts
    <Stack key="accounts" direction="row" spacing={0.75} alignItems="center">
      <BankOutlined
        style={{ fontSize: 14, color: theme.palette.text.secondary }}
      />
      <Typography variant="body2" color="text.secondary">
        {stats?.total_accounts ?? campaign.accounts_count ?? 0} accounts
      </Typography>
    </Stack>,
    // Progress
    typeof progress === "number" && (
      <Stack key="progress" direction="row" spacing={0.75} alignItems="center">
        <Typography
          variant="body2"
          color={progress >= 100 ? "success.main" : "text.secondary"}
          fontWeight={500}
        >
          {progress}% complete
        </Typography>
      </Stack>
    ),
  ].filter(Boolean);

  // ==============================|| RETURN ||============================== //

  return {
    avatar,
    title,
    headerActions,
    chips,
    infoItems,
  };
}
