// frontend/src/sections/campaigns/workspace/LogResponseModal.jsx
/**
 * Log Response Wizard — 3-step modal for logging an async response.
 *
 * Step 1 — Who answered? (contact from completed activities)
 * Step 2 — Which activity? (completed activities for that contact)
 * Step 3 — What was the result? (outcome + optional date + notes)
 */

"use client";

import PropTypes from "prop-types";
import { useState, useMemo } from "react";

// material-ui
import { useTheme, alpha } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Modal from "@mui/material/Modal";
import Paper from "@mui/material/Paper";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import FormControlLabel from "@mui/material/FormControlLabel";
import Stack from "@mui/material/Stack";
import Step from "@mui/material/Step";
import StepLabel from "@mui/material/StepLabel";
import Stepper from "@mui/material/Stepper";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// date picker
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";

// project imports
import MainCard from "components/MainCard";
import {
  useGetCompletedActivities,
  logCampaignResponse,
} from "api/campaigns/campaigns";
import {
  displaySuccessSnackbar,
  displayErrorSnackbar,
} from "utils/displayError";

// icons
import PhoneOutlined from "@ant-design/icons/PhoneOutlined";
import MailOutlined from "@ant-design/icons/MailOutlined";
import TeamOutlined from "@ant-design/icons/TeamOutlined";
import LinkedinOutlined from "@ant-design/icons/LinkedinOutlined";
import CalendarOutlined from "@ant-design/icons/CalendarOutlined";
import ArrowLeftOutlined from "@ant-design/icons/ArrowLeftOutlined";
import ArrowRightOutlined from "@ant-design/icons/ArrowRightOutlined";

// ==============================|| CONSTANTS ||============================== //

const STEPS = ["Who answered?", "Which activity?", "What was the result?"];

const ACTIVITY_TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: CalendarOutlined,
};

const ACTIVITY_TYPE_COLORS = {
  CALL: "info",
  EMAIL: "warning",
  MEETING: "success",
  LINKEDIN: "primary",
  OTHER: "default",
};

const RESPONSE_OPTIONS = [
  { value: "POSITIVE", label: "Positive response", color: "success" },
  { value: "MEETING_BOOKED", label: "Meeting booked", color: "success" },
  { value: "CALLBACK_REQUESTED", label: "Callback requested", color: "info" },
  { value: "NO_RESPONSE", label: "No response", color: "default" },
  { value: "NEGATIVE", label: "Not interested", color: "error" },
];

const RESPONSES_WITH_DATE = ["MEETING_BOOKED", "CALLBACK_REQUESTED"];

// ==============================|| STEP 1 — WHO ANSWERED ||============================== //

