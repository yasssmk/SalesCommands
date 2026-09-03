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
import { format, formatDistanceToNow, parseISO } from "date-fns";

// API
import { ACTIVITY_STATUS_LABELS } from "api/accounts/activities";

// Pipeline state
import { PIPELINE_STATE } from "hooks/usePipelineRunner";

// Modals
import ActivityCompleteModal from "sections/accounts/activities/ActivityCompleteModal";
import AlertActivityDelete from "sections/accounts/activities/AlertActivityDelete";
import AlertActivityCancel from "sections/accounts/activities/AlertActivityCancel";
import AlertActivityReopen from "sections/accounts/activities/AlertActivityReopen";
import CampaignOutcomeModal from "sections/campaigns/CampaignOutcomeModal";

// Icons
import {
  MoreOutlined,
  EditOutlined,
  CheckCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  PhoneOutlined,
  MailOutlined,
  TeamOutlined,
  DesktopOutlined,
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
  ExperimentOutlined,
  ExclamationCircleOutlined,
  LoadingOutlined,
} from "@ant-design/icons";

// ==============================|| TYPE CONFIGURATION ||============================== //

const TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  DEMO: DesktopOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined,
};

const TYPE_AVATAR_COLORS = {
  CALL: "info.main",
  EMAIL: "warning.main",
  MEETING: "success.main",
  DEMO: "error.main",
  TASK: "secondary.main",
  LINKEDIN: "primary.main",
  OTHER: "grey.500",
};

// Status → MUI colour role for the single discreet status chip. Planned reads
// neutral, Completed success, Cancelled error, On hold warning. The chip is
// tinted (light background + full-colour text/border) via theme tokens below —
// the role also drives the `.MuiChip-color*` class.
const STATUS_CHIP_COLOR = {
  PLANNED: "default",
  ON_HOLD: "warning",
  COMPLETED: "success",
  CANCELLED: "error",
};

// Per-role tint: light background + full-colour text/border, all theme tokens
// (no hardcoded hex). "default" is the neutral/muted Planned look.
const STATUS_CHIP_TINT = {
  default: { bgcolor: "action.hover", color: "text.secondary", borderColor: "divider" },
  success: { bgcolor: "success.lighter", color: "success.dark", borderColor: "success.light" },
  error: { bgcolor: "error.lighter", color: "error.dark", borderColor: "error.light" },
  warning: { bgcolor: "warning.lighter", color: "warning.dark", borderColor: "warning.light" },
};

const STATUS_LABEL_FALLBACK = { ON_HOLD: "On hold" };

// ==============================|| ACTIVITY HEADER PROPS HOOK ||============================== //

