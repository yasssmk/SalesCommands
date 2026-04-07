// frontend/src/sections/accounts/signals/FormSignalAdd.jsx
/**
 * FormSignalAdd — modal form for manual signal creation.
 *
 * Dual mode:
 *   CREATE    — supersedeTarget is null.
 *   SUPERSEDE — supersedeTarget = { signal, signalType }.
 *
 * Error handling: handleFormikError() from utils/formErrorHandler.
 * Field errors:   native Formik pattern (touched + errors).
 */

"use client";

import PropTypes from "prop-types";
import { useMemo, useEffect } from "react";
import { useFormik } from "formik";
import * as Yup from "yup";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

// project imports
import { createSignal, supersedeSignal } from "api/accounts/signals";
import {
  useGetContacts,
  useGetContactChoices,
} from "api/businessData/contacts";
import { handleFormikError } from "utils/formErrorHandler";

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  signal_type: Yup.string()
    .oneOf(["qualification", "tech-stack"])
    .required("Signal type is required"),
  field_name: Yup.string().required("Field name is required"),
  value: Yup.string().trim().required("Value is required"),
  tech_name: Yup.string().nullable(),
  signal_category: Yup.string().nullable(),
  source_contact: Yup.string().nullable(),
  source_department: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
  confidence: Yup.number().nullable().min(0, "Minimum 0").max(1, "Maximum 1"),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues(supersedeTarget, defaultContactId) {
  return {
    signal_type: supersedeTarget?.signalType ?? "qualification",
    field_name: supersedeTarget?.signal?.field_name ?? "",
    value: "",
    tech_name: "",
    signal_category: "",
    source_contact: defaultContactId ?? "",
    source_department: "",
    source_quote: "",
    confidence: "",
  };
}

// ==============================|| FORM SIGNAL ADD ||============================== //

