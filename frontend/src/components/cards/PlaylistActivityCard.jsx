// frontend/src/components/cards/PlaylistActivityCard.jsx
/**
 * Playlist Activity Card — Collapsed/Expanded card for campaign playlist.
 *
 * 2 states:
 * - Collapsed: compact card with type, account, date, "Log Result" button
 * - Expanded: adds outcome chips + notes + Complete button
 *
 * Pattern: DecisionCycleTimeline ActivityCard (getBorderColor, getBgColor, OUTCOME_CONFIG, formatDate)
 * Pattern: ActivityOutcomeTab ResultSection (outcome selection + complete flow)
 */

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// material-ui
import { useTheme, alpha } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// icons
import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import MailOutlined from "@ant-design/icons/MailOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import CheckSquareOutlined from "@ant-design/icons/CheckSquareOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import ClockCircleOutlined from "@ant-design/icons/ClockCircleOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";

// ==============================|| ACTIVITY TYPE ICONS ||============================== //

const ACTIVITY_TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: MailOutlined,
  OTHER: CalendarOutlined,
};

const ACTIVITY_TYPE_COLORS = {
  CALL: "info",
  EMAIL: "warning",
  MEETING: "success",
  TASK: "secondary",
  LINKEDIN: "primary",
  OTHER: "default",
};

// ==============================|| OUTCOME CONFIG ||============================== //

/**
 * Activity Outcome Configuration — matches backend ActivityOutcome choices.
 * Copied from DecisionCycleTimeline.jsx for consistency.
 */
const ACTIVITY_OUTCOME_CONFIG = {
  SUCCESSFUL: { color: "success", label: "Successful", category: "positive" },
  MEETING_SCHEDULED: {
    color: "success",
    label: "Meeting Scheduled",
    category: "positive",
  },
  NO_ANSWER: { color: "warning", label: "No Answer", category: "neutral" },
  CALLBACK_REQUESTED: {
    color: "info",
    label: "Callback Requested",
    category: "neutral",
  },
  FOLLOW_UP_NEEDED: {
    color: "warning",
    label: "Follow-up Needed",
    category: "neutral",
  },
  OTHER: { color: "default", label: "Other", category: "neutral" },
  NOT_INTERESTED: {
    color: "error",
    label: "Not Interested",
    category: "negative",
  },
  WRONG_CONTACT: {
    color: "error",
    label: "Wrong Contact",
    category: "negative",
  },
};

// Ordered for display: positive first, then neutral, then negative
const OUTCOME_KEYS_ORDERED = [
  "SUCCESSFUL",
  "MEETING_SCHEDULED",
  "NO_ANSWER",
  "CALLBACK_REQUESTED",
  "FOLLOW_UP_NEEDED",
  "OTHER",
  "NOT_INTERESTED",
  "WRONG_CONTACT",
];

// ==============================|| DATE HELPERS ||============================== //

/**
 * Format date with relative display.
 * Pattern: DecisionCycleTimeline ActivityCard formatDate.
 */
function formatRelativeDate(dateStr) {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === tomorrow.toDateString()) return "Tomorrow";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";

  const diffDays = Math.ceil((date - today) / (1000 * 60 * 60 * 24));
  if (diffDays > 0 && diffDays <= 7) {
    return date.toLocaleDateString("en-US", { weekday: "short" });
  }

  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/**
 * Format time (HH:MM)
 */
function formatTime(timeStr) {
  if (!timeStr) return null;
  return timeStr.slice(0, 5);
}

// ==============================|| PLAYLIST ACTIVITY CARD ||============================== //

