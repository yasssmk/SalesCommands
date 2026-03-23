// frontend/src/components/cards/PlaylistActivityCard.jsx
/**
 * Playlist Activity Card — Compact card for campaign playlist.
 *
 * Collapsed only — no inline expand.
 * EMAIL/LINKEDIN: 1-click "Sent" button → onComplete(id, {outcome: 'NO_ANSWER'})
 * CALL/MEETING/TASK: "Log Result" button → onLogOutcome(activity)
 */

"use client";

import PropTypes from "prop-types";
import { useRouter } from "next/navigation";

// material-ui
import { useTheme, alpha } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// constants
import { OUTCOME_CONFIG } from "sections/campaigns/constants/campaignOutcomes";

// icons
import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import MailOutlined from "@ant-design/icons/MailOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import CheckSquareOutlined from "@ant-design/icons/CheckSquareOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import ClockCircleOutlined from "@ant-design/icons/ClockCircleOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";

// ==============================|| ACTIVITY TYPE CONFIG ||============================== //

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

// Activity types that complete in 1 click ("sent" semantics)
const ONE_CLICK_TYPES = ["EMAIL", "LINKEDIN"];
const MAX_CALL_ATTEMPTS = 3;

// ==============================|| DATE HELPERS ||============================== //

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

function formatTime(timeStr) {
  if (!timeStr) return null;
  return timeStr.slice(0, 5);
}

// ==============================|| PLAYLIST ACTIVITY CARD ||============================== //