export default function FormSignalAdd({
  open,
  onClose,
  onSuccess,
  accountId,
  choices,
  choicesLoading,
  supersedeTarget,
  extraPayload,
  defaultContactId,
}) {
  const isSupersede = Boolean(supersedeTarget);
  const title = isSupersede ? "Supersede Signal" : "Add Signal";

  // ==============================|| DATA ||============================== //

  const { contacts, contactsLoading } = useGetContacts(
    open && accountId
      ? { pageSize: 100, filters: { account: accountId } }
      : null,
  );

  const { standardDepartments } = useGetContactChoices();

  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: d.value ?? d.id,
        label: d.label ?? d.name,
      })),
    [standardDepartments],
  );

  // ==============================|| FORMIK ||============================== //

  const formik = useFormik({
    initialValues: buildInitialValues(supersedeTarget, defaultContactId),
    validationSchema,
    enableReinitialize: true,

    onSubmit: async (values, { setSubmitting }) => {
      const payload = {
        account: accountId,
        field_name: values.field_name,
        value: values.value.trim(),
        source: "MANUAL",
        ...(extraPayload ?? {}),
      };

      if (values.signal_type === "tech-stack" && values.tech_name) {
        payload.tech_name = values.tech_name.trim();
      }
      if (values.signal_category)
        payload.signal_category = values.signal_category;
      if (values.source_contact) payload.source_contact = values.source_contact;
      if (values.source_department)
        payload.source_department = values.source_department;
      if (values.source_quote)
        payload.source_quote = values.source_quote.trim();
      if (values.confidence !== "")
        payload.confidence = Number(values.confidence);

      const result = isSupersede
        ? await supersedeSignal(
            supersedeTarget.signalType,
            supersedeTarget.signal.id,
            payload,
          )
        : await createSignal(values.signal_type, payload);

      setSubmitting(false);

      if (result.success) {
        onSuccess();
      } else {
        handleFormikError(result, formik);
      }
    },
  });

  // ==============================|| RESET ON OPEN ||============================== //

  useEffect(() => {
    if (open) {
      formik.resetForm({
        values: buildInitialValues(supersedeTarget, defaultContactId),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, supersedeTarget]);

  // ==============================|| FIELD NAME OPTIONS ||============================== //

  const fieldNameOptions = useMemo(() => {
    if (!choices) return [];
    return formik.values.signal_type === "tech-stack"
      ? (choices.tech_stack_fields ?? [])
      : (choices.qualification_fields ?? []);
  }, [choices, formik.values.signal_type]);

  const handleSignalTypeChange = (_e, newValue) => {
    if (!newValue || isSupersede) return;
    formik.setFieldValue("signal_type", newValue);
    formik.setFieldValue("field_name", "");
    formik.setFieldValue("tech_name", "");
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Dialog
      open={open}
      onClose={formik.isSubmitting ? undefined : onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="signal-add-dialog-title"
    >
      <DialogTitle id="signal-add-dialog-title">
        <Stack spacing={0.25}>
          <Typography variant="h5">{title}</Typography>
          {isSupersede && (
            <Typography variant="caption" color="text.secondary">
              The existing signal will be marked as superseded. A new validated
              signal will be created in its place.
            </Typography>
          )}
        </Stack>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2.5 }}>
        <Stack spacing={2.5}>
          {/* ---- Signal type ---- */}
          <Box>
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
              gutterBottom
            >
              Signal type *
            </Typography>
            <ToggleButtonGroup
              value={formik.values.signal_type}
              exclusive
              onChange={handleSignalTypeChange}
              size="small"
              disabled={isSupersede}
              aria-label="Signal type"
            >
              <ToggleButton
                value="qualification"
                sx={{ textTransform: "none", px: 2 }}
              >
                Qualification
              </ToggleButton>
              <ToggleButton
                value="tech-stack"
                sx={{ textTransform: "none", px: 2 }}
              >
                Tech Stack
              </ToggleButton>
            </ToggleButtonGroup>
            {isSupersede && (
              <Typography
                variant="caption"
                color="text.disabled"
                sx={{ mt: 0.5, display: "block" }}
              >
                Locked — inherits type from the signal being superseded.
              </Typography>
            )}
          </Box>

          {/* ---- Field name ---- */}
          <FormControl
            fullWidth
            size="small"
            error={
              formik.touched.field_name && Boolean(formik.errors.field_name)
            }
            disabled={isSupersede || choicesLoading}
          >
            <InputLabel id="field-name-label">Field name *</InputLabel>
            <Select
              labelId="field-name-label"
              id="field_name"
              name="field_name"
              value={formik.values.field_name}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Field name *"
            >
              {choicesLoading && (
                <MenuItem disabled value="">
                  Loading…
                </MenuItem>
              )}
              {!choicesLoading && fieldNameOptions.length === 0 && (
                <MenuItem disabled value="">
                  No options available
                </MenuItem>
              )}
              {fieldNameOptions.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
            {formik.touched.field_name && formik.errors.field_name && (
              <FormHelperText>{formik.errors.field_name}</FormHelperText>
            )}
            {isSupersede && (
              <FormHelperText>
                Locked — inherits field from the signal being superseded.
              </FormHelperText>
            )}
          </FormControl>

          {/* ---- Tech name (tech-stack only) ---- */}
          {formik.values.signal_type === "tech-stack" && (
            <TextField
              fullWidth
              size="small"
              id="tech_name"
              name="tech_name"
              label="Tool name"
              placeholder="e.g. Salesforce, HubSpot…"
              value={formik.values.tech_name}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={
                formik.touched.tech_name && Boolean(formik.errors.tech_name)
              }
              helperText={
                (formik.touched.tech_name && formik.errors.tech_name) ||
                "Name of the tool as mentioned in the conversation"
              }
            />
          )}

          {/* ---- Value ---- */}
          <TextField
            fullWidth
            size="small"
            id="value"
            name="value"
            label="Value *"
            placeholder="Describe the signal…"
            multiline
            minRows={3}
            value={formik.values.value}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.value && Boolean(formik.errors.value)}
            helperText={formik.touched.value && formik.errors.value}
          />

          {/* ---- Signal category ---- */}
          <FormControl
            fullWidth
            size="small"
            error={
              formik.touched.signal_category &&
              Boolean(formik.errors.signal_category)
            }
            disabled={choicesLoading}
          >
            <InputLabel id="signal-category-label">Category</InputLabel>
            <Select
              labelId="signal-category-label"
              id="signal_category"
              name="signal_category"
              value={formik.values.signal_category}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Category"
            >
              <MenuItem value="">None</MenuItem>
              {(choices?.signal_category ?? []).map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
            {formik.touched.signal_category &&
              formik.errors.signal_category && (
                <FormHelperText>{formik.errors.signal_category}</FormHelperText>
              )}
          </FormControl>

          {/* ---- Source contact ---- */}
          <FormControl
            fullWidth
            size="small"
            error={
              formik.touched.source_contact &&
              Boolean(formik.errors.source_contact)
            }
            disabled={contactsLoading}
          >
            <InputLabel id="source-contact-label">
              {contactsLoading ? "Loading contacts…" : "Source contact"}
            </InputLabel>
            <Select
              labelId="source-contact-label"
              id="source_contact"
              name="source_contact"
              value={formik.values.source_contact}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label={contactsLoading ? "Loading contacts…" : "Source contact"}
            >
              <MenuItem value="">None</MenuItem>
              {contacts.map((c) => (
                <MenuItem key={c.id} value={c.id}>
                  {`${c.first_name ?? ""} ${c.last_name ?? ""}`.trim() ||
                    c.email ||
                    c.id}
                  {c.job_title && (
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      sx={{ ml: 1 }}
                    >
                      · {c.job_title}
                    </Typography>
                  )}
                </MenuItem>
              ))}
            </Select>
            {formik.touched.source_contact && formik.errors.source_contact && (
              <FormHelperText>{formik.errors.source_contact}</FormHelperText>
            )}
          </FormControl>

          {/* ---- Source department ---- */}
          <FormControl
            fullWidth
            size="small"
            error={
              formik.touched.source_department &&
              Boolean(formik.errors.source_department)
            }
          >
            <InputLabel id="source-department-label">
              Source department
            </InputLabel>
            <Select
              labelId="source-department-label"
              id="source_department"
              name="source_department"
              value={formik.values.source_department}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Source department"
            >
              <MenuItem value="">None</MenuItem>
              {departmentOptions.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
            {formik.touched.source_department &&
              formik.errors.source_department && (
                <FormHelperText>
                  {formik.errors.source_department}
                </FormHelperText>
              )}
          </FormControl>

          {/* ---- Source quote ---- */}
          <TextField
            fullWidth
            size="small"
            id="source_quote"
            name="source_quote"
            label="Source quote"
            placeholder="Exact words from the transcript…"
            multiline
            minRows={2}
            value={formik.values.source_quote}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={
              formik.touched.source_quote && Boolean(formik.errors.source_quote)
            }
            helperText={
              formik.touched.source_quote && formik.errors.source_quote
            }
          />

          {/* ---- Confidence ---- */}
          <TextField
            fullWidth
            size="small"
            id="confidence"
            name="confidence"
            label="Confidence (0 – 1)"
            type="number"
            inputProps={{ min: 0, max: 1, step: 0.05 }}
            value={formik.values.confidence}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={
              formik.touched.confidence && Boolean(formik.errors.confidence)
            }
            helperText={
              (formik.touched.confidence && formik.errors.confidence) ||
              "Optional — how confident you are in this signal (0 = low, 1 = certain)"
            }
          />
        </Stack>
      </DialogContent>

      <Divider />

      <DialogActions sx={{ px: 3, py: 2 }}>
        <Button
          onClick={onClose}
          disabled={formik.isSubmitting}
          color="inherit"
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={formik.handleSubmit}
          disabled={formik.isSubmitting || !formik.isValid}
          startIcon={
            formik.isSubmitting ? (
              <CircularProgress size={14} color="inherit" />
            ) : null
          }
        >
          {formik.isSubmitting
            ? "Saving…"
            : isSupersede
              ? "Supersede"
              : "Add Signal"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ==============================|| PROP TYPES ||============================== //

FormSignalAdd.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
  accountId: PropTypes.string.isRequired,
  choices: PropTypes.shape({
    signal_category: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    qualification_fields: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    tech_stack_fields: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
  }),
  choicesLoading: PropTypes.bool,
  supersedeTarget: PropTypes.shape({
    signal: PropTypes.object.isRequired,
    signalType: PropTypes.oneOf(["qualification", "tech-stack"]).isRequired,
  }),
  extraPayload: PropTypes.object,
  defaultContactId: PropTypes.string,
};