export default function PlaylistActivityCard({
  activity,
  expanded,
  onExpand,
  onComplete,
  completing,
}) {
  const theme = useTheme();

  // ==============================|| LOCAL STATE ||============================== //

  const [selectedOutcome, setSelectedOutcome] = useState(null);
  const [notes, setNotes] = useState("");

  // ==============================|| DERIVED VALUES ||============================== //

  const TypeIcon =
    ACTIVITY_TYPE_ICONS[activity.activity_type] || CalendarOutlined;
  const typeColor = ACTIVITY_TYPE_COLORS[activity.activity_type] || "default";
  const isCompleted = activity.status === "COMPLETED";
  const isCancelled = activity.status === "CANCELLED";
  const activityDate = activity.scheduled_date || activity.due_date;
  const isOverdue =
    activity.is_overdue ||
    (activityDate &&
      new Date(activityDate) < new Date() &&
      !isCompleted &&
      !isCancelled);

  // Outcome category (for completed activities)
  const outcomeConfig = activity.outcome
    ? ACTIVITY_OUTCOME_CONFIG[activity.outcome]
    : null;
  const outcomeCategory = outcomeConfig?.category || "neutral";

  // ==============================|| STYLE HELPERS ||============================== //

  const getBorderColor = () => {
    if (isCancelled) return theme.palette.grey[300];
    if (isCompleted) {
      if (outcomeCategory === "positive") return theme.palette.success.light;
      if (outcomeCategory === "negative") return theme.palette.error.light;
      return theme.palette.warning.light;
    }
    if (isOverdue) return theme.palette.error.light;
    return theme.palette.divider;
  };

  const getBgColor = () => {
    if (isCancelled) return alpha(theme.palette.grey[500], 0.04);
    if (isCompleted) {
      if (outcomeCategory === "positive")
        return alpha(theme.palette.success.main, 0.04);
      if (outcomeCategory === "negative")
        return alpha(theme.palette.error.main, 0.04);
      return alpha(theme.palette.warning.main, 0.04);
    }
    if (isOverdue) return alpha(theme.palette.error.main, 0.04);
    return "background.paper";
  };

  // ==============================|| HANDLERS ||============================== //

  const handleToggleExpand = () => {
    if (isCompleted || isCancelled) return;
    onExpand?.(expanded ? null : activity.id);
    // Reset form when collapsing
    if (expanded) {
      setSelectedOutcome(null);
      setNotes("");
    }
  };

  const handleOutcomeSelect = (outcomeKey) => {
    setSelectedOutcome(outcomeKey === selectedOutcome ? null : outcomeKey);
  };

  const handleComplete = () => {
    if (!selectedOutcome) return;
    onComplete?.(activity.id, {
      outcome: selectedOutcome,
      outcome_notes: notes || undefined,
    });
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Paper
      elevation={0}
      sx={{
        border: "1px solid",
        borderColor: getBorderColor(),
        borderRadius: 1.5,
        bgcolor: getBgColor(),
        overflow: "hidden",
        transition: "all 0.2s ease",
        opacity: isCancelled ? 0.6 : 1,
      }}
    >
      {/* ==================== COLLAPSED CONTENT ==================== */}
      <Box
        sx={{
          p: 2,
          cursor: isCompleted || isCancelled ? "default" : "pointer",
          "&:hover": {
            bgcolor:
              isCompleted || isCancelled ? "transparent" : "action.hover",
          },
        }}
        onClick={handleToggleExpand}
      >
        {/* Row 1: Type chip + Date + Action button */}
        <Stack
          direction="row"
          alignItems="center"
          justifyContent="space-between"
          spacing={1}
        >
          <Stack
            direction="row"
            alignItems="center"
            spacing={1}
            sx={{ flex: 1, minWidth: 0 }}
          >
            {/* Type chip */}
            <Chip
              icon={<TypeIcon style={{ fontSize: 14 }} />}
              label={activity.activity_type_display || activity.activity_type}
              size="small"
              color={typeColor}
              variant="outlined"
              sx={{
                height: 24,
                "& .MuiChip-label": { px: 0.75, fontSize: "0.75rem" },
              }}
            />

            {/* Title (truncated) */}
            <Typography
              variant="body2"
              fontWeight={500}
              noWrap
              sx={{ flex: 1 }}
            >
              {activity.title}
            </Typography>
          </Stack>

          {/* Date + Button */}
          <Stack
            direction="row"
            alignItems="center"
            spacing={1.5}
            sx={{ flexShrink: 0 }}
          >
            {activityDate && (
              <Stack direction="row" alignItems="center" spacing={0.5}>
                <ClockCircleOutlined
                  style={{
                    fontSize: 12,
                    color: isOverdue
                      ? theme.palette.error.main
                      : theme.palette.text.disabled,
                  }}
                />
                <Typography
                  variant="caption"
                  sx={{
                    color: isOverdue ? "error.main" : "text.secondary",
                    fontWeight: isOverdue ? 600 : 400,
                  }}
                >
                  {formatRelativeDate(activityDate)}
                </Typography>
                {activity.scheduled_time && (
                  <Typography variant="caption" color="text.disabled">
                    {formatTime(activity.scheduled_time)}
                  </Typography>
                )}
              </Stack>
            )}

            {/* Action button or completed badge */}
            {isCompleted && outcomeConfig ? (
              <Chip
                label={outcomeConfig.label}
                size="small"
                color={outcomeConfig.color}
                variant="filled"
                sx={{ height: 22, fontSize: "0.7rem" }}
              />
            ) : !isCompleted && !isCancelled ? (
              <Button
                size="small"
                variant={expanded ? "text" : "outlined"}
                color={expanded ? "inherit" : "primary"}
                onClick={(e) => {
                  e.stopPropagation();
                  handleToggleExpand();
                }}
                startIcon={expanded ? <CloseOutlined /> : undefined}
                sx={{
                  minWidth: expanded ? "auto" : 90,
                  height: 28,
                  fontSize: "0.75rem",
                  textTransform: "none",
                }}
              >
                {expanded ? "Close" : "Log Result"}
              </Button>
            ) : null}
          </Stack>
        </Stack>

        {/* Row 2: Account + Contacts count */}
        <Stack
          direction="row"
          alignItems="center"
          spacing={0.5}
          sx={{ mt: 0.75 }}
        >
          {activity.account && (
            <Typography variant="body2" color="text.primary" fontWeight={500}>
              {activity.account.company_name}
            </Typography>
          )}
          {activity.contacts_count > 0 && (
            <Typography variant="caption" color="text.disabled">
              · {activity.contacts_count} contact
              {activity.contacts_count > 1 ? "s" : ""}
            </Typography>
          )}
        </Stack>

        {/* Row 3: Call to action (if available) */}
        {activity.call_to_action && (
          <Typography
            variant="caption"
            color="text.secondary"
            noWrap
            sx={{ mt: 0.5, display: "block" }}
          >
            {activity.call_to_action}
          </Typography>
        )}
      </Box>

      {/* ==================== EXPANDED CONTENT ==================== */}
      {expanded && !isCompleted && !isCancelled && (
        <>
          <Divider />
          <Box sx={{ p: 2 }}>
            {/* Outcome chips */}
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ mb: 1, display: "block" }}
            >
              Select outcome
            </Typography>
            <Stack direction="row" flexWrap="wrap" gap={0.75} sx={{ mb: 2 }}>
              {OUTCOME_KEYS_ORDERED.map((key) => {
                const config = ACTIVITY_OUTCOME_CONFIG[key];
                const isSelected = selectedOutcome === key;
                return (
                  <Chip
                    key={key}
                    label={config.label}
                    size="small"
                    color={config.color}
                    variant={isSelected ? "filled" : "outlined"}
                    onClick={() => handleOutcomeSelect(key)}
                    sx={{
                      cursor: "pointer",
                      fontWeight: isSelected ? 600 : 400,
                      height: 28,
                      "& .MuiChip-label": { px: 1 },
                    }}
                  />
                );
              })}
            </Stack>

            {/* Notes field */}
            <TextField
              placeholder="Add notes (optional)..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              size="small"
              fullWidth
              multiline
              rows={2}
              sx={{ mb: 1.5 }}
            />

            {/* Complete button */}
            <Stack direction="row" justifyContent="flex-end">
              <Button
                variant="contained"
                color="success"
                size="small"
                disabled={!selectedOutcome || completing}
                onClick={handleComplete}
                startIcon={<CheckCircleOutlined />}
                sx={{ textTransform: "none" }}
              >
                {completing ? "Completing..." : "Complete"}
              </Button>
            </Stack>
          </Box>
        </>
      )}
    </Paper>
  );
}

PlaylistActivityCard.propTypes = {
  /** Activity object from playlist API (ActivityListSerializer shape) */
  activity: PropTypes.object.isRequired,
  /** Whether this card is currently expanded */
  expanded: PropTypes.bool,
  /** Callback to toggle expand — receives activityId or null */
  onExpand: PropTypes.func,
  /** Callback to complete activity — receives (activityId, {outcome, outcome_notes}) */
  onComplete: PropTypes.func,
  /** Whether a complete mutation is in progress */
  completing: PropTypes.bool,
};
