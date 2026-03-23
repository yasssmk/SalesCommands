// frontend/src/sections/campaigns/workspace/CampaignOutcomeModal.jsx
/**
 * Campaign Outcome Modal — 3-step wizard for logging activity outcomes.
 *
 * Step 1 — Group: Callback / No Answer / Successful / Fail
 * Step 2 — Detail: date (Callback), sub-options (Fail), notes
 * Step 3 — Scope: contact / department / account (outcomes_requires_confirmation only)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback } from "react";

// material-ui
import { useTheme, alpha } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// date picker
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";

// icons
import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import ClockCircleOutlined from "@ant-design/icons/ClockCircleOutlined";
import StopOutlined from "@ant-design/icons/StopOutlined";

// api
import {
  completePlaylistActivity,
  cancelPlannedActivities,
  recordCallNoAnswer,
} from "api/campaigns/campaigns";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// ==============================|| CONSTANTS ||============================== //

const STEP_GROUP = 0;
const STEP_DETAIL = 1;
const STEP_SCOPE = 2;

// Mirrors backend outcomes_requires_confirmation
const OUTCOMES_REQUIRES_SCOPE = new Set([
  "SUCCESSFUL",
  "POSITIVE_RESPONSE",
  "MEETING_SCHEDULED",
  "NOT_INTERESTED",
]);

const GROUPS = [
  {
    key: "callback",
    label: "Callback",
    description: "Schedule a callback for a later time",
    Icon: ClockCircleOutlined,
    iconColor: "warning.main",
  },
  {
    key: "no_answer",
    label: "No Answer",
    description: "No one picked up or responded",
    Icon: PhoneOutlined,
    iconColor: "text.secondary",
  },
  {
    key: "successful",
    label: "Successful",
    description: "Positive outcome — contact reached",
    Icon: CheckCircleOutlined,
    iconColor: "success.main",
  },
  {
    key: "fail",
    label: "Not Interested / Wrong Contact",
    description: "Contact is disqualified from this campaign",
    Icon: CloseCircleOutlined,
    iconColor: "error.main",
  },
];

const FAIL_OPTIONS = [
  { value: "NOT_INTERESTED", label: "Not Interested" },
  { value: "WRONG_CONTACT", label: "Wrong Contact" },
  { value: "UNSUBSCRIBE_OPTOUT", label: "Opt Out / Unsubscribe" },
];

// Map group + fail sub-option to backend outcome
function resolveOutcome(group, failOption) {
  if (group === "callback") return "CALLBACK_REQUESTED";
  if (group === "no_answer") return "NO_ANSWER";
  if (group === "successful") return "SUCCESSFUL";
  if (group === "fail") return failOption;
  return null;
}

// ==============================|| GROUP CARD ||============================== //

function GroupCard({ group, selected, onClick }) {
  const theme = useTheme();

  // Resolve MUI theme path (e.g. "warning.main") to hex
  const resolveColor = (path) => {
    const [palette, shade] = path.split(".");
    return theme.palette[palette]?.[shade] || theme.palette.text.secondary;
  };

  const color = resolveColor(group.iconColor);
  const { Icon } = group;

  return (
    <Box
      onClick={onClick}
      sx={{
        p: 1.75,
        borderRadius: 1.5,
        border: "1px solid",
        borderColor: selected ? color : "divider",
        bgcolor: selected ? alpha(color, 0.07) : "background.paper",
        cursor: "pointer",
        transition: "border-color 0.15s, background-color 0.15s",
        "&:hover": {
          borderColor: color,
          bgcolor: alpha(color, 0.04),
        },
      }}
    >
      <Stack direction="row" spacing={1.5} alignItems="center">
        <Icon style={{ fontSize: 18, color }} />
        <Box>
          <Typography variant="body2" fontWeight={600}>
            {group.label}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {group.description}
          </Typography>
        </Box>
      </Stack>
    </Box>
  );
}

GroupCard.propTypes = {
  group: PropTypes.object.isRequired,
  selected: PropTypes.bool.isRequired,
  onClick: PropTypes.func.isRequired,
};

// ==============================|| CAMPAIGN OUTCOME MODAL ||============================== //

export default function CampaignOutcomeModal({
  open,
  onClose,
  activity,
  campaignId,
  onComplete,
  onUpdate,
}) {
  const [step, setStep] = useState(STEP_GROUP);
  const [group, setGroup] = useState(null);
  const [notes, setNotes] = useState("");
  const [callbackDate, setCallbackDate] = useState(null);
  const [failOption, setFailOption] = useState("NOT_INTERESTED");
  const [scopeChoice, setScopeChoice] = useState("contact");
  const [submitting, setSubmitting] = useState(false);

  // ── Derived from activity ──
  const contacts = activity?.contacts || [];
  const account = activity?.account || null;
  const primaryContact = contacts[0] || null;
  const department = primaryContact?.standard_department || null;
  const contactName = primaryContact
    ? `${primaryContact.first_name || ""} ${primaryContact.last_name || ""}`.trim()
    : null;

  const currentOutcome = resolveOutcome(group, failOption);
  const requiresScope = OUTCOMES_REQUIRES_SCOPE.has(currentOutcome);
  const totalSteps = requiresScope ? 3 : 2;

  // ── Reset on close ──
  const handleClose = useCallback(() => {
    setStep(STEP_GROUP);
    setGroup(null);
    setNotes("");
    setCallbackDate(null);
    setFailOption("NOT_INTERESTED");
    setScopeChoice("contact");
    setSubmitting(false);
    onClose();
  }, [onClose]);

  // ── Step 1 → Step 2 ──
  const handleGroupSelect = useCallback((selectedGroup) => {
    setGroup(selectedGroup);
    setStep(STEP_DETAIL);
  }, []);

  // ── Step 2 → Step 3 or submit ──
  const handleDetailNext = useCallback(() => {
    const outcome = resolveOutcome(group, failOption);
    if (OUTCOMES_REQUIRES_SCOPE.has(outcome)) {
      setStep(STEP_SCOPE);
    } else {
      handleSubmit(group, failOption);
    }
  }, [group, failOption]);

  // ── Final submit ──
  const handleSubmit = useCallback(
    async (resolvedGroup = group, resolvedFailOption = failOption) => {
      setSubmitting(true);
      const outcome = resolveOutcome(resolvedGroup, resolvedFailOption);

      const payload = {
        outcome,
        outcome_notes: notes || undefined,
      };
      if (resolvedGroup === "callback" && callbackDate) {
        payload.callback_date = callbackDate.toISOString().split("T")[0];
      }

      try {
        // NO_ANSWER on a campaign CALL → dedicated retry endpoint
        const isCallNoAnswerRetry =
          resolvedGroup === "no_answer" &&
          activity?.activity_type === "CALL" &&
          !!activity?.campaign_contact_id;

        let result;
        let wasCompleted = true;

        if (isCallNoAnswerRetry) {
          const raw = await recordCallNoAnswer(activity.id, notes);
          // recordCallNoAnswer returns res.data directly (not wrapped in {success})
          const updatedStatus = raw?.data?.status || raw?.status;
          wasCompleted = updatedStatus === "COMPLETED";
          result = { success: true };
        } else {
          result = await completePlaylistActivity(
            activity.id,
            campaignId,
            payload,
          );
        }

        if (!result.success) {
          displayErrorSnackbar(result);
          setSubmitting(false);
          return;
        }

        // CALL retry not yet exhausted — close without removal or scope step
        if (!wasCompleted) {
          displaySuccessSnackbar("No answer recorded — activity rescheduled");
          onUpdate?.();
          handleClose();
          return;
        }

        // Scope cancellation — only when user reached step 3
        if (step === STEP_SCOPE && account?.id) {
          const scopePayload = { account_id: account.id };

          if (scopeChoice === "contact" && primaryContact?.id) {
            scopePayload.scope = "contact";
            scopePayload.contact_id = primaryContact.id;
          } else if (scopeChoice === "department" && department?.id) {
            scopePayload.scope = "department";
            scopePayload.department_id = department.id;
          } else {
            scopePayload.scope = "account";
          }

          await cancelPlannedActivities(campaignId, scopePayload);
        }

        displaySuccessSnackbar("Activity completed");
        onComplete?.(activity.id, outcome);
        handleClose();
      } catch (err) {
        displayErrorSnackbar(err);
        setSubmitting(false);
      }
    },
    [
      group,
      failOption,
      notes,
      callbackDate,
      step,
      scopeChoice,
      activity,
      campaignId,
      account,
      primaryContact,
      department,
      onComplete,
      handleClose,
    ],
  );

  const isDetailValid = group === "callback" ? !!callbackDate : true;

  // ── Step titles ──
  const STEP_TITLES = [
    "What was the outcome?",
    "Add details",
    "Other contacts on this account",
  ];

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      {/* ── Header ── */}
      <DialogTitle sx={{ pb: 1 }}>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="flex-start"
        >
          <Box>
            <Typography variant="subtitle1" fontWeight={600}>
              {STEP_TITLES[step]}
            </Typography>
            {activity?.title && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: "block", mt: 0.25 }}
                noWrap
              >
                {activity.title}
              </Typography>
            )}
          </Box>
          {step > STEP_GROUP && (
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ flexShrink: 0, ml: 1, mt: 0.25 }}
            >
              {step + 1} / {totalSteps}
            </Typography>
          )}
        </Stack>
      </DialogTitle>

      <Divider />

      {/* ── Content ── */}
      <DialogContent sx={{ pt: 2, pb: 1 }}>
        {/* STEP 0 — Group selection */}
        {step === STEP_GROUP && (
          <Stack spacing={1}>
            {GROUPS.map((g) => (
              <GroupCard
                key={g.key}
                group={g}
                selected={group === g.key}
                onClick={() => handleGroupSelect(g.key)}
              />
            ))}
          </Stack>
        )}

        {/* STEP 1 — Detail */}
        {step === STEP_DETAIL && (
          <Stack spacing={2}>
            {/* Callback: date picker */}
            {group === "callback" && (
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  label="Callback date *"
                  value={callbackDate}
                  onChange={setCallbackDate}
                  disablePast
                  slotProps={{
                    textField: { size: "small", fullWidth: true },
                  }}
                />
              </LocalizationProvider>
            )}

            {/* No Answer: confirmation label */}
            {group === "no_answer" && (
              <Box
                sx={{
                  p: 1.5,
                  borderRadius: 1,
                  bgcolor: "action.hover",
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  This attempt will be logged as <strong>No Answer</strong>. The
                  contact remains active in the sequence.
                </Typography>
              </Box>
            )}

            {/* Fail: sub-option radio */}
            {group === "fail" && (
              <RadioGroup
                value={failOption}
                onChange={(e) => setFailOption(e.target.value)}
              >
                {FAIL_OPTIONS.map((opt) => (
                  <FormControlLabel
                    key={opt.value}
                    value={opt.value}
                    control={<Radio size="small" />}
                    label={<Typography variant="body2">{opt.label}</Typography>}
                  />
                ))}
              </RadioGroup>
            )}

            {/* Notes — available for all groups */}
            <TextField
              label="Notes (optional)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              multiline
              rows={3}
              size="small"
              fullWidth
              placeholder="Add any relevant context..."
            />
          </Stack>
        )}

        {/* STEP 2 — Scope */}
        {step === STEP_SCOPE && (
          <Stack spacing={1.5}>
            <Typography variant="body2" color="text.secondary">
              Do you want to cancel remaining activities for other contacts on
              this account?
            </Typography>

            <RadioGroup
              value={scopeChoice}
              onChange={(e) => setScopeChoice(e.target.value)}
            >
              {/* Contact only */}
              <FormControlLabel
                value="contact"
                control={<Radio size="small" />}
                label={
                  <Typography variant="body2">
                    This contact only
                    {contactName && (
                      <Typography
                        component="span"
                        variant="caption"
                        color="text.secondary"
                        sx={{ ml: 0.5 }}
                      >
                        — {contactName}
                      </Typography>
                    )}
                  </Typography>
                }
              />

              {/* Department — only shown when contact has a department */}
              {department && (
                <FormControlLabel
                  value="department"
                  control={<Radio size="small" />}
                  label={
                    <Typography variant="body2">
                      Entire department
                      <Typography
                        component="span"
                        variant="caption"
                        color="text.secondary"
                        sx={{ ml: 0.5 }}
                      >
                        — {department.name}
                      </Typography>
                    </Typography>
                  }
                />
              )}

              {/* Entire account */}
              <FormControlLabel
                value="account"
                control={<Radio size="small" />}
                label={
                  <Typography variant="body2">
                    Entire account
                    {account?.company_name && (
                      <Typography
                        component="span"
                        variant="caption"
                        color="text.secondary"
                        sx={{ ml: 0.5 }}
                      >
                        — {account.company_name}
                      </Typography>
                    )}
                  </Typography>
                }
              />
            </RadioGroup>
          </Stack>
        )}
      </DialogContent>

      <Divider />

      {/* ── Actions ── */}
      <DialogActions sx={{ px: 3, py: 2 }}>
        {step === STEP_GROUP ? (
          <Button onClick={handleClose} color="inherit" size="small">
            Cancel
          </Button>
        ) : (
          <Button
            onClick={() => setStep((s) => s - 1)}
            color="inherit"
            size="small"
            disabled={submitting}
          >
            Back
          </Button>
        )}

        {step === STEP_DETAIL && (
          <Button
            onClick={handleDetailNext}
            variant="contained"
            size="small"
            disabled={!isDetailValid || submitting}
          >
            {requiresScope ? "Next" : submitting ? "Saving..." : "Complete"}
          </Button>
        )}

        {step === STEP_SCOPE && (
          <Button
            onClick={() => handleSubmit()}
            variant="contained"
            size="small"
            disabled={submitting}
          >
            {submitting ? "Saving..." : "Confirm & Complete"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}

CampaignOutcomeModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  activity: PropTypes.object,
  campaignId: PropTypes.string.isRequired,
  onComplete: PropTypes.func,
  onUpdate: PropTypes.func,
};
