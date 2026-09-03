// frontend/src/sections/activities/workspace/ActivityHeader.jsx
/**
 * Activity Header — hook feeding the shared WorkspaceHeader (opaque slots).
 *
 * Returns layout props + modals JSX (title is read-only — no onTitleSave):
 *   { avatar, title, titleAdornment, headerActions, chips, infoItems, modals }
 * titleAdornment is the status pill (Row 1, next to the title); chips is empty.
 *
 * Usage in index.jsx:
 *   const headerProps = useActivityHeaderProps({ activity });
 *   <WorkspaceHeader {...headerProps} />
 *   {headerProps.modals}
 */

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

// MUI
import { useTheme } from "@mui/material/styles";
import Avatar from "@mui/material/Avatar";
import IconButton from "@mui/material/IconButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Date formatting
import { format, formatDistanceToNow, parseISO } from "date-fns";

// API
import {
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS,
  ACTIVITY_STATUS_CHIP_COLORS,
} from "api/accounts/activities";

// Primitives
import StatusPill from "components/chips/StatusPill";

// Pipeline state
import { PIPELINE_STATE } from "hooks/usePipelineRunner";

// Modals
import AlertActivityDelete from "sections/accounts/activities/AlertActivityDelete";

// Icons
import {
  MoreOutlined,
  EditOutlined,
  CheckCircleOutlined,
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

// ==============================|| ACTIVITY HEADER PROPS HOOK ||============================== //

export default function useActivityHeaderProps({
  activity,
  // onSave / isLocked are no longer consumed here — the header title is
  // read-only (inline edit removed; editing happens in the edit drawer, S2c).
  // The page still passes onSave (handleSaveField) to ActivityNotesTab, so the
  // page-level handler is NOT dead — only this hook stopped reading it.
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

  // Delete confirmation (the only status/lifecycle action left in the ⋮ menu —
  // Complete/Cancel/Reopen now happen via the Edit drawer, S2c).
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // ==============================|| EARLY RETURN (no data) ||============================== //

  if (!activity) {
    return { avatar: null, title: "", chips: [], infoItems: [], modals: null };
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const TypeIcon = TYPE_ICONS[activity.activity_type] || QuestionCircleOutlined;
  const avatarColor = TYPE_AVATAR_COLORS[activity.activity_type] || "grey.500";

  // Status → semantic colour role and label come from the front activities
  // constants (ACTIVITY_STATUS_COLORS / ACTIVITY_STATUS_LABELS), never hardcoded.
  const statusChipColor = ACTIVITY_STATUS_COLORS[activity.status] || "default";
  const statusChipLabel =
    ACTIVITY_STATUS_LABELS[activity.status] || activity.status;

  const isCompleted = activity.status === "COMPLETED";
  const isCancelled = activity.status === "CANCELLED";

  // Delete is offered for standalone activities only (unchanged gate).
  const isCampaignActivity =
    Boolean(activity.campaign_detail) && !activity.decision_cycle;

  // ==============================|| HANDLERS — Actions menu ||============================== //

  const handleMenuOpen = (event) => setAnchorEl(event.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

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

  // Square rounded TILE carrying the activity-type icon. Both the tile and the
  // icon are sized from the theme's iconSizes scale (no hardcoded px): the icon
  // is the `xl` glyph, the tile twice that — a compact tile that matches the
  // mockup. Radius from the aphoriQ token.
  const tileIconSize = theme.iconSizes.xl;
  const avatar = (
    <Avatar
      variant="rounded"
      sx={{
        width: tileIconSize * 2,
        height: tileIconSize * 2,
        bgcolor: avatarColor,
        fontSize: tileIconSize,
        borderRadius: `${theme.aphoriQ.radius.md}px`,
      }}
    >
      <TypeIcon />
    </Avatar>
  );

  // ==============================|| ROW 1: Title ||============================== //

  // Read-only title — inline editing is removed; editing happens in the edit
  // drawer (S2c). We no longer pass onTitleSave/titleDisabled to the shell.
  const title = activity.title || "";

  // ==============================|| ROW 1: Status pill (title adornment) ||============================== //

  // A compact PILL next to the title, rendered with the shared StatusPill: dark
  // background + status-coloured text AND border, from the {text, background}
  // table in the activities constants. Contour now visible (3-part chip).
  const chipStyle =
    ACTIVITY_STATUS_CHIP_COLORS[activity.status] || ACTIVITY_STATUS_CHIP_COLORS.PLANNED;
  const titleAdornment = (
    <StatusPill
      data-status-color={statusChipColor}
      label={statusChipLabel}
      colorText={chipStyle.text}
      colorBg={chipStyle.background}
    />
  );

  // ==============================|| ROW 1: Actions (⋯ menu) ||============================== //

  const headerActions = (
    <>
      <IconButton onClick={handleMenuOpen}>
        <MoreOutlined />
      </IconButton>
      <Menu anchorEl={anchorEl} open={menuOpen} onClose={handleMenuClose}>
        {/* Edit — opens the activity edit drawer (status change happens here).
            Inert for now; wired in S2c. Shown even though it is not connected. */}
        <MenuItem>
          <ListItemIcon>
            <EditOutlined style={{ color: theme.palette.text.secondary }} />
          </ListItemIcon>
          <Typography>Edit</Typography>
        </MenuItem>
        {/* Delete — existing action, wired as before (standalone activities). */}
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

  // Empty — the status now renders as a pill next to the title (titleAdornment,
  // Row 1), and the type lives in the avatar tile. No Row 2 chips for Activity.
  const chips = [];

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
    titleAdornment,
    headerActions,
    chips,
    infoItems,
    modals,
  };
}
