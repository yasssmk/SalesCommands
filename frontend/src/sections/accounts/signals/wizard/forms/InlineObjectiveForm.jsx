// frontend/src/sections/accounts/signals/wizard/forms/InlineObjectiveForm.jsx
/**
 * InlineObjectiveForm — inline form for staging a single ObjectiveSignal inside the wizard.
 *
 * This form does NOT call createSignal directly.
 * It calls onAdd(payload) with a ready-to-dispatch payload object.
 * The wizard container (WizardSignalAdd) injects account + extraPayload
 * at dispatch time.
 *
 * Required fields: summary, goal_level, source_contact.
 *
 * Contact fields use AsyncContactSelect scoped to the account via
 * filters={{ account_id: accountId }}. Formik stores the full contact
 * object; .id is extracted when building the payload.
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
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";
import { useGetContactChoices } from "api/businessData/contacts";

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  goal_level: Yup.string().required("Goal level is required"),
  source_contact: Yup.object()
    .nullable()
    .required("Source contact is required"),
  success_criteria: Yup.string().nullable(),
  measurement_method: Yup.string().nullable(),
  target_contact: Yup.object().nullable(),
  target_department: Yup.string().nullable(),
  notes: Yup.string().nullable(),
  source_department: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
  signal_category: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues(defaultContact) {
  return {
    summary: "",
    goal_level: "",
    source_contact: defaultContact ?? null,
    success_criteria: "",
    measurement_method: "",
    target_contact: null,
    target_department: "",
    notes: "",
    source_department: "",
    source_quote: "",
    signal_category: "",
  };
}

// ==============================|| INLINE OBJECTIVE FORM ||============================== //

/**
 * InlineObjectiveForm
 *
 * @param {Object}   choices         - Choices from useGetSignalChoices()
 * @param {boolean}  choicesLoading  - True while choices are loading
 * @param {string}   accountId       - Account UUID — scopes contact search
 * @param {Object}   defaultContact  - Full contact object to pre-fill source_contact
 * @param {Function} onAdd           - (payload: Object) => void
 * @param {Function} onCancel        - () => void
 */
