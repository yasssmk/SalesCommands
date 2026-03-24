// frontend/src/sections/activities/workspace/ActivityHeader.jsx
/**
 * Activity Header — Hook version for WorkspaceLayout.
 *
 * Returns layout props + modals JSX:
 *   { avatar, title, onTitleSave, titleDisabled, headerActions, chips, infoItems, modals }
 *
 * Usage in index.jsx:
 *   const headerProps = useActivityHeaderProps({ activity, onSave, onUpdate, isLocked });
 *   <WorkspaceLayout {...headerProps} />
 *   {headerProps.modals}
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// MUI
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

// Date formatting
import { format } from "date-fns";

// API
import {
  updateActivity,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS,
  ACTIVITY_OUTCOME_LABELS,
  ACTIVITY_OUTCOME_COLORS,
} from "api/accounts/activities";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// Modals
import ActivityCompleteModal from "sections/accounts/activities/ActivityCompleteModal";
import AlertActivityDelete from "sections/accounts/activities/AlertActivityDelete";
import AlertActivityCancel from "sections/accounts/activities/AlertActivityCancel";
import AlertActivityReopen from "sections/accounts/activities/AlertActivityReopen";
import CampaignOutcomeModal from "sections/campaigns/CampaignOutcomeModal";

// Icons
import {
  MoreOutlined,
  CheckCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  PhoneOutlined,
  MailOutlined,
  TeamOutlined,
  CheckSquareOutlined,
  LinkedinOutlined,
  QuestionCircleOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  BankOutlined,
  ApartmentOutlined,
  RightOutlined,
  UndoOutlined,
  AimOutlined,
} from "@ant-design/icons";

// ==============================|| TYPE CONFIGURATION ||============================== //

const TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined,
};

const TYPE_AVATAR_COLORS = {
  CALL: "info.main",
  EMAIL: "warning.main",
  MEETING: "success.main",
  TASK: "secondary.main",
  LINKEDIN: "primary.main",
  OTHER: "grey.500",
};

const TYPE_CHIP_COLORS = {
  CALL: "info",
  EMAIL: "warning",
  MEETING: "success",
  TASK: "secondary",
  LINKEDIN: "primary",
  OTHER: "default",
};

// ==============================|| ACTIVITY HEADER PROPS HOOK ||============================== //

export default function useActivityHeaderProps({
  activity,
  onSave,
  onUpdate,
  isLocked = false,
}) {
  const theme = useTheme();
  const router = useRouter();

  // ==============================|| STATE ||============================== //

  // Actions menu
  const [anchorEl, setAnchorEl] = useState(null);
  const menuOpen = Boolean(anchorEl);

  // Type change menu
  const [typeAnchorEl, setTypeAnchorEl] = useState(null);
  const typeMenuOpen = Boolean(typeAnchorEl);
  const [savingType, setSavingType] = useState(false);

  // Modal states
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [reopenDialogOpen, setReopenDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [campaignOutcomeModalOpen, setCampaignOutcomeModalOpen] =
    useState(false);

  // ==============================|| EARLY RETURN (no data) ||============================== //

  if (!activity) {
    return { avatar: null, title: "", chips: [], infoItems: [], modals: null };
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const TypeIcon = TYPE_ICONS[activity.activity_type] || QuestionCircleOutlined;
  const avatarColor = TYPE_AVATAR_COLORS[activity.activity_type] || "grey.500";
  const typeChipColor = TYPE_CHIP_COLORS[activity.activity_type] || "default";

  const isCompleted = activity.status === "COMPLETED";
  const isCancelled = activity.status === "CANCELLED";
  const isPlanned = activity.status === "PLANNED";
  const canComplete = !isCompleted && !isCancelled;
  const canCancel = isPlanned;
  const canReopen = isCompleted || isCancelled;

  const isCampaignActivity =
    Boolean(activity.campaign_detail) && !activity.decision_cycle;
  const previousActivities =
    activity?.sequence_context?.previous_activities || [];
  const previousActivity = previousActivities[0] || null;
  const isPreviousBlocking =
    isCampaignActivity &&
    previousActivity &&
    previousActivity.status !== "COMPLETED";

  // ==============================|| HANDLERS — Actions menu ||============================== //

  const handleMenuOpen = (event) => setAnchorEl(event.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  const handleCompleteClick = () => {
    handleMenuClose();
    if (isCampaignActivity) {
      setCampaignOutcomeModalOpen(true);
    } else {
      setCompleteModalOpen(true);
    }
  };
  const handleCompleteSuccess = () => {
    setCompleteModalOpen(false);
    setCampaignOutcomeModalOpen(false);
    onUpdate?.();
  };

  const handleCancelClick = () => {
    handleMenuClose();
    setCancelDialogOpen(true);
  };
  const handleCancelSuccess = () => {
    setCancelDialogOpen(false);
    onUpdate?.();
  };

  const handleReopenClick = () => {
    handleMenuClose();
    setReopenDialogOpen(true);
  };
  const handleReopenSuccess = () => {
    setReopenDialogOpen(false);
    onUpdate?.();
  };

  const handleDeleteClick = () => {
    handleMenuClose();
    setDeleteDialogOpen(true);
  };

  // ==============================|| HANDLERS — Type change ||============================== //

  const handleTypeMenuOpen = (event) => setTypeAnchorEl(event.currentTarget);
  const handleTypeMenuClose = () => setTypeAnchorEl(null);

  const handleTypeChange = async (newType) => {
    if (newType === activity.activity_type) {
      handleTypeMenuClose();
      return;
    }
    setSavingType(true);
    try {
      const result = await updateActivity(activity.id, {
        activity_type: newType,
      });
      if (result.success) {
        displaySuccessSnackbar("Activity type updated");
        onUpdate?.();
      } else {
        displayErrorSnackbar(result);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setSavingType(false);
      handleTypeMenuClose();
    }
  };

  // ==============================|| HANDLERS — Navigation ||============================== //

  const handleAccountClick = () => {
    if (activity.account_detail?.id) {
      router.push(`/accounts/${activity.account_detail.id}`);
    }
  };

  const handleCycleClick = () => {
    if (activity.account_detail?.id) {
      const cycleId = activity.decision_cycle || null;
      const cycleParam = cycleId ? `&cycle=${cycleId}` : "";
      router.push(
        `/accounts/${activity.account_detail.id}?tab=decision-cycle${cycleParam}`,
      );
    }
  };
  // ==============================|| DATE INFO HELPER ||============================== //

  const renderDateInfo = () => {
    if (isCompleted && activity.completed_at) {
      const dateText = format(
        new Date(activity.completed_at),
        "MMM d, yyyy HH:mm",
      );
      const byName = activity.completed_by_name
        ? ` by ${activity.completed_by_name}`
        : "";
      return (
        <Stack key="date" direction="row" spacing={0.75} alignItems="center">
          <CheckCircleOutlined
            style={{
              fontSize: theme.iconSizes.sm,
              color: theme.palette.success.main,
              display: "flex",
            }}
          />
          <Typography variant="body2" color="success.main">
            Completed: {dateText}
            {byName}
          </Typography>
        </Stack>
      );
    }

    if (isCancelled) {
      return (
        <Stack key="date" direction="row" spacing={0.75} alignItems="center">
          <ClockCircleOutlined
            style={{
              fontSize: theme.iconSizes.sm,
              color: theme.palette.text.disabled,
              display: "flex",
            }}
          />
          <Typography variant="body2" color="text.disabled">
            Cancelled
          </Typography>
        </Stack>
      );
    }

    // Planned — show due date or scheduled date
    const dateField = activity.due_date || activity.scheduled_date;
    if (!dateField) return null;

    const label = activity.due_date ? "Due" : "Scheduled";
    const dateText = format(new Date(dateField), "MMM d, yyyy");
    const isOverdue =
      activity.due_date &&
      new Date(activity.due_date) < new Date() &&
      isPlanned;

    return (
      <Stack key="date" direction="row" spacing={0.75} alignItems="center">
        <CalendarOutlined
          style={{
            fontSize: theme.iconSizes.sm,
            color: isOverdue
              ? theme.palette.error.main
              : theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography
          variant="body2"
          color={isOverdue ? "error.main" : "text.secondary"}
        >
          {label}: {dateText}
          {isOverdue && " (Overdue)"}
        </Typography>
      </Stack>
    );
  };

  // ==============================|| ROW 1: Avatar ||============================== //

  const avatar = (
    <Avatar
      sx={{ width: 56, height: 56, bgcolor: avatarColor, fontSize: "1.5rem" }}
    >
      <TypeIcon />
    </Avatar>
  );

  // ==============================|| ROW 1: Title ||============================== //

  const title = activity.title || "";
  const onTitleSave = onSave;
  const titleDisabled = isLocked;

  // ==============================|| ROW 1: Actions (⋯ menu) ||============================== //

  const headerActions = (
    <>
      <IconButton onClick={handleMenuOpen}>
        <MoreOutlined />
      </IconButton>
      <Menu anchorEl={anchorEl} open={menuOpen} onClose={handleMenuClose}>
        {canComplete && !isLocked && (
          <Tooltip
            title={
              isPreviousBlocking
                ? "Complete the previous activities in the playlist first."
                : ""
            }
            placement="left"
            arrow
          >
            <span>
              <MenuItem
                onClick={isPreviousBlocking ? undefined : handleCompleteClick}
                disabled={isPreviousBlocking}
              >
                <ListItemIcon>
                  <CheckCircleOutlined
                    style={{ color: theme.palette.success.main }}
                  />
                </ListItemIcon>
                <Typography>
                  {isCampaignActivity ? "Log Response" : "Complete"}
                </Typography>
              </MenuItem>
            </span>
          </Tooltip>
        )}
        {canCancel && !isLocked && !isCampaignActivity && (
          <MenuItem onClick={handleCancelClick}>
            <ListItemIcon>
              <StopOutlined style={{ color: theme.palette.warning.main }} />
            </ListItemIcon>
            <Typography>Cancel</Typography>
          </MenuItem>
        )}
        {canReopen && (
          <MenuItem onClick={handleReopenClick}>
            <ListItemIcon>
              <UndoOutlined style={{ color: theme.palette.primary.main }} />
            </ListItemIcon>
            <Typography>Reopen</Typography>
          </MenuItem>
        )}
        {!isCampaignActivity && <Divider />}
        {!isCampaignActivity && (
          <MenuItem onClick={handleDeleteClick}>
            <ListItemIcon>
              <DeleteOutlined style={{ color: theme.palette.error.main }} />
            </ListItemIcon>
            <Typography color="error.main">Delete</Typography>
          </MenuItem>
        )}
      </Menu>
    </>
  );

  // ==============================|| ROW 2: Chips ||============================== //

  const chips = [
    // Type chip (clickable → type change menu)
    <Tooltip key="type" title={isLocked ? "" : "Click to change type"} arrow>
      <Chip
        label={
          ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type
        }
        color={typeChipColor}
        size="small"
        variant="filled"
        onClick={isLocked ? undefined : handleTypeMenuOpen}
        sx={isLocked ? {} : { cursor: "pointer" }}
      />
    </Tooltip>,

    // Type change menu (anchored to chip)
    <Menu
      key="type-menu"
      anchorEl={typeAnchorEl}
      open={typeMenuOpen}
      onClose={handleTypeMenuClose}
    >
      {Object.entries(ACTIVITY_TYPE_LABELS).map(([typeValue, typeLabel]) => {
        const isSelected = activity.activity_type === typeValue;
        const TypeOptionIcon = TYPE_ICONS[typeValue] || QuestionCircleOutlined;
        return (
          <MenuItem
            key={typeValue}
            selected={isSelected}
            onClick={() => handleTypeChange(typeValue)}
            disabled={savingType}
          >
            <ListItemIcon>
              <TypeOptionIcon
                style={{
                  color: isSelected
                    ? theme.palette.primary.main
                    : theme.palette.text.secondary,
                }}
              />
            </ListItemIcon>
            <Typography
              variant="body2"
              fontWeight={isSelected ? 600 : 400}
              color={isSelected ? "primary.main" : "text.primary"}
            >
              {typeLabel}
            </Typography>
          </MenuItem>
        );
      })}
    </Menu>,

    // Status chip
    <Chip
      key="status"
      label={ACTIVITY_STATUS_LABELS[activity.status] || activity.status}
      color={ACTIVITY_STATUS_COLORS[activity.status] || "default"}
      size="small"
      variant="filled"
    />,

    // Campaign context chip (when activity belongs to a campaign)
    activity.campaign_detail && !activity.decision_cycle && (
      <Chip
        key="campaign"
        label={`Campaign: ${activity.campaign_detail.name}`}
        size="small"
        variant="outlined"
        color="secondary"
        icon={<AimOutlined />}
        onClick={() => router.push(`/campaigns/${activity.campaign_detail.id}`)}
        sx={{ cursor: "pointer" }}
      />
    ),

    // Outcome chip (only when completed)
    activity.outcome && (
      <Chip
        key="outcome"
        label={ACTIVITY_OUTCOME_LABELS[activity.outcome] || activity.outcome}
        color={ACTIVITY_OUTCOME_COLORS[activity.outcome] || "default"}
        size="small"
        variant="outlined"
      />
    ),
  ];

  // ==============================|| INFO ITEMS (after divider) ||============================== //

  const infoItems = [
    // Account link
    activity.account_detail?.company_name && (
      <Stack
        key="account"
        direction="row"
        spacing={0.75}
        alignItems="center"
        onClick={handleAccountClick}
        sx={{
          cursor: "pointer",
          "&:hover .info-link": { textDecoration: "underline" },
        }}
      >
        <BankOutlined
          style={{
            fontSize: theme.iconSizes.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Typography variant="body2" color="primary.main" className="info-link">
          {activity.account_detail.company_name}
        </Typography>
      </Stack>
    ),

    // Origin: Cycle > Step
    activity.decision_cycle_detail && (
      <Stack key="origin" direction="row" spacing={0.75} alignItems="center">
        <ApartmentOutlined
          style={{
            fontSize: theme.iconSizes.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Typography
            variant="body2"
            color="primary.main"
            onClick={handleCycleClick}
            sx={{
              cursor: "pointer",
              "&:hover": { textDecoration: "underline" },
            }}
          >
            {activity.decision_cycle_detail.name}
          </Typography>
          {activity.decision_step_detail && (
            <>
              <RightOutlined
                style={{
                  fontSize: theme.iconSizes.xs - 2,
                  color: theme.palette.text.disabled,
                }}
              />
              <Typography variant="body2" color="text.secondary">
                {activity.decision_step_detail.name}
              </Typography>
            </>
          )}
        </Stack>
      </Stack>
    ),

    // Campaign context (when activity was generated by a campaign)
    activity.campaign_detail && (
      <Stack key="campaign" direction="row" spacing={0.75} alignItems="center">
        <AimOutlined
          style={{
            fontSize: theme.iconSizes.sm,
            color: theme.palette.text.secondary,
            display: "flex",
          }}
        />
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Typography
            variant="body2"
            color="primary.main"
            onClick={() =>
              router.push(`/campaigns/${activity.campaign_detail.id}`)
            }
            sx={{
              cursor: "pointer",
              "&:hover": { textDecoration: "underline" },
            }}
          >
            {activity.campaign_detail.name}
          </Typography>
          {activity.campaign_detail.sequence_position && (
            <>
              <RightOutlined
                style={{
                  fontSize: theme.iconSizes.xs - 2,
                  color: theme.palette.text.disabled,
                }}
              />
              <Typography variant="body2" color="text.secondary">
                Step {activity.campaign_detail.sequence_position}
              </Typography>
            </>
          )}
        </Stack>
      </Stack>
    ),

    // Date info
    renderDateInfo(),
  ];

  // ==============================|| MODALS ||============================== //

  const modals = (
    <>
      <ActivityCompleteModal
        open={completeModalOpen}
        onClose={() => setCompleteModalOpen(false)}
        activity={activity}
        onSuccess={handleCompleteSuccess}
      />
      <CampaignOutcomeModal
        open={campaignOutcomeModalOpen}
        onClose={() => setCampaignOutcomeModalOpen(false)}
        activity={activity}
        campaignId={activity?.campaign_detail?.id}
        onComplete={handleCompleteSuccess}
        onUpdate={onUpdate}
      />
      <AlertActivityCancel
        open={cancelDialogOpen}
        handleClose={() => setCancelDialogOpen(false)}
        activity={activity}
        onSuccess={handleCancelSuccess}
      />
      <AlertActivityReopen
        open={reopenDialogOpen}
        handleClose={() => setReopenDialogOpen(false)}
        activity={activity}
        onSuccess={handleReopenSuccess}
      />
      <AlertActivityDelete
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        activity={activity}
        onSuccess={() => {
          setDeleteDialogOpen(false);
          if (activity?.account_detail?.id) {
            router.push(`/accounts/${activity.account_detail.id}`);
          } else {
            router.push("/territories");
          }
        }}
      />
    </>
  );

  // ==============================|| RETURN ||============================== //

  return {
    avatar,
    title,
    onTitleSave,
    titleDisabled,
    headerActions,
    chips,
    infoItems,
    modals,
  };
}
