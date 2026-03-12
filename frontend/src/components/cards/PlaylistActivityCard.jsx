// frontend/src/components/cards/PlaylistActivityCard.jsx
/**
 * Playlist Activity Card — Collapsed/Expanded card for campaign playlist.
 *
 * 2 states:
 * - Collapsed: compact card with type, account, date, "Log Result" button
 * - Expanded: outcome chips + notes + optional callback date + complete button
 *
 * Gaps fixed:
 * - sequence_position badge in header ("Step X")
 * - callback_date DatePicker when outcome = CALLBACK_REQUESTED
 * - Confirmation Dialog for terminal outcomes (NOT_INTERESTED, WRONG_CONTACT)
 * - handleComplete passes full payload {outcome, outcome_notes, callback_date?}
 */

"use client";

import PropTypes from "prop-types";
import { useState } from "react";

// material-ui
import { useTheme, alpha } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// date picker
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { TimePicker } from "@mui/x-date-pickers/TimePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";

// icons
import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import MailOutlined from "@ant-design/icons/MailOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import CheckSquareOutlined from "@ant-design/icons/CheckSquareOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import ClockCircleOutlined from "@ant-design/icons/ClockCircleOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import WarningOutlined from "@ant-design/icons/WarningOutlined";

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

// Activity types that complete in 1 click ("sent" semantics — no outcome picker needed)
const ONE_CLICK_TYPES = ["EMAIL", "LINKEDIN"];
const MAX_CALL_ATTEMPTS = 3;

// ==============================|| OUTCOME CONFIG ||============================== //

/**
 * Activity Outcome Configuration — matches backend ActivityOutcome choices.
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

// Ordered: positive first, then neutral, then negative
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

// Outcomes that require a confirmation dialog (cancel entire sequence chain)
const TERMINAL_OUTCOMES = ["NOT_INTERESTED", "WRONG_CONTACT"];

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

// ==============================|| CONFIRMATION DIALOG ||============================== //

/**
 * Confirmation dialog for terminal outcomes (NOT_INTERESTED, WRONG_CONTACT).
 * Warns the user that all remaining sequence activities for this contact will be cancelled.
 */
function TerminalOutcomeDialog({ open, outcome, onConfirm, onCancel }) {
  const theme = useTheme();
  const config = outcome ? ACTIVITY_OUTCOME_CONFIG[outcome] : null;

  return (
    <Dialog open={open} onClose={onCancel} maxWidth="xs" fullWidth>
      <DialogTitle>
        <Stack direction="row" alignItems="center" spacing={1}>
          <WarningOutlined
            style={{ color: theme.palette.error.main, fontSize: 20 }}
          />
          <span>Cancel sequence?</span>
        </Stack>
      </DialogTitle>
      <DialogContent>
        <DialogContentText>
          Marking this activity as <strong>{config?.label}</strong> will cancel
          all remaining sequence activities for this contact. This cannot be
          undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onCancel} color="inherit" size="small">
          Go back
        </Button>
        <Button
          onClick={onConfirm}
          color="error"
          variant="contained"
          size="small"
          sx={{ textTransform: "none" }}
        >
          Confirm &amp; cancel sequence
        </Button>
      </DialogActions>
    </Dialog>
  );
}

TerminalOutcomeDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  outcome: PropTypes.string,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
};

// ==============================|| PLAYLIST ACTIVITY CARD ||============================== //

