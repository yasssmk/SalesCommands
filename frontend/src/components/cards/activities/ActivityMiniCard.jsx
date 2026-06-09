// frontend/src/components/cards/activities/ActivityMiniCard.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import { useTheme } from "@mui/material/styles";
import Card from "@mui/material/Card";
import Chip from "@mui/material/Chip";
import IconButton from "@mui/material/IconButton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import RobotOutlined from "@ant-design/icons/RobotOutlined";

// Project imports
import {
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS,
} from "api/accounts/activities";

// ==============================|| ACTIVITY MINI CARD ||============================== //

function formatDate(dateStr) {
  if (!dateStr) return null;
  return new Date(dateStr).toLocaleDateString();
}

export default function ActivityMiniCard({
  activity: activityItem,
  onNavigate,
  onUnlink,
  showUnlink = false,
}) {
  const theme = useTheme();

  const displayDate = activityItem.scheduled_date || activityItem.due_date;
  const stepName = activityItem.decision_step_name;
  const fromAI = Boolean(activityItem.next_step_signal);

  return (
    <Card
      variant="outlined"
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
      <Stack spacing={1}>
        {/* Row 1: Type + Title */}
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Chip
            label={
              ACTIVITY_TYPE_LABELS[activityItem.activity_type] ||
              activityItem.activity_type
            }
            size="small"
            variant="outlined"
            sx={{ minWidth: 80 }}
          />
          <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1 }}>
            {activityItem.title}
          </Typography>
          {showUnlink && (
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                onUnlink?.();
              }}
              sx={{ ml: "auto" }}
            >
              <CloseOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
          )}
        </Stack>

        {/* Row 2: Meta info (step, date, status, from-AI) */}
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
        >
          {stepName && (
            <Chip
              label={stepName}
              size="small"
              variant="filled"
              sx={{
                height: 20,
                fontSize: "0.7rem",
                bgcolor: theme.palette.grey[100],
                color: theme.palette.text.secondary,
              }}
            />
          )}
          {displayDate && (
            <Typography variant="caption" color="text.secondary">
              {formatDate(displayDate)}
            </Typography>
          )}
          <Chip
            label={
              activityItem.is_overdue
                ? "Overdue"
                : ACTIVITY_STATUS_LABELS[activityItem.status] ||
                  activityItem.status
            }
            size="small"
            color={
              activityItem.is_overdue
                ? "error"
                : ACTIVITY_STATUS_COLORS[activityItem.status] || "default"
            }
            sx={{ height: 20, fontSize: "0.7rem" }}
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
