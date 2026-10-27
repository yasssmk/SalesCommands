// frontend/src/components/cards/activities/ActivityMiniCard.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import RobotOutlined from "@ant-design/icons/RobotOutlined";

// Project imports
import StatusPill from "components/chips/StatusPill";
import { formatShortDate } from "components/signals/SignalLine";
import { getActivityTypeIcon, ACTIVITY_TYPE_ICON_COLOR } from "utils/activityTypes";
import {
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_CHIP_COLORS,
  ACTIVITY_OVERDUE_LABEL,
  ACTIVITY_OVERDUE_CHIP_COLORS,
} from "api/accounts/activities";

// ==============================|| ACTIVITY MINI CARD ||============================== //
//
// Sprint Next steps 5.9b (PO) — ONE line: left the type ICON
// (getActivityTypeIcon, ACTIVITY_TYPE_ICON_COLOR — no type chip) + the title;
// right step · date · the status pill (the shared StatusPill, the activity
// status tables, "Overdue" when late). Under the md breakpoint, back to two
// lines (title, then the meta). Consumers: UpcomingActivitiesSection (the next
// planned step), NextStepValidateFlow (the link candidates).

export default function ActivityMiniCard({
  activity: activityItem,
  onNavigate,
  onUnlink,
  showUnlink = false,
}) {
  const theme = useTheme();

  const TypeIcon = getActivityTypeIcon(activityItem.activity_type);
  const meta = [
    activityItem.decision_step_name,
    formatShortDate(activityItem.scheduled_date || activityItem.due_date),
  ].filter(Boolean);
  const fromAI = Boolean(activityItem.next_step_signal);
  const statusLabel = activityItem.is_overdue
    ? ACTIVITY_OVERDUE_LABEL
    : ACTIVITY_STATUS_LABELS[activityItem.status] || activityItem.status;
  const statusColors = activityItem.is_overdue
    ? ACTIVITY_OVERDUE_CHIP_COLORS
    : ACTIVITY_STATUS_CHIP_COLORS[activityItem.status] || ACTIVITY_STATUS_CHIP_COLORS.PLANNED;

  return (
    <Card
      variant="outlined"
      data-testid="activity-mini-card"
      sx={{
        p: 1.5,
        cursor: "pointer",
        transition: "all 0.15s ease-in-out",
        "&:hover": {
          bgcolor: "action.hover",
          borderColor: theme.palette.primary.light,
        },
      }}
      onClick={() => onNavigate(activityItem.id)}
    >
      <Stack
        data-testid="activity-mini-card-row"
        direction={{ xs: "column", md: "row" }}
        alignItems={{ xs: "stretch", md: "center" }}
        spacing={1}
      >
        {/* Left: type icon + title */}
        <Stack
          data-testid="activity-mini-card-main"
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ flex: 1, minWidth: 0 }}
        >
          <Box
            data-testid="activity-mini-card-type-icon"
            sx={{ display: "flex", flexShrink: 0, color: ACTIVITY_TYPE_ICON_COLOR }}
          >
            <TypeIcon style={{ fontSize: theme.iconSizes.sm }} />
          </Box>
          <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1, minWidth: 0 }}>
            {activityItem.title}
          </Typography>
        </Stack>

        {/* Right: step · date · status pill (+ from AI, unlink) */}
        <Stack
          data-testid="activity-mini-card-meta"
          direction="row"
          spacing={1}
          alignItems="center"
          sx={{ flexShrink: 0 }}
        >
          {meta.length > 0 && (
            <Typography variant="caption" color="text.secondary" noWrap>
              {meta.join(" · ")}
            </Typography>
          )}
          <StatusPill
            label={statusLabel}
            colorText={statusColors.text}
            colorBg={statusColors.background}
          />
          {fromAI && (
            <Chip
              icon={<RobotOutlined style={{ fontSize: 10 }} />}
              label="from AI"
              size="small"
              color="warning"
              variant="outlined"
              sx={{ height: 20, fontSize: "0.7rem" }}
            />
          )}
          {showUnlink && (
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onUnlink?.();
              }}
            >
              <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
          )}
        </Stack>
      </Stack>
    </Card>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityMiniCard.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string.isRequired,
    title: PropTypes.string,
    activity_type: PropTypes.string,
    status: PropTypes.string,
    is_overdue: PropTypes.bool,
    scheduled_date: PropTypes.string,
    due_date: PropTypes.string,
    decision_step_name: PropTypes.string,
    next_step_signal: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
  }).isRequired,
  onNavigate: PropTypes.func.isRequired,
  onUnlink: PropTypes.func,
  showUnlink: PropTypes.bool,
};
