// frontend/src/sections/accounts/activities/ActivityModal.jsx
/**
 * Activity Modal Component
 *
 * Modal for creating and editing activities.
 * Supports inline creation of Contact and Decision Cycle.
 *
 * Note: Decision Steps (Pipeline Steps) are FIXED and auto-created when a cycle
 * is created. Users SELECT from existing steps, they cannot create new ones.
 * When a cycle is selected, a step selection is REQUIRED.
 *
 * UX Goal: Allow activity creation in <30 seconds even when prerequisite
 * entities don't exist yet.
 */

"use client";

import PropTypes from "prop-types";
import { useState, useEffect, useMemo } from "react";

// material-ui
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Modal from "@mui/material/Modal";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import FormHelperText from "@mui/material/FormHelperText";

// date pickers
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { TimePicker } from "@mui/x-date-pickers/TimePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import dayjs from "dayjs";

// third-party
import { useFormik } from "formik";
import * as Yup from "yup";

// project imports
import MainCard from "components/MainCard";
import {
  InlineContactForm,
  InlineCycleForm,
  PIPELINE_STEPS,
} from "./components";
import {
  createActivity,
  createActivityWithEntities,
  updateActivity,
  useGetActivityChoices,
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUSES,
  ACTIVITY_STATUS_LABELS,
} from "api/accounts/activities";

// Icons for inline creation
import PlusOutlined from "@ant-design/icons/PlusOutlined";

import { useGetContacts } from "api/businessData/contacts";
import {
  useGetDecisionCyclesByAccount,
  useGetDecisionStepsByCycle,
} from "api/accounts/decisionCycles";
import {
  displayErrorSnackbar,
  displaySuccessSnackbar,
} from "utils/displayError";

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object(
  {
    title: Yup.string()
      .required("Title is required")
      .max(255, "Title must be at most 255 characters"),
    activity_type: Yup.string().required("Activity type is required"),
    status: Yup.string().required("Status is required"),
    description: Yup.string()
      .max(2000, "Description must be at most 2000 characters")
      .nullable(),
    call_to_action: Yup.string()
      .max(500, "Call to action must be at most 500 characters")
      .nullable(),
    scheduled_date: Yup.date()
      .nullable()
      .typeError("Please select a valid date")
      .when("due_date", {
        is: (dueDate) => !dueDate,
        then: (schema) =>
          schema.required("Scheduled date or due date is required"),
        otherwise: (schema) => schema.nullable(),
      }),
    due_date: Yup.date().nullable().typeError("Please select a valid date"),
    contact_ids: Yup.array().of(Yup.string()),
    has_inline_contact: Yup.boolean(),
    decision_cycle_id: Yup.string().nullable(),
    decision_step_id: Yup.string()
      .nullable()
      .when("decision_cycle_id", {
        is: (cycleId) => Boolean(cycleId),
        then: (schema) =>
          schema.required("Please select a pipeline step for this cycle"),
        otherwise: (schema) => schema.nullable(),
      }),
  },
  [["scheduled_date", "due_date"]],
);

// ==============================|| ACTIVITY MODAL ||============================== //

