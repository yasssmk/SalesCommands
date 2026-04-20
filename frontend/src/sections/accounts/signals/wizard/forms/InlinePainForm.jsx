// frontend/src/sections/accounts/signals/wizard/forms/InlinePainForm.jsx
/**
 * InlinePainForm — inline form for staging a single PainSignal inside the wizard.
 *
 * This form does NOT call createSignal directly.
 * It calls onAdd(payload) with a ready-to-dispatch payload object.
 * The wizard container (WizardSignalAdd) injects account + extraPayload
 * at dispatch time.
 *
 * Required fields: summary, category, pain_level, source_contact.
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
  category: Yup.string().required("Category is required"),
  pain_level: Yup.string().required("Pain level is required"),
  source_contact: Yup.object()
    .nullable()
    .required("Source contact is required"),
  business_cost: Yup.string().nullable(),
  impact_summary: Yup.string().nullable(),
  impacted_department: Yup.string().nullable(),
  notes: Yup.string().nullable(),
  source_department: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
  signal_category: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues(defaultContact) {
  return {
    summary: "",
    category: "",
    pain_level: "",
    source_contact: defaultContact ?? null,
    business_cost: "",
    impact_summary: "",
    impacted_department: "",
    notes: "",
    source_department: "",
    source_quote: "",
    signal_category: "",
  };
}

// ==============================|| INLINE PAIN FORM ||============================== //

/**
 * InlinePainForm
 *
 * @param {Object}   choices         - Choices from useGetSignalChoices()
 * @param {boolean}  choicesLoading  - True while choices are loading
 * @param {string}   accountId       - Account UUID — scopes contact search
 * @param {Object}   defaultContact  - Full contact object to pre-fill source_contact
 * @param {Function} onAdd           - (payload: Object) => void
 * @param {Function} onCancel        - () => void
 */
export default function InlinePainForm({
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
        category: values.category,
        pain_level: values.pain_level,
        // Keep full contact object — UUID is extracted at dispatch time
        // (wizard dispatch or SignalEditDialog PATCH)
        source_contact: values.source_contact,
      };

      if (values.business_cost)
        payload.business_cost = values.business_cost.trim();
      if (values.impact_summary)
        payload.impact_summary = values.impact_summary.trim();
      if (values.impacted_department)
        payload.impacted_department = values.impacted_department;
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
        borderColor: "error.light",
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
            New Pain Signal
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
          id="pain-summary"
          name="summary"
          label="Summary *"
          placeholder="Describe the pain point observed…"
          multiline
          minRows={2}
          value={formik.values.summary}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.summary && Boolean(formik.errors.summary)}
          helperText={formik.touched.summary && formik.errors.summary}
        />

        {/* ---- Category + Pain Level (required) ---- */}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <FormControl
            fullWidth
            size="small"
            error={formik.touched.category && Boolean(formik.errors.category)}
            disabled={choicesLoading}
          >
            <InputLabel id="pain-category-label">Category *</InputLabel>
            <Select
              labelId="pain-category-label"
              id="pain-category"
              name="category"
              value={formik.values.category}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Category *"
            >
              {(choices?.pain_categories ?? []).map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
            {formik.touched.category && formik.errors.category && (
              <FormHelperText>{formik.errors.category}</FormHelperText>
            )}
          </FormControl>

          <FormControl
            fullWidth
            size="small"
            error={
              formik.touched.pain_level && Boolean(formik.errors.pain_level)
            }
            disabled={choicesLoading}
          >
            <InputLabel id="pain-level-label">Pain Level *</InputLabel>
            <Select
              labelId="pain-level-label"
              id="pain-level"
              name="pain_level"
              value={formik.values.pain_level}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Pain Level *"
            >
              {(choices?.pain_levels ?? []).map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
            {formik.touched.pain_level && formik.errors.pain_level && (
              <FormHelperText>{formik.errors.pain_level}</FormHelperText>
            )}
          </FormControl>
        </Stack>

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

        {/* ---- Business Cost (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="pain-business-cost"
          name="business_cost"
          label="Business Cost"
          placeholder="e.g. 2h/day, $10k/year…"
          value={formik.values.business_cost}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={
            formik.touched.business_cost && Boolean(formik.errors.business_cost)
          }
          helperText={
            formik.touched.business_cost && formik.errors.business_cost
          }
        />

        {/* ---- Impact Summary (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="pain-impact-summary"
          name="impact_summary"
          label="Impact Summary"
          placeholder="Broader impact on the business…"
          multiline
          minRows={2}
          value={formik.values.impact_summary}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={
            formik.touched.impact_summary &&
            Boolean(formik.errors.impact_summary)
          }
          helperText={
            formik.touched.impact_summary && formik.errors.impact_summary
          }
        />

        {/* ---- Impacted Department + Source Department (optional) ---- */}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <FormControl fullWidth size="small">
            <InputLabel id="pain-impacted-dept-label">
              Impacted Department
            </InputLabel>
            <Select
              labelId="pain-impacted-dept-label"
              id="pain-impacted-department"
              name="impacted_department"
              value={formik.values.impacted_department}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Impacted Department"
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

          <FormControl fullWidth size="small">
            <InputLabel id="pain-source-dept-label">
              Source Department
            </InputLabel>
            <Select
              labelId="pain-source-dept-label"
              id="pain-source-department"
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
        </Stack>

        {/* ---- Notes (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="pain-notes"
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
          id="pain-source-quote"
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
          <InputLabel id="pain-signal-category-label">
            Signal Category
          </InputLabel>
          <Select
            labelId="pain-signal-category-label"
            id="pain-signal-category"
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
            {submitLabel ?? "Add Pain"}
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

InlinePainForm.propTypes = {
  choices: PropTypes.shape({
    pain_categories: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    pain_levels: PropTypes.arrayOf(
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