export default function useActivityHeaderProps({
  activity,
  onSave,
  onUpdate,
  isLocked = false,
  pipelineState = PIPELINE_STATE.IDLE,
  lastRun = null,
  counts = null,
  onPendingClick,
}) {
  const theme = useTheme();
  const router = useRouter();

  // ==============================|| STATE ||============================== //

  // Actions menu
  const [anchorEl, setAnchorEl] = useState(null);
  const menuOpen = Boolean(anchorEl);

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

  const statusChipColor = STATUS_CHIP_COLOR[activity.status] || "default";
  const statusChipLabel =
    ACTIVITY_STATUS_LABELS[activity.status] ||
    STATUS_LABEL_FALLBACK[activity.status] ||
    activity.status;

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

  // ==============================|| HANDLERS — Navigation ||============================== //

  const handleAccountClick = () => {
    if (activity.account_detail?.id) {
      router.push(`/accounts/${activity.account_detail.id}`);
    }
  };

  const handleCycleClick = () => {
    if (activity.account_detail?.id) {
      const cycleId = activity.decision_cycle || null;
      // Route to the DC workspace TIMELINE tab of the parent cycle (the
      // per-step workspace is being retired). Fall back to the account's
      // decision-cycle tab when the cycle id is unavailable, so the click
      // never builds a broken `/dc/undefined` link.
      router.push(
        cycleId
          ? `/accounts/${activity.account_detail.id}/dc/${cycleId}?tab=timeline`
          : `/accounts/${activity.account_detail.id}?tab=decision-cycle`,
      );
    }
  };
  // ==============================|| AI STATUS BADGE HELPER ||============================== //

  const renderAIBadge = () => {
    if (pipelineState === PIPELINE_STATE.RUNNING) {
      return (
        <Stack key="ai-badge" direction="row" spacing={0.75} alignItems="center">
          <LoadingOutlined
            style={{ fontSize: theme.iconSizes.sm, color: theme.palette.primary.main, display: 'flex' }}
          />
          <Typography variant="body2" color="primary.main">
            AI running…
          </Typography>
        </Stack>
      );
    }

    if (pipelineState === PIPELINE_STATE.ERROR) {
      return (
        <Stack key="ai-badge" direction="row" spacing={0.75} alignItems="center">
          <ExclamationCircleOutlined
            style={{ fontSize: theme.iconSizes.sm, color: theme.palette.error.main, display: 'flex' }}
          />
          <Typography variant="body2" color="error.main">
            AI run failed
          </Typography>
        </Stack>
      );
    }

    if (lastRun?.last_run_at) {
      const timeago = formatDistanceToNow(new Date(lastRun.last_run_at), { addSuffix: true });
      const isPartial = lastRun.status === 'PARTIAL';
      return (
        <Stack key="ai-badge" direction="row" spacing={0.75} alignItems="center">
          <ExperimentOutlined
            style={{
              fontSize: theme.iconSizes.sm,
              color: isPartial ? theme.palette.warning.main : theme.palette.text.secondary,
              display: 'flex',
            }}
          />
          <Typography variant="body2" color={isPartial ? 'warning.main' : 'text.secondary'}>
            {isPartial ? 'Partial run' : 'AI run'} · {timeago}
          </Typography>
        </Stack>
      );
    }

    return null;
  };

  // ==============================|| PENDING COUNTER HELPER ||============================== //

  const renderPendingCounter = () => {
    const pending = counts?.pending;
    if (!pending || pending <= 0) return null;

    return (
      <Stack
        key="pending-counter"
        direction="row"
        spacing={0.75}
        alignItems="center"
        onClick={() => onPendingClick?.()}
        sx={{
          cursor: onPendingClick ? 'pointer' : 'default',
          '&:hover .pending-label': onPendingClick ? { textDecoration: 'underline' } : {},
        }}
      >
        <ExclamationCircleOutlined
          style={{ fontSize: theme.iconSizes.sm, color: theme.palette.warning.main, display: 'flex' }}
        />
        <Typography
          variant="body2"
          className="pending-label"
          color="warning.main"
          sx={{ fontWeight: 'medium' }}
        >
          {pending} to validate
        </Typography>
      </Stack>
    );
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
    // parseISO reads a date-only string as LOCAL midnight — `new Date("YYYY-MM-DD")`
    // parses it as UTC midnight, shifting the shown day back by one in any
    // negative-UTC timezone. R2 fix.
    const dateText = format(parseISO(dateField), "MMM d, yyyy");
    // Overdue is the backend's decision (date-vs-date, status-aware), never a
    // client recompute — `new Date("YYYY-MM-DD") < new Date()` marked today's
    // activities overdue. R2 fix.
    const isOverdue = Boolean(activity.is_overdue);

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

  // Square rounded TILE carrying the activity-type icon (radius from the theme).
  const avatar = (
    <Avatar
      variant="rounded"
      sx={{
        width: 56,
        height: 56,
        bgcolor: avatarColor,
        fontSize: "1.5rem",
        borderRadius: `${theme.aphoriQ.radius.md}px`,
      }}
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
        {/* Edit — opens the activity edit drawer. Inert for now; wired in S2c. */}
        <MenuItem>
          <ListItemIcon>
            <EditOutlined style={{ color: theme.palette.text.secondary }} />
          </ListItemIcon>
          <Typography>Edit</Typography>
        </MenuItem>
        <Divider />
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

  // The type now lives in the avatar tile, so the single chip is the STATUS —
  // discreet (light tint + full-colour text/border), the only filled-tone chip.
  const chips = [
    <Chip
      key="status"
      label={statusChipLabel}
      color={statusChipColor}
      size="small"
      variant="outlined"
      sx={{
        borderStyle: "solid",
        borderWidth: theme.aphoriQ.border.width.thin,
        fontWeight: "medium",
        ...STATUS_CHIP_TINT[statusChipColor],
      }}
    />,
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

    // AI status badge
    renderAIBadge(),

    // Pending counter badge
    renderPendingCounter(),
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
