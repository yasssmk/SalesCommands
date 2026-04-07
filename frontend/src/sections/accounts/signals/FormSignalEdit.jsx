// frontend/src/sections/accounts/signals/FormSignalEdit.jsx
/**
 * FormSignalEdit — modal form for editing an existing signal (PATCH).
 *
 * Allowed fields (matches BaseSignalUpdateSerializer):
 *   value, signal_category, source_department, source_contact, source_quote.
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
import Alert from "@mui/material/Alert";
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
import Typography from "@mui/material/Typography";

// project imports
import { updateSignal } from "api/accounts/signals";
import {
  useGetContacts,
  useGetContactChoices,
} from "api/businessData/contacts";
import { handleFormikError } from "utils/formErrorHandler";

// ==============================|| HELPERS ||============================== //

function displayValue(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  try {
    const str = JSON.stringify(value, null, 0);
    return str.length > 300 ? `${str.slice(0, 300)}…` : str;
  } catch {
    return String(value);
  }
}

function buildInitialValues(signal) {
  if (!signal) {
    return {
      value: "",
      signal_category: "",
      source_contact: "",
      source_department: "",
      source_quote: "",
    };
  }
  return {
    value: displayValue(signal.value),
    signal_category: signal.signal_category ?? "",
    source_contact: signal.source_contact?.id ?? "",
    source_department: signal.source_department?.id ?? "",
    source_quote: signal.source_quote ?? "",
  };
}

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  value: Yup.string().trim().required("Value is required"),
  signal_category: Yup.string().nullable(),
  source_contact: Yup.string().nullable(),
  source_department: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| FORM SIGNAL EDIT ||============================== //

export default function FormSignalEdit({
  open,
  onClose,
  onSuccess,
  signal,
  signalType,
  choices,
  choicesLoading,
}) {
  // ==============================|| DATA ||============================== //

  const accountId = useMemo(() => {
    if (!signal?.account) return null;
    if (typeof signal.account === "string") return signal.account;
    return signal.account?.id ?? null;
  }, [signal]);

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

  const hasOriginalValue =
    signal?.original_value !== null && signal?.original_value !== undefined;

  // ==============================|| FORMIK ||============================== //

  const formik = useFormik({
    initialValues: buildInitialValues(signal),
    validationSchema,
    enableReinitialize: true,

    onSubmit: async (values, { setSubmitting }) => {
      if (!signal || !signalType) return;

      const initial = buildInitialValues(signal);
      const patch = {};

      if (values.value.trim() !== initial.value.trim())
        patch.value = values.value.trim();
      if (values.signal_category !== initial.signal_category)
        patch.signal_category = values.signal_category || null;
      if (values.source_contact !== initial.source_contact)
        patch.source_contact = values.source_contact || null;
      if (values.source_department !== initial.source_department)
        patch.source_department = values.source_department || null;
      if (values.source_quote.trim() !== initial.source_quote.trim())
        patch.source_quote = values.source_quote.trim() || null;

      if (Object.keys(patch).length === 0) {
        setSubmitting(false);
        onClose();
        return;
      }

      const result = await updateSignal(signalType, signal.id, patch);

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
    if (open && signal) {
      formik.resetForm({ values: buildInitialValues(signal) });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, signal?.id]);

  // ==============================|| RENDER ||============================== //

  return (
    <Dialog
      open={open}
      onClose={formik.isSubmitting ? undefined : onClose}
      maxWidth="sm"
      fullWidth
      aria-labelledby="signal-edit-dialog-title"
    >
      <DialogTitle id="signal-edit-dialog-title">
        <Stack spacing={0.25}>
          <Typography variant="h5">Edit Signal</Typography>
          {signal && (
            <Typography variant="caption" color="text.secondary">
              {signal.field_name_display || signal.field_name}
              {signal.tech_name ? ` · ${signal.tech_name}` : ""}
            </Typography>
          )}
        </Stack>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2.5 }}>
        <Stack spacing={2.5}>
          {/* ---- Original value (LLM_MODIFIED) ---- */}
          {hasOriginalValue && (
            <Alert severity="info" variant="outlined">
              <Typography
                variant="caption"
                display="block"
                fontWeight={600}
                gutterBottom
              >
                Original value (before LLM modification)
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {displayValue(signal.original_value)}
              </Typography>
            </Alert>
          )}

          {/* ---- Value ---- */}
          <TextField
            fullWidth
            size="small"
            id="value"
            name="value"
            label="Value *"
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
            <InputLabel id="edit-signal-category-label">Category</InputLabel>
            <Select
              labelId="edit-signal-category-label"
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
            <InputLabel id="edit-source-contact-label">
              {contactsLoading ? "Loading contacts…" : "Source contact"}
            </InputLabel>
            <Select
              labelId="edit-source-contact-label"
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
            <InputLabel id="edit-source-department-label">
              Source department
            </InputLabel>
            <Select
              labelId="edit-source-department-label"
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

          {/* ---- Read-only hint ---- */}
          {signal && (
            <Box
              sx={{ bgcolor: "action.hover", borderRadius: 1, px: 1.5, py: 1 }}
            >
              <Typography variant="caption" color="text.disabled">
                Editing is tracked — changing the value will snapshot the
                current value as <em>original_value</em> on the backend. To
                replace this signal entirely, use <strong>Supersede</strong>{" "}
                instead.
              </Typography>
            </Box>
          )}
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
          {formik.isSubmitting ? "Saving…" : "Save Changes"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ==============================|| PROP TYPES ||============================== //

FormSignalEdit.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
  signal: PropTypes.shape({
    id: PropTypes.string.isRequired,
    field_name: PropTypes.string,
    field_name_display: PropTypes.string,
    tech_name: PropTypes.string,
    value: PropTypes.any,
    original_value: PropTypes.any,
    signal_category: PropTypes.string,
    source_quote: PropTypes.string,
    source_contact: PropTypes.shape({ id: PropTypes.string }),
    source_department: PropTypes.shape({ id: PropTypes.string }),
    account: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
  }),
  signalType: PropTypes.oneOf(["qualification", "tech-stack"]),
  choices: PropTypes.shape({
    signal_category: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
  }),
  choicesLoading: PropTypes.bool,
};