export default function PlaylistActivityCard({
  activity,
  expanded,
  onExpand,
  onComplete,
  completing,
  isGreyedOut = false,
  campaignEndDate = null,
}) {
  const theme = useTheme();

  const [selectedOutcome, setSelectedOutcome] = useState(null);
  const [notes, setNotes] = useState("");
  const [callbackDate, setCallbackDate] = useState(null);
  const [callbackTime, setCallbackTime] = useState(null);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);

  const TypeIcon =
    ACTIVITY_TYPE_ICONS[activity.activity_type] || CalendarOutlined;
  const typeColor = ACTIVITY_TYPE_COLORS[activity.activity_type] || "default";
  const isCompleted = activity.status === "COMPLETED";
  const isCancelled = activity.status === "CANCELLED";
  const activityDate = activity.scheduled_date || activity.due_date;

  // Compare date strings (YYYY-MM-DD) to avoid UTC timezone drift.
  const todayStr = new Date().toLocaleDateString("en-CA");

  const isOverdue =
    !isGreyedOut &&
    activityDate &&
    activityDate < todayStr &&
    !isCompleted &&
    !isCancelled;

  // Activity scheduled beyond campaign planned end date — soft warning only
  const isBeyondEndDate =
    !isCompleted &&
    !isCancelled &&
    !isOverdue &&
    campaignEndDate &&
    activityDate &&
    activityDate > campaignEndDate;

  const outcomeConfig = activity.outcome
    ? ACTIVITY_OUTCOME_CONFIG[activity.outcome]
    : null;
  const outcomeCategory = outcomeConfig?.category || "neutral";

  const isCallbackOutcome = selectedOutcome === "CALLBACK_REQUESTED";
  const isTerminalOutcome = TERMINAL_OUTCOMES.includes(selectedOutcome);

  // CALL retry tracking — derived from CampaignAccount.no_answer_count via serializer.
  const isCall = activity.activity_type === "CALL";
  const noAnswerCount = activity.no_answer_count || 0;
  const attemptsLeft = isCall
    ? Math.max(0, MAX_CALL_ATTEMPTS - noAnswerCount)
    : null;
  // True when this NO_ANSWER click is a retry (activity stays PLANNED after submit).
  const isCallNoAnswerRetry =
    isCall && selectedOutcome === "NO_ANSWER" && attemptsLeft > 1;

  // Callback date is required when outcome = CALLBACK_REQUESTED
  const isCompleteDisabled =
    !selectedOutcome || completing || (isCallbackOutcome && !callbackDate);

  // ==============================|| STYLE HELPERS ||============================== //

  const getBorderColor = () => {
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

  // ==============================|| HANDLERS ||============================== //

  const handleToggleExpand = () => {
    if (isCompleted || isCancelled) return;
    onExpand?.(expanded ? null : activity.id);
    if (expanded) {
      setSelectedOutcome(null);
      setNotes("");
      setCallbackDate(null);
      setCallbackTime(null);
    }
  };

  const handleOutcomeSelect = (outcomeKey) => {
    setSelectedOutcome(outcomeKey === selectedOutcome ? null : outcomeKey);
    // Reset callback fields when switching away from CALLBACK_REQUESTED
    if (outcomeKey !== "CALLBACK_REQUESTED") {
      setCallbackDate(null);
      setCallbackTime(null);
    }
  };

  const handleCompleteClick = () => {
    if (!selectedOutcome) return;
    // Terminal outcomes require confirmation before submitting
    if (isTerminalOutcome) {
      setConfirmDialogOpen(true);
      return;
    }
    submitComplete();
  };

  const submitComplete = () => {
    const payload = {
      outcome: selectedOutcome,
      outcome_notes: notes || undefined,
    };
    // Flag for NO_ANSWER retry — tab intercepts to call record-no-answer instead of complete
    if (isCallNoAnswerRetry) {
      payload._is_no_answer_retry = true;
    }
    // Include callback fields only when relevant
    if (isCallbackOutcome && callbackDate) {
      payload.callback_date = callbackDate.toISOString().split("T")[0];
      if (callbackTime) {
        // Format HH:MM — backend stores in Activity.scheduled_time
        payload.callback_time = dayjs(callbackTime).format("HH:mm");
      }
    }
    onComplete?.(activity.id, payload);
  };

  const handleConfirmTerminal = () => {
    setConfirmDialogOpen(false);
    submitComplete();
  };

  const handleCancelConfirm = () => {
    setConfirmDialogOpen(false);
  };

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <Paper
        elevation={0}
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
        }}
      >
        <Box
          sx={{
            p: 2,
            cursor:
              isCompleted || isCancelled || isGreyedOut ? "default" : "pointer",
            "&:hover": {
              bgcolor:
                isCompleted || isCancelled || isGreyedOut
                  ? "transparent"
                  : "action.hover",
            },
          }}
          onClick={handleToggleExpand}
        >
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
              {activityDate && (
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
              )}

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
                  // 1-click complete for EMAIL / LINKEDIN — no outcome picker
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

              {/* Callback date + time — only when CALLBACK_REQUESTED */}
              {isCallbackOutcome && (
                <LocalizationProvider dateAdapter={AdapterDayjs}>
                  <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
                    <DatePicker
                      label="Callback date *"
                      value={callbackDate}
                      onChange={(newValue) => setCallbackDate(newValue)}
                      minDate={dayjs()}
                      slotProps={{
                        textField: {
                          size: "small",
                          fullWidth: true,
                          error: !callbackDate,
                          helperText: !callbackDate
                            ? "Callback date is required"
                            : campaignEndDate &&
                                callbackDate &&
                                callbackDate.isAfter(dayjs(campaignEndDate))
                              ? "Beyond campaign planned end date"
                              : undefined,
                        },
                      }}
                    />
                    <TimePicker
                      label="Time (optional)"
                      value={callbackTime}
                      onChange={(newValue) => setCallbackTime(newValue)}
                      slotProps={{
                        textField: {
                          size: "small",
                          fullWidth: true,
                        },
                      }}
                    />
                  </Stack>
                </LocalizationProvider>
              )}

              {/* Terminal outcome warning banner */}
              {isTerminalOutcome && (
                <Stack
                  direction="row"
                  spacing={1}
                  alignItems="flex-start"
                  sx={{
                    mb: 2,
                    p: 1.5,
                    borderRadius: 1,
                    bgcolor: alpha(theme.palette.error.main, 0.06),
                    border: "1px solid",
                    borderColor: alpha(theme.palette.error.main, 0.2),
                  }}
                >
                  <WarningOutlined
                    style={{
                      fontSize: 14,
                      color: theme.palette.error.main,
                      marginTop: 2,
                      flexShrink: 0,
                    }}
                  />
                  <Typography variant="caption" color="error.main">
                    This will cancel all remaining sequence activities for this
                    contact.
                  </Typography>
                </Stack>
              )}

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
                  color={isTerminalOutcome ? "error" : "success"}
                  size="small"
                  disabled={isCompleteDisabled}
                  onClick={handleCompleteClick}
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

      {/* Confirmation dialog for terminal outcomes */}
      <TerminalOutcomeDialog
        open={confirmDialogOpen}
        outcome={selectedOutcome}
        onConfirm={handleConfirmTerminal}
        onCancel={handleCancelConfirm}
      />
    </>
  );
}

PlaylistActivityCard.propTypes = {
  activity: PropTypes.object.isRequired,
  expanded: PropTypes.bool,
  onExpand: PropTypes.func,
  onComplete: PropTypes.func,
  completing: PropTypes.bool,
  isGreyedOut: PropTypes.bool,
  campaignEndDate: PropTypes.string, // YYYY-MM-DD
};