function StepWhoAnswered({ completedActivities, selectedContactId, onSelect }) {
  const theme = useTheme();

  // Extract unique contacts from completed activities
  const contacts = useMemo(() => {
    const seen = new Set();
    const result = [];
    completedActivities.forEach((a) => {
      if (!a.contacts || a.contacts.length === 0) return;
      a.contacts.forEach((c) => {
        if (!seen.has(c.id)) {
          seen.add(c.id);
          result.push({ ...c, account_name: a.account?.company_name });
        }
      });
    });
    return result;
  }, [completedActivities]);

  if (contacts.length === 0) {
    return (
      <Box sx={{ py: 4, textAlign: "center" }}>
        <Typography variant="body2" color="text.secondary">
          No contacts found. Complete at least one activity or make a call
          attempt first.
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
        {contacts.map((contact) => {
          const isSelected = selectedContactId === contact.id;
          return (
            <Paper
              key={contact.id}
              elevation={0}
              onClick={() => onSelect(contact.id)}
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
                value={contact.id}
                control={<Radio size="small" />}
                label={
                  <Box>
                    <Typography variant="body2" fontWeight={600}>
                      {contact.first_name} {contact.last_name}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {contact.job_title || contact.email || "—"}
                      {contact.account_name ? ` · ${contact.account_name}` : ""}
                    </Typography>
                  </Box>
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

// ==============================|| STEP 2 — WHICH ACTIVITY ||============================== //

function StepWhichActivity({
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
        {filtered.map((activity) => {
          const isSelected = selectedActivityId === activity.id;
          const TypeIcon =
            ACTIVITY_TYPE_ICONS[activity.activity_type] || CalendarOutlined;
          const typeColor =
            ACTIVITY_TYPE_COLORS[activity.activity_type] || "default";
          // PLANNED = call in progress (contact called back before retries exhausted)
          const isPending = activity.status === "PLANNED";

          return (
            <Paper
              key={activity.id}
              elevation={0}
              onClick={() => onSelect(activity.id)}
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
                value={activity.id}
                control={<Radio size="small" />}
                label={
                  <Stack
                    direction="row"
                    alignItems="center"
                    spacing={1}
                    sx={{ width: "100%" }}
                  >
                    <Box sx={{ flex: 1 }}>
                      <Typography variant="body2" fontWeight={600}>
                        {activity.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {activity.activity_type}
                        {activity.scheduled_date
                          ? ` · ${activity.scheduled_date}`
                          : ""}
                      </Typography>
                    </Box>
                    {isPending && (
                      <Chip
                        label="In progress"
                        size="small"
                        color="warning"
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

// ==============================|| STEP 3 — RESULT ||============================== //

function StepResult({
  response,
  onResponseChange,
  responseDate,
  onDateChange,
  notes,
  onNotesChange,
}) {
  const theme = useTheme();
  const needsDate = RESPONSES_WITH_DATE.includes(response);

  return (
    <Stack spacing={2.5}>
      {/* Response options */}
      <RadioGroup
        value={response || ""}
        onChange={(e) => onResponseChange(e.target.value)}
      >
        <Stack spacing={1}>
          {RESPONSE_OPTIONS.map((opt) => {
            const isSelected = response === opt.value;
            return (
              <Paper
                key={opt.value}
                elevation={0}
                onClick={() => onResponseChange(opt.value)}
                sx={{
                  p: 1.5,
                  border: "1px solid",
                  borderColor: isSelected ? `${opt.color}.main` : "divider",
                  borderRadius: 1.5,
                  cursor: "pointer",
                  bgcolor: isSelected
                    ? alpha(
                        theme.palette[opt.color]?.main ||
                          theme.palette.primary.main,
                        0.05,
                      )
                    : "background.paper",
                  transition: "all 0.15s ease",
                }}
              >
                <FormControlLabel
                  value={opt.value}
                  control={
                    <Radio
                      size="small"
                      color={opt.color === "default" ? "primary" : opt.color}
                    />
                  }
                  label={
                    <Typography
                      variant="body2"
                      fontWeight={isSelected ? 600 : 400}
                    >
                      {opt.label}
                    </Typography>
                  }
                  sx={{ m: 0, width: "100%" }}
                />
              </Paper>
            );
          })}
        </Stack>
      </RadioGroup>

      {/* Date picker — conditional */}
      {needsDate && (
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DatePicker
            label={
              response === "MEETING_BOOKED" ? "Meeting date" : "Callback date"
            }
            value={responseDate}
            onChange={onDateChange}
            slotProps={{
              textField: { fullWidth: true, size: "small", required: true },
            }}
          />
        </LocalizationProvider>
      )}

      {/* Notes */}
      <TextField
        placeholder="Add notes (optional)..."
        value={notes}
        onChange={(e) => onNotesChange(e.target.value)}
        size="small"
        fullWidth
        multiline
        rows={2}
      />
    </Stack>
  );
}

// ==============================|| LOG RESPONSE MODAL ||============================== //

export default function LogResponseModal({
  open,
  onClose,
  campaign,
  onSuccess,
}) {
  const [activeStep, setActiveStep] = useState(0);
  const [selectedContactId, setSelectedContactId] = useState(null);
  const [selectedActivityId, setSelectedActivityId] = useState(null);
  const [response, setResponse] = useState(null);
  const [responseDate, setResponseDate] = useState(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const { activities: completedActivities, completedActivitiesLoading } =
    useGetCompletedActivities(open ? campaign?.id : null);

  const isStepValid = () => {
    if (activeStep === 0) return !!selectedContactId;
    if (activeStep === 1) return !!selectedActivityId;
    if (activeStep === 2) {
      if (!response) return false;
      if (RESPONSES_WITH_DATE.includes(response) && !responseDate) return false;
      return true;
    }
    return false;
  };

  const handleNext = () => setActiveStep((s) => s + 1);
  const handleBack = () => setActiveStep((s) => s - 1);

  const handleClose = () => {
    setActiveStep(0);
    setSelectedContactId(null);
    setSelectedActivityId(null);
    setResponse(null);
    setResponseDate(null);
    setNotes("");
    onClose();
  };

  const handleContactSelect = (contactId) => {
    setSelectedContactId(contactId);
    // Reset activity selection when contact changes
    setSelectedActivityId(null);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload = {
        activity_id: selectedActivityId,
        response,
        notes: notes || undefined,
        response_date: responseDate
          ? responseDate.format("YYYY-MM-DD")
          : undefined,
      };

      const result = await logCampaignResponse(campaign.id, payload);

      if (result.success) {
        displaySuccessSnackbar("Response logged successfully");
        onSuccess?.();
        handleClose();
      } else {
        displayErrorSnackbar(result);
      }
    } catch (err) {
      displayErrorSnackbar(err);
    } finally {
      setSubmitting(false);
    }
  };

  const renderStep = () => {
    if (completedActivitiesLoading) {
      return (
        <Box sx={{ py: 6, display: "flex", justifyContent: "center" }}>
          <CircularProgress size={32} />
        </Box>
      );
    }
    if (activeStep === 0)
      return (
        <StepWhoAnswered
          completedActivities={completedActivities}
          selectedContactId={selectedContactId}
          onSelect={handleContactSelect}
        />
      );
    if (activeStep === 1)
      return (
        <StepWhichActivity
          completedActivities={completedActivities}
          selectedContactId={selectedContactId}
          selectedActivityId={selectedActivityId}
          onSelect={setSelectedActivityId}
        />
      );
    return (
      <StepResult
        response={response}
        onResponseChange={setResponse}
        responseDate={responseDate}
        onDateChange={setResponseDate}
        notes={notes}
        onNotesChange={setNotes}
      />
    );
  };

  return (
    <Modal open={open} onClose={handleClose}>
      <MainCard
        sx={{
          width: "calc(100% - 48px)",
          maxWidth: 520,
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          maxHeight: "calc(100vh - 48px)",
          display: "flex",
          flexDirection: "column",
        }}
        modal
        content={false}
      >
        {/* Header */}
        <Box sx={{ p: 2.5, pb: 2, flexShrink: 0 }}>
          <Typography variant="h5">Log Response</Typography>
          {campaign?.name && (
            <Typography variant="caption" color="text.secondary">
              {campaign.name}
            </Typography>
          )}
        </Box>

        <Divider sx={{ flexShrink: 0 }} />

        {/* Stepper */}
        <Box sx={{ px: 3, py: 2, flexShrink: 0 }}>
          <Stepper activeStep={activeStep} alternativeLabel>
            {STEPS.map((label, i) => (
              <Step key={label} completed={i < activeStep}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>

        <Divider sx={{ flexShrink: 0 }} />

        {/* Step content */}
        <Box
          sx={{
            px: 3,
            py: 2.5,
            flexGrow: 1,
            overflowY: "auto",
            minHeight: 200,
          }}
        >
          {renderStep()}
        </Box>

        <Divider sx={{ flexShrink: 0 }} />

        {/* Footer */}
        <Box sx={{ px: 3, py: 2, flexShrink: 0 }}>
          <Stack direction="row" justifyContent="space-between">
            <Stack direction="row" spacing={1}>
              <Button color="error" onClick={handleClose} disabled={submitting}>
                Cancel
              </Button>
              {activeStep > 0 && (
                <Button
                  variant="outlined"
                  startIcon={<ArrowLeftOutlined />}
                  onClick={handleBack}
                  disabled={submitting}
                >
                  Back
                </Button>
              )}
            </Stack>

            {activeStep < 2 ? (
              <Button
                variant="contained"
                endIcon={<ArrowRightOutlined />}
                onClick={handleNext}
                disabled={!isStepValid()}
              >
                Next
              </Button>
            ) : (
              <Button
                variant="contained"
                color="success"
                onClick={handleSubmit}
                disabled={!isStepValid() || submitting}
                startIcon={
                  submitting ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : null
                }
              >
                {submitting ? "Saving..." : "Confirm"}
              </Button>
            )}
          </Stack>
        </Box>
      </MainCard>
    </Modal>
  );
}

LogResponseModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  campaign: PropTypes.object,
  onSuccess: PropTypes.func,
};
