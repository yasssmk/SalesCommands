// frontend/src/sections/campaigns/CampaignOutcomeModal.jsx
/**
 * Campaign Outcome Modal — unified wizard for logging activity outcomes.
 *
 * Mode A — "Log Response" (from campaign header, no activity pre-selected):
 *   Step 1: Who answered? (contact from completed activities)
 *   Step 2: Which activity?
 *   Step 3: What was the outcome? (group selection)
 *   Step 4: Details (date / sub-option / notes)
 *   Step 5: Scope (cancel siblings — conditional on outcome)
 *
 * Mode B — "Log Outcome" (from PlaylistActivityCard, activity already known):
 *   Step 1: What was the outcome?
 *   Step 2: Details
 *   Step 3: Scope (conditional)
 *
 * Mode is detected automatically: if `activity` prop is provided → Mode B.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useCallback, useMemo, useEffect } from "react";

// material-ui
import { useTheme, alpha } from "@mui/material/styles";
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import Paper from "@mui/material/Paper";
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
import MailOutlined from "@ant-design/icons/MailOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import LinkedinOutlined from "@ant-design/icons/LinkedinOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import CheckCircleOutlined from "@ant-design/icons/CheckCircleOutlined";
import CloseCircleOutlined from "@ant-design/icons/CloseCircleOutlined";
import ClockCircleOutlined from "@ant-design/icons/ClockCircleOutlined";
import DownOutlined from "@ant-design/icons/DownOutlined";
import WarningOutlined from "@ant-design/icons/WarningOutlined";

// api
import {
  useGetCompletedActivities,
  completePlaylistActivity,
  cancelPlannedActivities,
  recordCallNoAnswer,
} from "api/campaigns/campaigns";

// components
import ActivityModal from "sections/accounts/activities/ActivityModal";

// utils
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// constants
import { CANCEL_TRIGGER_OUTCOMES } from "./constants/campaignOutcomes";

// ==============================|| STEP KEYS ||============================== //

const STEP = {
  CONTACT: "contact", // Mode A only
  ACTIVITY: "activity", // Mode A only
  GROUP: "group",
  DETAIL: "detail",
  NEXT_STEP: "next_step", // conditional — SUCCESSFUL / MEETING_SCHEDULED only
  SCOPE: "scope", // conditional
};

// Outcomes that trigger the "Create next step?" prompt
const NEXT_STEP_OUTCOMES = new Set(["SUCCESSFUL", "MEETING_SCHEDULED"]);

const MODE_A_BASE = [STEP.CONTACT, STEP.ACTIVITY, STEP.GROUP, STEP.DETAIL];
const MODE_B_BASE = [STEP.GROUP, STEP.DETAIL];

// ==============================|| OUTCOME GROUPS ||============================== //

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
  { value: "WRONG_EMAIL", label: "Wrong Email" },
  { value: "INVALID_PHONE_NUMBER", label: "Invalid Phone Number" },
];

const ACTIVITY_TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: CalendarOutlined,
};

const STEP_TITLES = {
  [STEP.CONTACT]: "Who answered?",
  [STEP.ACTIVITY]: "Which activity?",
  [STEP.GROUP]: "What was the outcome?",
  [STEP.DETAIL]: "Add details",
  [STEP.NEXT_STEP]: "Create a next step?",
  [STEP.SCOPE]: "Cancel other activities?",
};

function resolveOutcome(group, failOption) {
  if (group === "callback") return "CALLBACK_REQUESTED";
  if (group === "no_answer") return "NO_ANSWER";
  if (group === "successful") return "SUCCESSFUL";
  if (group === "fail") return failOption;
  return null;
}

// ==============================|| SUB-COMPONENTS ||============================== //

function GroupCard({ group, selected, onClick }) {
  const theme = useTheme();
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
        "&:hover": { borderColor: color, bgcolor: alpha(color, 0.04) },
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

// ── Mode A Step 1: contact selection ──
function StepContact({ completedActivities, selectedContactId, onSelect }) {
  const theme = useTheme();

  const accountGroups = useMemo(() => {
    const groups = {};
    completedActivities.forEach((a) => {
      if (!a.contacts?.length) return;
      const accountId = a.account?.id || "__no_account__";
      const accountName = a.account?.company_name || "No account";
      if (!groups[accountId])
        groups[accountId] = { name: accountName, contacts: [] };
      a.contacts.forEach((c) => {
        if (!groups[accountId].contacts.find((x) => x.id === c.id)) {
          groups[accountId].contacts.push(c);
        }
      });
    });
    return Object.entries(groups);
  }, [completedActivities]);

  const [expandedAccount, setExpandedAccount] = useState(
    () => accountGroups[0]?.[0] || null,
  );

  if (accountGroups.length === 0) {
    return (
      <Box sx={{ py: 4, textAlign: "center" }}>
        <Typography variant="body2" color="text.secondary">
          No contacts found. Complete at least one activity first.
        </Typography>
      </Box>
    );
  }

  return (
    <RadioGroup
      value={selectedContactId || ""}
      onChange={(e) => onSelect(e.target.value)}
    >
      <Stack spacing={1}>
        {accountGroups.map(([accountId, group]) => {
          const hasSelected = group.contacts.some(
            (c) => c.id === selectedContactId,
          );
          return (
            <Accordion
              key={accountId}
              disableGutters
              elevation={0}
              expanded={expandedAccount === accountId}
              onChange={(_, isExpanded) =>
                setExpandedAccount(isExpanded ? accountId : null)
              }
              sx={{
                border: "1px solid",
                borderColor: hasSelected ? "primary.main" : "divider",
                borderRadius: "8px !important",
                "&:before": { display: "none" },
                overflow: "hidden",
              }}
            >
              <AccordionSummary
                expandIcon={<DownOutlined style={{ fontSize: 11 }} />}
                sx={{ minHeight: 44, px: 1.5 }}
              >
                <Stack direction="row" alignItems="center" spacing={1}>
                  <Typography variant="body2" fontWeight={600}>
                    {group.name}
                  </Typography>
                  <Chip
                    label={group.contacts.length}
                    size="small"
                    color={hasSelected ? "primary" : "default"}
                    variant={hasSelected ? "filled" : "outlined"}
                    sx={{ height: 18, fontSize: "0.65rem" }}
                  />
                </Stack>
              </AccordionSummary>
              <AccordionDetails sx={{ pt: 0, pb: 1, px: 1.5 }}>
                <Stack spacing={0.75}>
                  {group.contacts.map((contact) => {
                    const isSelected = selectedContactId === contact.id;
                    return (
                      <Paper
                        key={contact.id}
                        elevation={0}
                        onClick={() => onSelect(contact.id)}
                        sx={{
                          p: 1.25,
                          border: "1px solid",
                          borderColor: isSelected ? "primary.main" : "divider",
                          borderRadius: 1.5,
                          cursor: "pointer",
                          bgcolor: isSelected
                            ? alpha(theme.palette.primary.main, 0.05)
                            : "transparent",
                          transition: "all 0.15s ease",
                          "&:hover": { borderColor: "primary.light" },
                        }}
                      >
                        <FormControlLabel
                          value={contact.id}
                          control={<Radio size="small" />}
                          label={
                            <Box>
                              <Typography
                                variant="body2"
                                fontWeight={isSelected ? 600 : 400}
                              >
                                {contact.first_name} {contact.last_name}
                              </Typography>
                              {(contact.job_title || contact.email) && (
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                >
                                  {contact.job_title || contact.email}
                                </Typography>
                              )}
                            </Box>
                          }
                          sx={{ m: 0, width: "100%" }}
                        />
                      </Paper>
                    );
                  })}
                </Stack>
              </AccordionDetails>
            </Accordion>
          );
        })}
      </Stack>
    </RadioGroup>
  );
}

StepContact.propTypes = {
  completedActivities: PropTypes.array.isRequired,
  selectedContactId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
};

// ── Mode A Step 2: activity selection ──
function StepActivity({
  completedActivities,
  selectedContactId,
  selectedActivityId,
  onSelect,
}) {
  const theme = useTheme();

  const filtered = useMemo(
    () =>
      completedActivities.filter((a) =>
        a.contacts?.some((c) => c.id === selectedContactId),
      ),
    [completedActivities, selectedContactId],
  );

  if (filtered.length === 0) {
    return (
      <Box sx={{ py: 4, textAlign: "center" }}>
        <Typography variant="body2" color="text.secondary">
          No activities found for this contact.
        </Typography>
      </Box>
    );
  }

  return (
    <RadioGroup
      value={selectedActivityId || ""}
      onChange={(e) => onSelect(e.target.value)}
    >
      <Stack spacing={1}>
        {filtered.map((a) => {
          const isSelected = selectedActivityId === a.id;
          const TypeIcon =
            ACTIVITY_TYPE_ICONS[a.activity_type] || CalendarOutlined;
          return (
            <Paper
              key={a.id}
              elevation={0}
              onClick={() => onSelect(a.id)}
              sx={{
                p: 1.5,
                border: "1px solid",
                borderColor: isSelected ? "primary.main" : "divider",
                borderRadius: 1.5,
                cursor: "pointer",
                bgcolor: isSelected
                  ? alpha(theme.palette.primary.main, 0.05)
                  : "background.paper",
                transition: "all 0.15s ease",
                "&:hover": { borderColor: "primary.light" },
              }}
            >
              <FormControlLabel
                value={a.id}
                control={<Radio size="small" />}
                label={
                  <Stack
                    direction="row"
                    alignItems="center"
                    spacing={1}
                    sx={{ width: "100%" }}
                  >
                    <TypeIcon
                      style={{
                        fontSize: 14,
                        color: theme.palette.text.secondary,
                      }}
                    />
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" fontWeight={600}>
                        {a.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {a.activity_type}
                        {a.completed_at
                          ? ` · ${a.completed_at.slice(0, 10)}`
                          : ""}
                      </Typography>
                    </Box>
                    {a.outcome && (
                      <Chip
                        label={a.outcome}
                        size="small"
                        variant="outlined"
                        sx={{ height: 20, fontSize: "0.65rem" }}
                      />
                    )}
                  </Stack>
                }
                sx={{ m: 0, width: "100%" }}
              />
            </Paper>
          );
        })}
      </Stack>
    </RadioGroup>
  );
}

StepActivity.propTypes = {
  completedActivities: PropTypes.array.isRequired,
  selectedContactId: PropTypes.string,
  selectedActivityId: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
};

// ==============================|| MAIN COMPONENT ||============================== //

export default function CampaignOutcomeModal({
  open,
  onClose,
  activity, // Mode B: PLANNED activity from playlist card
  campaignId, // required in Mode B (or derived from campaign)
  campaign, // Mode A: campaign object
  onComplete, // called after successful completion: (activityId, outcome) => void
  onUpdate, // called after any mutation to revalidate lists
}) {
  // ── Mode detection ──
  const isModeB = !!activity;
  const resolvedCampaignId = campaignId || campaign?.id;

  const [step, setStep] = useState(() => (isModeB ? STEP.GROUP : STEP.CONTACT));

  // Reset step to correct mode each time modal opens
  useEffect(() => {
    if (open) {
      setStep(isModeB ? STEP.GROUP : STEP.CONTACT);
    }
  }, [open, isModeB]);

  // ── Step navigation ──
  const initialStep = isModeB ? STEP.GROUP : STEP.CONTACT;

  // ── Mode A state ──
  const [selectedContactId, setSelectedContactId] = useState(null);
  const [selectedActivityId, setSelectedActivityId] = useState(null);

  // ── Shared outcome state ──
  const [group, setGroup] = useState(null);
  const [notes, setNotes] = useState("");
  const [callbackDate, setCallbackDate] = useState(null);
  const [failOption, setFailOption] = useState("NOT_INTERESTED");
  const [scopeChoice, setScopeChoice] = useState("contact");

  // ── UI state ──
  const [submitting, setSubmitting] = useState(false);
  const [confirmAccountScope, setConfirmAccountScope] = useState(false);
  const [activityModalOpen, setActivityModalOpen] = useState(false);

  // ── Completed activities (Mode A only) ──
  const { activities: completedActivities, completedActivitiesLoading } =
    useGetCompletedActivities(!isModeB && open ? resolvedCampaignId : null);

  // ── Active activity: from prop (B) or from selection (A) ──
  const activeActivity = isModeB
    ? activity
    : completedActivities.find((a) => a.id === selectedActivityId) || null;

  // ── Derive context from active activity ──
  const actContacts = activeActivity?.contacts || [];
  const account = activeActivity?.account_detail
    ?? (typeof activeActivity?.account === 'object' ? activeActivity.account : null);

  // In Mode A the user chose a specific contact; in Mode B use first contact.
  const primaryContact = isModeB
    ? actContacts[0] || null
    : actContacts.find((c) => c.id === selectedContactId) ||
      actContacts[0] ||
      null;

  const departmentId = primaryContact?.standard_department_id || null;
  const departmentName = primaryContact?.standard_department_name || null;
  const department = departmentId
    ? { id: departmentId, name: departmentName }
    : null;
  const contactName = primaryContact
    ? `${primaryContact.first_name || ""} ${primaryContact.last_name || ""}`.trim()
    : null;

  const currentOutcome = resolveOutcome(group, failOption);
  const requiresScope = CANCEL_TRIGGER_OUTCOMES.has(currentOutcome);

  // ── Ordered step list (scope appended conditionally at runtime) ──
  const baseSteps = isModeB ? MODE_B_BASE : MODE_A_BASE;

  // ── Reset on close ──
  const handleClose = useCallback(() => {
    setStep(isModeB ? STEP.GROUP : STEP.CONTACT);
    setSelectedContactId(null);
    setSelectedActivityId(null);
    setGroup(null);
    setNotes("");
    setCallbackDate(null);
    setFailOption("NOT_INTERESTED");
    setScopeChoice("contact");
    setSubmitting(false);
    setConfirmAccountScope(false);
    setActivityModalOpen(false);
    onClose();
  }, [onClose, isModeB]);

  // ── Contact select — reset activity (FRONT-02) ──
  const handleContactSelect = useCallback((contactId) => {
    setSelectedContactId(contactId);
    setSelectedActivityId(null); // reset activity when contact changes — FRONT-02
  }, []);

  // ── Group select → auto-advance to detail ──
  const handleGroupSelect = useCallback((selectedGroup) => {
    setGroup(selectedGroup);
    setStep(STEP.DETAIL);
  }, []);

  // ── Back navigation ──
  const handleBack = useCallback(() => {
    const fullSteps = requiresScope ? [...baseSteps, STEP.SCOPE] : baseSteps;
    const idx = fullSteps.indexOf(step);
    if (idx > 0) setStep(fullSteps[idx - 1]);
  }, [step, baseSteps, requiresScope]);

  // ── Core submit ──
  const handleSubmit = useCallback(async () => {
    if (!activeActivity) return;
    setSubmitting(true);

    const outcome = resolveOutcome(group, failOption);
    const payload = { outcome, outcome_notes: notes || undefined };
    if (group === "callback" && callbackDate) {
      payload.callback_date = callbackDate.toISOString().split("T")[0];
    }

    try {
      // NO_ANSWER on a CALL in Mode B only (Mode A activities are already COMPLETED)
      const isCallNoAnswerRetry =
        isModeB &&
        group === "no_answer" &&
        activeActivity.activity_type === "CALL" &&
        !!activeActivity.campaign_contact_id;

      let result;
      let wasCompleted = true;

      if (isCallNoAnswerRetry) {
        const raw = await recordCallNoAnswer(activeActivity.id, notes);
        const updatedStatus = raw?.data?.status || raw?.status;
        wasCompleted = updatedStatus === "COMPLETED";
        result = { success: true };
      } else {
        result = await completePlaylistActivity(
          activeActivity.id,
          resolvedCampaignId,
          payload,
        );
      }

      // FRONT-06: always verify result
      if (!result.success) {
        displayErrorSnackbar(result);
        setSubmitting(false);
        return;
      }

      // CALL retry not yet exhausted — close without scope step
      if (!wasCompleted) {
        displaySuccessSnackbar("No answer recorded — activity rescheduled");
        onUpdate?.(); // FRONT-01
        handleClose();
        return;
      }

      // Scope cancellation when outcome requires it
      if (CANCEL_TRIGGER_OUTCOMES.has(outcome) && account?.id) {
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

        const cancelResult = await cancelPlannedActivities(
          resolvedCampaignId,
          scopePayload,
        );
        // FRONT-06: verify cancel result
        if (!cancelResult.success) {
          displayErrorSnackbar(cancelResult);
          setSubmitting(false);
          return;
        }
      }

      displaySuccessSnackbar("Activity completed");
      onComplete?.(activeActivity.id, outcome);
      onUpdate?.(); // FRONT-01
      handleClose();
    } catch (err) {
      displayErrorSnackbar(err);
      setSubmitting(false);
    }
  }, [
    group,
    failOption,
    scopeChoice,
    notes,
    callbackDate,
    activeActivity,
    isModeB,
    resolvedCampaignId,
    account,
    primaryContact,
    department,
    onComplete,
    onUpdate,
    handleClose,
  ]);

  // ── Detail step next ──
  const handleDetailNext = useCallback(() => {
    // SUCCESSFUL / MEETING_SCHEDULED → propose creating a next step first
    if (NEXT_STEP_OUTCOMES.has(currentOutcome)) {
      setStep(STEP.NEXT_STEP);
    } else if (requiresScope) {
      setStep(STEP.SCOPE);
    } else {
      handleSubmit();
    }
  }, [currentOutcome, requiresScope, handleSubmit]);

  const handleNextStepContinue = useCallback(() => {
    // Called after ActivityModal closes (created or skipped)
    setActivityModalOpen(false);
    if (requiresScope) {
      setStep(STEP.SCOPE);
    } else {
      handleSubmit();
    }
  }, [requiresScope, handleSubmit]);

  // ── Scope confirm — intercept account for confirmation (FRONT-03) ──
  const handleScopeConfirm = useCallback(() => {
    if (scopeChoice === "account") {
      setConfirmAccountScope(true);
    } else {
      handleSubmit();
    }
  }, [scopeChoice, handleSubmit]);

  // ── Step validity ──
  const isStepValid = () => {
    if (step === STEP.CONTACT) return !!selectedContactId;
    if (step === STEP.ACTIVITY) return !!selectedActivityId;
    if (step === STEP.GROUP) return !!group;
    if (step === STEP.DETAIL)
      return group === "callback" ? !!callbackDate : true;
    return true;
  };

  const isFirstStep = step === initialStep;

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
        {/* Header */}
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
              {activeActivity?.title && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: "block", mt: 0.25 }}
                  noWrap
                >
                  {activeActivity.title}
                </Typography>
              )}
            </Box>
          </Stack>
        </DialogTitle>

        <Divider />

        {/* Content */}
        <DialogContent sx={{ pt: 2, pb: 1, minHeight: 220 }}>
          {/* Mode A — Step: Contact */}
          {step === STEP.CONTACT &&
            (completedActivitiesLoading ? (
              <Box sx={{ py: 4, textAlign: "center" }}>
                <Typography variant="body2" color="text.secondary">
                  Loading…
                </Typography>
              </Box>
            ) : (
              <StepContact
                completedActivities={completedActivities}
                selectedContactId={selectedContactId}
                onSelect={handleContactSelect}
              />
            ))}

          {/* Mode A — Step: Activity */}
          {step === STEP.ACTIVITY && (
            <StepActivity
              completedActivities={completedActivities}
              selectedContactId={selectedContactId}
              selectedActivityId={selectedActivityId}
              onSelect={setSelectedActivityId}
            />
          )}

          {/* Step: Group */}
          {step === STEP.GROUP && (
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

          {/* Step: Detail */}
          {step === STEP.DETAIL && (
            <Stack spacing={2}>
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

              {group === "no_answer" && (
                <Box sx={{ p: 1.5, borderRadius: 1, bgcolor: "action.hover" }}>
                  <Typography variant="body2" color="text.secondary">
                    This attempt will be logged as <strong>No Answer</strong>.
                    The contact remains active in the sequence.
                  </Typography>
                </Box>
              )}

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
                      label={
                        <Typography variant="body2">{opt.label}</Typography>
                      }
                    />
                  ))}
                </RadioGroup>
              )}

              <TextField
                label="Notes (optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                multiline
                rows={3}
                size="small"
                fullWidth
                placeholder="Add any relevant context…"
              />
            </Stack>
          )}

          {/* Step: Next Step (SUCCESSFUL / MEETING_SCHEDULED only) */}
          {step === STEP.NEXT_STEP && (
            <Stack spacing={2}>
              <Typography variant="body2" color="text.secondary">
                Would you like to create a follow-up activity and link it to a
                decision cycle?
              </Typography>
              <Stack spacing={1}>
                <Button
                  variant="contained"
                  fullWidth
                  onClick={() => setActivityModalOpen(true)}
                >
                  Create a decision cycle activity
                </Button>
                <Button
                  variant="outlined"
                  color="inherit"
                  fullWidth
                  onClick={handleNextStepContinue}
                >
                  Skip
                </Button>
              </Stack>

              {/* ActivityModal — mounted inline, does not close CampaignOutcomeModal */}
              {activeActivity && (
                <ActivityModal
                  open={activityModalOpen}
                  onClose={() => setActivityModalOpen(false)}
                  accountId={activeActivity?.account_detail?.id ?? (typeof activeActivity?.account === 'string' ? activeActivity.account : activeActivity?.account?.id)}
                  sourceActivityId={activeActivity.id}
                  defaultActivityType="MEETING"
                  onSuccess={() => {
                    // Activity created — continue to scope step
                    handleNextStepContinue();
                  }}
                />
              )}
            </Stack>
          )}

          {/* Step: Scope */}
          {step === STEP.SCOPE && (
            <Stack spacing={1.5}>
              <Typography variant="body2" color="text.secondary">
                Do you want to cancel remaining activities for other contacts on
                this account?
              </Typography>
              <RadioGroup
                value={scopeChoice}
                onChange={(e) => setScopeChoice(e.target.value)}
              >
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

        {/* Actions */}
        <DialogActions sx={{ px: 3, py: 2 }}>
          {isFirstStep ? (
            <Button
              onClick={handleClose}
              color="inherit"
              size="small"
              disabled={submitting}
            >
              Cancel
            </Button>
          ) : (
            <Button
              onClick={handleBack}
              color="inherit"
              size="small"
              disabled={submitting}
            >
              Back
            </Button>
          )}

          {/* Contact / Activity steps: explicit Next */}
          {(step === STEP.CONTACT || step === STEP.ACTIVITY) && (
            <Button
              variant="contained"
              size="small"
              disabled={!isStepValid()}
              onClick={() => {
                if (step === STEP.CONTACT) setStep(STEP.ACTIVITY);
                if (step === STEP.ACTIVITY) setStep(STEP.GROUP);
              }}
            >
              Next
            </Button>
          )}

          {/* Next Step: no footer buttons — actions are inline in the content */}
          {step === STEP.NEXT_STEP && null}

          {/* Detail: next or complete */}
          {step === STEP.DETAIL && (
            <Button
              variant="contained"
              size="small"
              disabled={!isStepValid() || submitting}
              onClick={handleDetailNext}
            >
              {requiresScope ? "Next" : submitting ? "Saving…" : "Complete"}
            </Button>
          )}

          {/* Scope: confirm */}
          {step === STEP.SCOPE && (
            <Button
              variant="contained"
              size="small"
              disabled={submitting}
              onClick={handleScopeConfirm}
            >
              {submitting ? "Saving…" : "Confirm & Complete"}
            </Button>
          )}
        </DialogActions>
      </Dialog>

      {/* FRONT-03: confirmation before account-wide cancel */}
      <Dialog
        open={confirmAccountScope}
        onClose={() => setConfirmAccountScope(false)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>
          <Stack direction="row" alignItems="center" spacing={1}>
            <WarningOutlined style={{ fontSize: 18 }} />
            <span>Cancel all activities?</span>
          </Stack>
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            This will cancel all remaining planned activities for the entire
            account{account?.company_name ? ` (${account.company_name})` : ""}.
            This cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button
            onClick={() => setConfirmAccountScope(false)}
            color="inherit"
            size="small"
          >
            Cancel
          </Button>
          <Button
            onClick={() => {
              setConfirmAccountScope(false);
              handleSubmit();
            }}
            variant="contained"
            color="error"
            size="small"
          >
            Confirm
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

CampaignOutcomeModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  activity: PropTypes.object, // Mode B
  campaignId: PropTypes.string, // Mode B (or derived from campaign)
  campaign: PropTypes.object, // Mode A
  onComplete: PropTypes.func,
  onUpdate: PropTypes.func,
};