export default function ActivityModal({
  open,
  onClose,
  activity = null,
  accountId,
  decisionStepId = null,
  decisionCycleId = null,
  defaultActivityType = null,
  previousActivityId = null,
  sourceActivityId = null,
  nextStepSignal = null,
  onSuccess,
}) {
  const [submitting, setSubmitting] = useState(false);

  // Inline creation modes
  const [showInlineContact, setShowInlineContact] = useState(false);
  const [showInlineCycle, setShowInlineCycle] = useState(false);

  // Inline creation data
  const [inlineContact, setInlineContact] = useState(null);
  const [inlineCycle, setInlineCycle] = useState(null);
  const [inlineStepStage, setInlineStepStage] = useState("QUALIFICATION");

  const isEditMode = Boolean(activity?.id);

  // Fetch choices (skip when modal is closed)
  const { choicesLoading } = useGetActivityChoices(open);

  // Fetch contacts for the account (skip when modal is closed)
  const { contacts, contactsLoading } = useGetContacts(
    open ? { filters: { account_id: accountId }, pageSize: 100 } : null,
  );

  // Contact options for autocomplete
  const contactOptions = useMemo(() => {
    if (!contacts || contacts.length === 0) return [];
    return contacts.map((contact) => ({
      id: contact.id,
      label:
        `${contact.first_name || ""} ${contact.last_name || ""}`.trim() ||
        contact.email,
      email: contact.email,
      job_title: contact.job_title,
    }));
  }, [contacts]);

  // Fetch decision cycles for the account (skip when modal is closed)
  const { cycles, cyclesLoading } = useGetDecisionCyclesByAccount(
    open ? accountId : null,
  );

  // Cycle options for dropdown
  const cycleOptions = useMemo(() => {
    if (!cycles || cycles.length === 0) return [];
    return cycles.map((cycle) => ({
      id: cycle.id,
      name: cycle.name,
      is_active: cycle.is_active,
    }));
  }, [cycles]);

  // Pre-fill from nextStepSignal when converting an AI suggestion
  const signalContactIds = useMemo(() => {
    if (!nextStepSignal?.suggested_contacts) return [];
    return nextStepSignal.suggested_contacts.map((c) => c.id);
  }, [nextStepSignal]);

  // Build initial values
  const initialValues = useMemo(
    () => ({
      title: activity?.title || nextStepSignal?.suggested_title || "",
      activity_type:
        activity?.activity_type ||
        nextStepSignal?.suggested_activity_type ||
        defaultActivityType ||
        "MEETING",
      status: activity?.status || "PLANNED",
      description: activity?.description || "",
      call_to_action: activity?.call_to_action || "",
      scheduled_date: activity?.scheduled_date
        ? dayjs(activity.scheduled_date)
        : nextStepSignal?.suggested_due_date
          ? dayjs(nextStepSignal.suggested_due_date)
          : null,
      scheduled_time: activity?.scheduled_time
        ? dayjs(`2000-01-01T${activity.scheduled_time}`)
        : null,
      due_date: activity?.due_date ? dayjs(activity.due_date) : null,
      contact_ids:
        activity?.contacts?.map((c) => c.id) ||
        (signalContactIds.length > 0 ? signalContactIds : []),
      has_inline_contact: false,
      decision_cycle_id: activity?.decision_cycle || decisionCycleId || "",
      decision_step_id: activity?.decision_step || decisionStepId || "",
    }),
    [activity, nextStepSignal, signalContactIds, defaultActivityType, decisionCycleId, decisionStepId],
  );

  // Formik setup
  const formik = useFormik({
    initialValues,
    validationSchema,
    enableReinitialize: true,
    onSubmit: async (values) => {
      setSubmitting(true);

      try {
        // Guard: at least one contact (selected or inline)
        if (values.contact_ids.length === 0 && !values.has_inline_contact) {
          formik.setFieldError(
            "contact_ids",
            "At least one contact is required",
          );
          formik.setFieldTouched("contact_ids", true, false);
          setSubmitting(false);
          return;
        }

        // Build activity payload
        const activityPayload = {
          title: values.title.trim(),
          activity_type: values.activity_type,
          status: values.status,
          description: values.description?.trim() || null,
          call_to_action: values.call_to_action?.trim() || null,
          scheduled_date: values.scheduled_date
            ? dayjs(values.scheduled_date).format("YYYY-MM-DD")
            : null,
          scheduled_time: values.scheduled_time
            ? dayjs(values.scheduled_time).format("HH:mm:ss")
            : null,
          due_date: values.due_date
            ? dayjs(values.due_date).format("YYYY-MM-DD")
            : null,
          contact_ids: values.contact_ids || [],
        };

        let result;

        if (isEditMode) {
          // Edit mode - use standard update
          activityPayload.decision_cycle_id = values.decision_cycle_id || null;
          activityPayload.decision_step_id = values.decision_step_id || null;
          result = await updateActivity(activity.id, activityPayload);
        } else {
          // Create mode - check if we need inline entity creation
          const hasInlineEntities = inlineContact || inlineCycle;

          if (hasInlineEntities) {
            // Use multi-entity creation endpoint
            activityPayload.account_id = accountId;

            if (!inlineCycle) {
              activityPayload.decision_cycle_id =
                values.decision_cycle_id || null;
            }

            activityPayload.decision_step_id = values.decision_step_id || null;

            if (previousActivityId) {
              activityPayload.previous_activity_id = previousActivityId;
            }
            if (sourceActivityId) {
              activityPayload.source_activity_id = sourceActivityId;
            }
            if (nextStepSignal?.id) {
              activityPayload.next_step_signal_id = nextStepSignal.id;
            }

            result = await createActivityWithEntities({
              activity: activityPayload,
              inline_contact: inlineContact || null,
              inline_cycle: inlineCycle || null,
              inline_step_stage: inlineCycle ? inlineStepStage : null,
            });
          } else {
            // Standard creation
            activityPayload.account_id = accountId;
            activityPayload.decision_cycle_id =
              values.decision_cycle_id || null;
            activityPayload.decision_step_id = values.decision_step_id || null;

            if (previousActivityId) {
              activityPayload.previous_activity_id = previousActivityId;
            }
            if (sourceActivityId) {
              activityPayload.source_activity_id = sourceActivityId;
            }
            if (nextStepSignal?.id) {
              activityPayload.next_step_signal_id = nextStepSignal.id;
            }

            result = await createActivity(activityPayload);
          }
        } // <- accolade manquante

        if (result.success) {
          const createdEntities = result.data?.created_entities;
          let message = isEditMode
            ? "Activity updated successfully"
            : "Activity created successfully";

          if (createdEntities) {
            const parts = [];
            if (createdEntities.contact) parts.push("contact");
            if (createdEntities.cycle) parts.push("cycle");
            if (createdEntities.step) parts.push("step");
            if (parts.length > 0) {
              message += ` (with new ${parts.join(", ")})`;
            }
          }

          displaySuccessSnackbar(message);
          onSuccess?.(result.data?.activity || result.data);
          handleClose();
        } else {
          displayErrorSnackbar(result);
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setSubmitting(false);
      }
    },
  });

  const {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    handleSubmit,
    resetForm,
    setFieldValue,
  } = formik;

  // Fetch decision steps based on selected cycle (skip when modal is closed)
  const { steps, stepsLoading } = useGetDecisionStepsByCycle(
    open ? values.decision_cycle_id : null,
  );

  // Step options for dropdown
  const stepOptions = useMemo(() => {
    if (!steps || steps.length === 0) return [];
    return steps.map((step) => ({
      id: step.id,
      name: step.name,
      status: step.status,
    }));
  }, [steps]);

  useEffect(() => {
    if (
      values.decision_cycle_id !==
      (activity?.decision_cycle || decisionCycleId || "")
    ) {
      setFieldValue("decision_step_id", "");
    }
  }, [
    values.decision_cycle_id,
    activity?.decision_cycle,
    decisionCycleId,
    setFieldValue,
  ]);

  useEffect(() => {
    if (open) {
      resetForm({ values: initialValues });
      setShowInlineContact(false);
      setShowInlineCycle(false);
      setInlineContact(null);
      setInlineCycle(null);
      setInlineStepStage("QUALIFICATION");
    }
  }, [open, initialValues, resetForm]);

  const handleClose = () => {
    resetForm();
    onClose();
  };

  const selectedContacts = useMemo(() => {
    return contactOptions.filter((c) => values.contact_ids.includes(c.id));
  }, [contactOptions, values.contact_ids]);

  if (choicesLoading) {
    return (
      <Modal open={open} onClose={handleClose}>
        <MainCard
          sx={{
            width: "calc(100% - 48px)",
            maxWidth: 600,
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
          }}
          modal
          content={false}
        >
          <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
            <CircularProgress />
          </Box>
        </MainCard>
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="modal-activity-title"
      sx={{
        "& .MuiPaper-root:focus": { outline: "none" },
      }}
    >
      <MainCard
        sx={{
          width: "calc(100% - 48px)",
          minWidth: 340,
          maxWidth: 800,
          maxHeight: "calc(100vh - 48px)",
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        }}
        modal
        content={false}
      >
        <Box
          sx={{
            maxHeight: "calc(100vh - 48px)",
            overflowY: "auto",
          }}
        >
          <Box component="form" onSubmit={handleSubmit}>
            <Box sx={{ p: 2.5, pb: 2 }}>
              <Typography variant="h5" id="modal-activity-title">
                {isEditMode ? "Edit Activity" : "Create Activity"}
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 0.5 }}
              >
                {isEditMode
                  ? "Update activity details"
                  : "Add a new activity to track your sales actions"}
              </Typography>
            </Box>

            <Divider />

            <Box sx={{ p: 2.5 }}>
              <Grid container spacing={2.5}>
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="title" required>
                      Title
                    </InputLabel>
                    <TextField
                      id="title"
                      name="title"
                      fullWidth
                      placeholder="e.g., Follow-up call with John"
                      value={values.title}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(touched.title && errors.title)}
                      helperText={touched.title && errors.title}
                    />
                  </Stack>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="activity_type" required>
                      Type
                    </InputLabel>
                    <Select
                      id="activity_type"
                      name="activity_type"
                      fullWidth
                      value={values.activity_type}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(
                        touched.activity_type && errors.activity_type,
                      )}
                    >
                      {Object.entries(ACTIVITY_TYPES).map(([key, value]) => (
                        <MenuItem key={key} value={value}>
                          {ACTIVITY_TYPE_LABELS[key]}
                        </MenuItem>
                      ))}
                    </Select>
                    {touched.activity_type && errors.activity_type && (
                      <FormHelperText error>
                        {errors.activity_type}
                      </FormHelperText>
                    )}
                  </Stack>
                </Grid>

                {/* Status field — only shown in edit mode.
                    New activities are always created with PLANNED status (enforced by backend). */}
                {isEditMode && (
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel htmlFor="status" required>
                        Status
                      </InputLabel>
                      <Select
                        id="status"
                        name="status"
                        fullWidth
                        value={values.status}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        error={Boolean(touched.status && errors.status)}
                      >
                        {Object.entries(ACTIVITY_STATUSES).map(
                          ([key, value]) => (
                            <MenuItem key={key} value={value}>
                              {ACTIVITY_STATUS_LABELS[key]}
                            </MenuItem>
                          ),
                        )}
                      </Select>
                      {touched.status && errors.status && (
                        <FormHelperText error>{errors.status}</FormHelperText>
                      )}
                    </Stack>
                  </Grid>
                )}

                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel required={!values.due_date}>
                      Scheduled Date
                    </InputLabel>
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                      <DatePicker
                        value={values.scheduled_date}
                        onChange={(newValue) =>
                          setFieldValue("scheduled_date", newValue)
                        }
                        slotProps={{
                          textField: {
                            fullWidth: true,
                            error: Boolean(
                              touched.scheduled_date && errors.scheduled_date,
                            ),
                            helperText:
                              touched.scheduled_date && errors.scheduled_date,
                          },
                        }}
                      />
                    </LocalizationProvider>
                  </Stack>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel>Scheduled Time</InputLabel>
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                      <TimePicker
                        value={values.scheduled_time}
                        onChange={(newValue) =>
                          setFieldValue("scheduled_time", newValue)
                        }
                        slotProps={{
                          textField: {
                            fullWidth: true,
                          },
                        }}
                      />
                    </LocalizationProvider>
                  </Stack>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel>Due Date</InputLabel>
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                      <DatePicker
                        value={values.due_date}
                        onChange={(newValue) =>
                          setFieldValue("due_date", newValue)
                        }
                        slotProps={{
                          textField: {
                            fullWidth: true,
                            error: Boolean(touched.due_date && errors.due_date),
                            helperText: touched.due_date && errors.due_date,
                          },
                        }}
                      />
                    </LocalizationProvider>
                  </Stack>
                </Grid>

                <Grid item xs={12} sm={6} />

                <Grid item xs={12}>
                  <Divider sx={{ my: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Contacts
                    </Typography>
                  </Divider>
                </Grid>

                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <InputLabel required>Contacts</InputLabel>

                    <Autocomplete
                      multiple
                      id="contact_ids"
                      options={contactOptions}
                      loading={contactsLoading}
                      value={selectedContacts}
                      onChange={(event, newValue) => {
                        setFieldValue(
                          "contact_ids",
                          newValue.map((c) => c.id),
                        );
                      }}
                      onBlur={() => formik.setFieldTouched("contact_ids", true)}
                      getOptionLabel={(option) => option.label || ""}
                      isOptionEqualToValue={(option, value) =>
                        option.id === value.id
                      }
                      renderInput={(params) => (
                        <TextField
                          {...params}
                          placeholder={
                            contactOptions.length === 0
                              ? "No contacts yet"
                              : "Select contacts..."
                          }
                          error={Boolean(
                            touched.contact_ids &&
                            errors.contact_ids &&
                            !inlineContact,
                          )}
                          helperText={
                            touched.contact_ids &&
                            errors.contact_ids &&
                            !inlineContact
                              ? errors.contact_ids
                              : ""
                          }
                          InputProps={{
                            ...params.InputProps,
                            endAdornment: (
                              <>
                                {contactsLoading ? (
                                  <CircularProgress color="inherit" size={20} />
                                ) : null}
                                {params.InputProps.endAdornment}
                              </>
                            ),
                          }}
                        />
                      )}
                      renderOption={(props, option) => (
                        <li {...props} key={option.id}>
                          <Stack>
                            <Typography variant="body2">
                              {option.label}
                            </Typography>
                            {option.job_title && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {option.job_title}
                              </Typography>
                            )}
                          </Stack>
                        </li>
                      )}
                    />

                    {inlineContact && (
                      <Box
                        sx={{
                          p: 1.5,
                          bgcolor: "success.lighter",
                          borderRadius: 1,
                        }}
                      >
                        <Stack
                          direction="row"
                          justifyContent="space-between"
                          alignItems="center"
                        >
                          <Typography variant="body2" color="success.dark">
                            ✓ New contact: {inlineContact.first_name}{" "}
                            {inlineContact.last_name}
                          </Typography>
                          <Button
                            size="small"
                            color="error"
                            onClick={() => {
                              setInlineContact(null);
                              setFieldValue("has_inline_contact", false);
                            }}
                          >
                            Remove
                          </Button>
                        </Stack>
                      </Box>
                    )}

                    {!showInlineContact && !inlineContact && !isEditMode && (
                      <Button
                        size="small"
                        startIcon={<PlusOutlined />}
                        onClick={() => setShowInlineContact(true)}
                        sx={{ alignSelf: "flex-start" }}
                      >
                        Add new contact
                      </Button>
                    )}

                    {showInlineContact && (
                      <InlineContactForm
                        onSave={(contactData) => {
                          setInlineContact(contactData);
                          setShowInlineContact(false);
                          setFieldValue("has_inline_contact", true);
                          formik.setFieldError("contact_ids", undefined);
                          displaySuccessSnackbar(
                            `Contact "${contactData.first_name} ${contactData.last_name}" will be created with this activity`,
                          );
                        }}
                        onCancel={() => setShowInlineContact(false)}
                      />
                    )}
                  </Stack>
                </Grid>

                <Grid item xs={12}>
                  <Divider sx={{ my: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Activity Details (Optional)
                    </Typography>
                  </Divider>
                </Grid>

                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="call_to_action">
                      Call to Action
                    </InputLabel>
                    <TextField
                      id="call_to_action"
                      name="call_to_action"
                      fullWidth
                      placeholder="e.g., Ask about budget timeline"
                      value={values.call_to_action}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(
                        touched.call_to_action && errors.call_to_action,
                      )}
                      helperText={
                        touched.call_to_action && errors.call_to_action
                      }
                    />
                  </Stack>
                </Grid>

                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="description">Description</InputLabel>
                    <TextField
                      id="description"
                      name="description"
                      fullWidth
                      multiline
                      rows={3}
                      placeholder="Additional details about this activity..."
                      value={values.description}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(touched.description && errors.description)}
                      helperText={touched.description && errors.description}
                    />
                  </Stack>
                </Grid>

                <Grid item xs={12}>
                  <Divider sx={{ my: 1 }}>
                    <Typography variant="caption" color="text.secondary">
                      Decision Cycle Link (Optional)
                    </Typography>
                  </Divider>
                </Grid>

                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel>Decision Cycle</InputLabel>

                    {inlineCycle ? (
                      <Box
                        sx={{
                          p: 1.5,
                          bgcolor: "success.lighter",
                          borderRadius: 1,
                        }}
                      >
                        <Stack
                          direction="row"
                          justifyContent="space-between"
                          alignItems="center"
                        >
                          <Stack>
                            <Typography variant="body2" color="success.dark">
                              ✓ {inlineCycle.name}
                            </Typography>
                            <Typography variant="caption" color="success.main">
                              Starting at:{" "}
                              {PIPELINE_STEPS.find(
                                (s) => s.value === inlineStepStage,
                              )?.label || "Qualification"}
                            </Typography>
                          </Stack>
                          <Button
                            size="small"
                            color="error"
                            onClick={() => {
                              setInlineCycle(null);
                              setInlineStepStage("QUALIFICATION");
                            }}
                          >
                            Remove
                          </Button>
                        </Stack>
                      </Box>
                    ) : (
                      <Select
                        id="decision_cycle_id"
                        name="decision_cycle_id"
                        fullWidth
                        value={values.decision_cycle_id}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        displayEmpty
                        disabled={cyclesLoading}
                      >
                        <MenuItem value="">
                          <em>
                            {cycleOptions.length === 0
                              ? "No cycles yet"
                              : "None"}
                          </em>
                        </MenuItem>
                        {cycleOptions.map((cycle) => (
                          <MenuItem key={cycle.id} value={cycle.id}>
                            {cycle.name}
                            {!cycle.is_active && " (Inactive)"}
                          </MenuItem>
                        ))}
                      </Select>
                    )}

                    {!showInlineCycle && !inlineCycle && !isEditMode && (
                      <Button
                        size="small"
                        startIcon={<PlusOutlined />}
                        onClick={() => setShowInlineCycle(true)}
                        sx={{ alignSelf: "flex-start" }}
                      >
                        Create new cycle
                      </Button>
                    )}

                    {showInlineCycle && (
                      <Box sx={{ gridColumn: "span 2" }}>
                        <InlineCycleForm
                          onSave={(cycleData) => {
                            const { step_stage, ...cycleInfo } = cycleData;
                            setInlineCycle(cycleInfo);
                            setInlineStepStage(step_stage);
                            setShowInlineCycle(false);
                            setFieldValue("decision_cycle_id", "");
                            setFieldValue("decision_step_id", "");
                            displaySuccessSnackbar(
                              `Cycle "${cycleInfo.name}" will be created with this activity`,
                            );
                          }}
                          onCancel={() => setShowInlineCycle(false)}
                        />
                      </Box>
                    )}
                  </Stack>
                </Grid>

                {!inlineCycle && !showInlineCycle && (
                  <Grid item xs={12} sm={6}>
                    <Stack spacing={1}>
                      <InputLabel>
                        Decision Step {values.decision_cycle_id && "*"}
                      </InputLabel>
                      <Select
                        id="decision_step_id"
                        name="decision_step_id"
                        fullWidth
                        value={values.decision_step_id}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        displayEmpty
                        disabled={stepsLoading || !values.decision_cycle_id}
                        error={Boolean(
                          touched.decision_step_id && errors.decision_step_id,
                        )}
                      >
                        <MenuItem value="">
                          <em>
                            {!values.decision_cycle_id
                              ? "Select a cycle first"
                              : "Select a pipeline step"}
                          </em>
                        </MenuItem>
                        {stepOptions.map((step) => (
                          <MenuItem key={step.id} value={step.id}>
                            {step.name}
                          </MenuItem>
                        ))}
                      </Select>
                      {touched.decision_step_id && errors.decision_step_id && (
                        <FormHelperText error>
                          {errors.decision_step_id}
                        </FormHelperText>
                      )}
                    </Stack>
                  </Grid>
                )}
              </Grid>
            </Box>

            <Divider />

            <Box sx={{ p: 2.5 }}>
              <Stack direction="row" spacing={2} justifyContent="flex-end">
                <Button color="error" onClick={handleClose}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="contained"
                  disabled={submitting}
                  startIcon={
                    submitting ? (
                      <CircularProgress size={16} color="inherit" />
                    ) : null
                  }
                >
                  {submitting
                    ? isEditMode
                      ? "Updating..."
                      : "Creating..."
                    : isEditMode
                      ? "Update"
                      : "Create"}
                </Button>
              </Stack>
            </Box>
          </Box>
        </Box>
      </MainCard>
    </Modal>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  activity: PropTypes.object,
  accountId: PropTypes.string,
  decisionStepId: PropTypes.string,
  decisionCycleId: PropTypes.string,
  defaultActivityType: PropTypes.string,
  previousActivityId: PropTypes.string,
  sourceActivityId: PropTypes.string,
  nextStepSignal: PropTypes.shape({
    id: PropTypes.string,
    suggested_title: PropTypes.string,
    suggested_activity_type: PropTypes.string,
    suggested_due_date: PropTypes.string,
    suggested_contacts: PropTypes.arrayOf(
      PropTypes.shape({
        id: PropTypes.string,
        first_name: PropTypes.string,
        last_name: PropTypes.string,
      }),
    ),
    source_quote: PropTypes.string,
  }),
  onSuccess: PropTypes.func,
};