export default function PlaylistActivityCard({
  activity,
  onComplete,
  onLogOutcome,
  completing,
  isGreyedOut = false,
}) {
  const theme = useTheme();

  const router = useRouter();

  const handleCardClick = () => {
    if (isGreyedOut) return;
    router.push(`/activities/${activity.id}`);
  };

  const TypeIcon =
    ACTIVITY_TYPE_ICONS[activity.activity_type] || CalendarOutlined;
  const typeColor = ACTIVITY_TYPE_COLORS[activity.activity_type] || "default";
  const isCompleted = activity.status === "COMPLETED";
  const isCancelled = activity.status === "CANCELLED";
  const isOnHold = activity.status === "ON_HOLD";
  const activityDate = activity.scheduled_date || activity.due_date;

  // Compare date strings (YYYY-MM-DD) to avoid UTC timezone drift.
  const todayStr = new Date().toLocaleDateString("en-CA");

  const isOverdue =
    !isGreyedOut &&
    activityDate &&
    activityDate < todayStr &&
    !isCompleted &&
    !isCancelled;

  const campaignEndDate = activity.campaign_end_date || null;
  const isBeyondEndDate =
    !isCompleted &&
    !isCancelled &&
    !isOverdue &&
    campaignEndDate &&
    activityDate &&
    activityDate > campaignEndDate;

  const outcomeConfig = activity.outcome
    ? OUTCOME_CONFIG[activity.outcome]
    : null;
  const outcomeCategory = outcomeConfig?.category || "neutral";

  // CALL retry tracking — derived from CampaignAccount.no_answer_count via serializer.
  const isCall = activity.activity_type === "CALL";
  const noAnswerCount = activity.no_answer_count || 0;
  const attemptsLeft = isCall
    ? Math.max(0, MAX_CALL_ATTEMPTS - noAnswerCount)
    : null;

  // ==============================|| STYLE HELPERS ||============================== //

  const getBorderColor = () => {
    if (isOnHold) return theme.palette.warning.light;
    if (isGreyedOut) return theme.palette.divider;
    if (isCancelled) return theme.palette.grey[300];
    if (isCompleted) {
      if (outcomeCategory === "positive") return theme.palette.success.light;
      if (outcomeCategory === "negative") return theme.palette.error.light;
      return theme.palette.warning.light;
    }
    if (isOverdue) return theme.palette.error.light;
    if (isBeyondEndDate) return theme.palette.warning.light;
    return theme.palette.divider;
  };

  const getBgColor = () => {
    if (isOnHold) return alpha(theme.palette.warning.main, 0.06);
    if (isGreyedOut) return alpha(theme.palette.grey[500], 0.03);
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

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <Paper
        elevation={0}
        onClick={handleCardClick}
        sx={{
          border: "1px solid",
          borderColor: getBorderColor(),
          borderRadius: 1.5,
          bgcolor: getBgColor(),
          overflow: "hidden",
          transition: "all 0.2s ease",
          opacity: isGreyedOut ? 0.55 : isCancelled ? 0.6 : 1,
          // Greyed out cards are display-only — no pointer interaction
          pointerEvents: isGreyedOut ? "none" : "auto",
          cursor: isGreyedOut ? "default" : "pointer",
          "&:hover": isGreyedOut
            ? {}
            : {
                borderColor: theme.palette.primary.light,
                boxShadow: `0 0 0 1px ${theme.palette.primary.light}`,
              },
        }}
      >
        <Box sx={{ p: 2 }}>
          {/* Row 1: Type chip + Step badge + Title + Date + Action button */}
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
              {/* Activity type chip */}
              <Chip
                icon={<TypeIcon style={{ fontSize: 14 }} />}
                label={activity.activity_type_display || activity.activity_type}
                size="small"
                color={typeColor}
                variant="outlined"
                sx={{
                  height: 24,
                  flexShrink: 0,
                  "& .MuiChip-label": { px: 0.75, fontSize: "0.75rem" },
                }}
              />

              {/* Sequence step badge — shown only when sequence_position is set */}
              {activity.sequence_position != null && (
                <Chip
                  label={`Step ${activity.sequence_position}`}
                  size="small"
                  variant="outlined"
                  color="default"
                  sx={{
                    height: 20,
                    flexShrink: 0,
                    "& .MuiChip-label": {
                      px: 0.75,
                      fontSize: "0.7rem",
                      color: "text.secondary",
                    },
                  }}
                />
              )}

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

            {/* Date + Action button */}
            <Stack
              direction="row"
              alignItems="center"
              spacing={1.5}
              sx={{ flexShrink: 0 }}
            >
              {isOnHold ? (
                <Chip
                  label="On Hold"
                  size="small"
                  color="warning"
                  variant="filled"
                  sx={{ height: 22, fontSize: "0.7rem" }}
                />
              ) : activityDate ? (
                <Stack direction="row" alignItems="center" spacing={0.5}>
                  <ClockCircleOutlined
                    style={{
                      fontSize: 12,
                      color: isOverdue
                        ? theme.palette.error.main
                        : isBeyondEndDate
                          ? theme.palette.warning.main
                          : theme.palette.text.disabled,
                    }}
                  />
                  <Typography
                    variant="caption"
                    sx={{
                      color: isOverdue
                        ? "error.main"
                        : isBeyondEndDate
                          ? "warning.main"
                          : "text.secondary",
                      fontWeight: isOverdue || isBeyondEndDate ? 600 : 400,
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
              ) : null}

              {/* CALL retry badge — shown when at least one attempt has been made */}
              {isCall && !isCompleted && !isCancelled && noAnswerCount > 0 && (
                <Chip
                  label={`${attemptsLeft} attempt${attemptsLeft !== 1 ? "s" : ""} left`}
                  size="small"
                  color={attemptsLeft === 1 ? "error" : "warning"}
                  variant="outlined"
                  sx={{ height: 20, fontSize: "0.65rem", mr: 0.5 }}
                />
              )}

              {/* Completed badge or action button */}
              {isCompleted && outcomeConfig ? (
                <Chip
                  label={outcomeConfig.label}
                  size="small"
                  color={outcomeConfig.color}
                  variant="filled"
                  sx={{ height: 22, fontSize: "0.7rem" }}
                />
              ) : !isCompleted && !isCancelled ? (
                ONE_CLICK_TYPES.includes(activity.activity_type) ? (
                  // 1-click for EMAIL / LINKEDIN
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    disabled={completing}
                    onClick={(e) => {
                      e.stopPropagation();
                      onComplete?.(activity.id, { outcome: "NO_ANSWER" });
                    }}
                    startIcon={<CheckCircleOutlined />}
                    sx={{
                      height: 28,
                      fontSize: "0.75rem",
                      textTransform: "none",
                    }}
                  >
                    {completing
                      ? "..."
                      : activity.activity_type === "LINKEDIN"
                        ? "Message Sent"
                        : "Email Sent"}
                  </Button>
                ) : (
                  // Opens CampaignOutcomeModal
                  <Button
                    size="small"
                    variant="outlined"
                    color="primary"
                    disabled={completing}
                    onClick={(e) => {
                      e.stopPropagation();
                      onLogOutcome?.(activity);
                    }}
                    sx={{
                      height: 28,
                      minWidth: 90,
                      fontSize: "0.75rem",
                      textTransform: "none",
                    }}
                  >
                    {completing ? "..." : "Log Result"}
                  </Button>
                )
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

          {/* Row 3: Call to action */}
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
      </Paper>
    </>
  );
}

PlaylistActivityCard.propTypes = {
  activity: PropTypes.object.isRequired,
  /** 1-click complete handler (EMAIL/LINKEDIN): (activityId, payload) => void */
  onComplete: PropTypes.func,
  /** Opens outcome modal: (activity) => void */
  onLogOutcome: PropTypes.func,
  completing: PropTypes.bool,
  isGreyedOut: PropTypes.bool,
};