export default function InlineObjectiveForm({
  choices,
  choicesLoading,
  accountId,
  defaultContact,
  onAdd,
  onCancel,
  initialValues: initialValuesProp,
  submitLabel,
}) {
  // ==============================|| DATA ||============================== //

  const { standardDepartments } = useGetContactChoices();

  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: d.value ?? d.id,
        label: d.label ?? d.name,
      })),
    [standardDepartments],
  );

  /** Contact search scoped to this account only */
  const contactFilters = useMemo(
    () => ({ account_id: accountId }),
    [accountId],
  );

  // ==============================|| FORMIK ||============================== //

  const formik = useFormik({
    initialValues: initialValuesProp ?? buildInitialValues(defaultContact),
    validationSchema,
    enableReinitialize: true,
    onSubmit: (values, { resetForm }) => {
      const payload = {
        summary: values.summary.trim(),
        goal_level: values.goal_level,
        // Keep full contact object — UUID is extracted at dispatch time
        // (wizard dispatch or SignalEditDialog PATCH)
        source_contact: values.source_contact,
      };

      if (values.target_contact) payload.target_contact = values.target_contact;
      if (values.success_criteria)
        payload.success_criteria = values.success_criteria.trim();
      if (values.measurement_method)
        payload.measurement_method = values.measurement_method.trim();
      if (values.target_department)
        payload.target_department = values.target_department;
      if (values.notes) payload.notes = values.notes.trim();
      if (values.source_department)
        payload.source_department = values.source_department;
      if (values.source_quote)
        payload.source_quote = values.source_quote.trim();
      if (values.signal_category)
        payload.signal_category = values.signal_category;

      onAdd(payload);
      resetForm({ values: buildInitialValues(defaultContact) });
    },
  });

  // ==============================|| SYNC defaultContact ||============================== //

  useEffect(() => {
    // Only sync defaultContact when not in edit mode (initialValuesProp absent)
    if (!initialValuesProp) {
      formik.setFieldValue("source_contact", defaultContact ?? null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultContact, initialValuesProp]);

  // ==============================|| RENDER ||============================== //

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: "info.light",
        borderRadius: 1.5,
        p: 2,
        bgcolor: "background.paper",
      }}
    >
      <Stack spacing={2}>
        {/* ---- Header ---- */}
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          <Typography variant="subtitle2" fontWeight={600}>
            New Objective Signal
          </Typography>
          <Button
            size="small"
            color="inherit"
            onClick={onCancel}
            startIcon={<CloseOutlined style={{ fontSize: 12 }} />}
            sx={{ minWidth: 0, px: 1 }}
          >
            Cancel
          </Button>
        </Stack>

        <Divider />

        {/* ---- Summary (required) ---- */}
        <TextField
          fullWidth
          size="small"
          id="objective-summary"
          name="summary"
          label="Summary *"
          placeholder="Describe the objective observed…"
          multiline
          minRows={2}
          value={formik.values.summary}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.summary && Boolean(formik.errors.summary)}
          helperText={formik.touched.summary && formik.errors.summary}
        />

        {/* ---- Goal Level (required) ---- */}
        <FormControl
          fullWidth
          size="small"
          error={formik.touched.goal_level && Boolean(formik.errors.goal_level)}
          disabled={choicesLoading}
        >
          <InputLabel id="objective-goal-level-label">Goal Level *</InputLabel>
          <Select
            labelId="objective-goal-level-label"
            id="objective-goal-level"
            name="goal_level"
            value={formik.values.goal_level}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            label="Goal Level *"
          >
            {(choices?.goal_levels ?? []).map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
          {formik.touched.goal_level && formik.errors.goal_level && (
            <FormHelperText>{formik.errors.goal_level}</FormHelperText>
          )}
        </FormControl>

        {/* ---- Source Contact (required) ---- */}
        <AsyncContactSelect
          label="Source Contact *"
          value={formik.values.source_contact}
          onChange={(_e, contact) =>
            formik.setFieldValue("source_contact", contact)
          }
          onBlur={() => formik.setFieldTouched("source_contact", true)}
          filters={contactFilters}
          disabled={!accountId}
          error={
            formik.touched.source_contact &&
            Boolean(formik.errors.source_contact)
          }
          helperText={
            formik.touched.source_contact && formik.errors.source_contact
          }
        />

        {/* ---- Success Criteria (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="objective-success-criteria"
          name="success_criteria"
          label="Success Criteria"
          placeholder="How will success be measured?…"
          multiline
          minRows={2}
          value={formik.values.success_criteria}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={
            formik.touched.success_criteria &&
            Boolean(formik.errors.success_criteria)
          }
          helperText={
            formik.touched.success_criteria && formik.errors.success_criteria
          }
        />

        {/* ---- Measurement Method (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="objective-measurement-method"
          name="measurement_method"
          label="Measurement Method"
          placeholder="KPI, metric, tool used to track…"
          value={formik.values.measurement_method}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={
            formik.touched.measurement_method &&
            Boolean(formik.errors.measurement_method)
          }
          helperText={
            formik.touched.measurement_method &&
            formik.errors.measurement_method
          }
        />

        {/* ---- Target Contact + Target Department (optional) ---- */}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <AsyncContactSelect
            label="Target Contact"
            value={formik.values.target_contact}
            onChange={(_e, contact) =>
              formik.setFieldValue("target_contact", contact)
            }
            onBlur={() => formik.setFieldTouched("target_contact", true)}
            filters={contactFilters}
            disabled={!accountId}
            error={
              formik.touched.target_contact &&
              Boolean(formik.errors.target_contact)
            }
            helperText={
              formik.touched.target_contact && formik.errors.target_contact
            }
          />

          <FormControl fullWidth size="small">
            <InputLabel id="objective-target-dept-label">
              Target Department
            </InputLabel>
            <Select
              labelId="objective-target-dept-label"
              id="objective-target-department"
              name="target_department"
              value={formik.values.target_department}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Target Department"
            >
              <MenuItem value="">
                <em>None</em>
              </MenuItem>
              {departmentOptions.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>

        {/* ---- Source Department (optional) ---- */}
        <FormControl fullWidth size="small">
          <InputLabel id="objective-source-dept-label">
            Source Department
          </InputLabel>
          <Select
            labelId="objective-source-dept-label"
            id="objective-source-department"
            name="source_department"
            value={formik.values.source_department}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            label="Source Department"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {departmentOptions.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* ---- Notes (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="objective-notes"
          name="notes"
          label="Notes"
          placeholder="Additional context…"
          multiline
          minRows={2}
          value={formik.values.notes}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.notes && Boolean(formik.errors.notes)}
          helperText={formik.touched.notes && formik.errors.notes}
        />

        {/* ---- Source Quote (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="objective-source-quote"
          name="source_quote"
          label="Source Quote"
          placeholder="Exact words from the conversation…"
          multiline
          minRows={2}
          value={formik.values.source_quote}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={
            formik.touched.source_quote && Boolean(formik.errors.source_quote)
          }
          helperText={formik.touched.source_quote && formik.errors.source_quote}
        />

        {/* ---- Signal Category (optional) ---- */}
        <FormControl fullWidth size="small" disabled={choicesLoading}>
          <InputLabel id="objective-signal-category-label">
            Signal Category
          </InputLabel>
          <Select
            labelId="objective-signal-category-label"
            id="objective-signal-category"
            name="signal_category"
            value={formik.values.signal_category}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            label="Signal Category"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {(choices?.signal_category ?? []).map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* ---- Actions ---- */}
        <Divider />

        <Stack direction="row" spacing={1.5} justifyContent="flex-end">
          <Button
            size="small"
            color="inherit"
            onClick={onCancel}
            disabled={formik.isSubmitting}
          >
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            onClick={formik.handleSubmit}
            disabled={formik.isSubmitting || !formik.isValid || !formik.dirty}
            startIcon={
              formik.isSubmitting ? (
                <CircularProgress size={12} color="inherit" />
              ) : (
                <PlusOutlined style={{ fontSize: 12 }} />
              )
            }
          >
            {submitLabel ?? "Add Objective"}
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

InlineObjectiveForm.propTypes = {
  choices: PropTypes.shape({
    goal_levels: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    signal_category: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
  }),
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
  defaultContact: PropTypes.object,
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  /** Pre-filled values for edit mode — triggers enableReinitialize */
  initialValues: PropTypes.object,
  /** Override submit button label (default: "Add X") */
  submitLabel: PropTypes.string,
};
