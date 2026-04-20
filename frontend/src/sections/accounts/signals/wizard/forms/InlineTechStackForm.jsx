// frontend/src/sections/accounts/signals/wizard/forms/InlineTechStackForm.jsx
/**
 * InlineTechStackForm — inline form for staging a single TechStackSignal inside the wizard.
 *
 * This form does NOT call createSignal directly.
 * It calls onAdd(payload) with a ready-to-dispatch payload object.
 * The wizard container (WizardSignalAdd) injects account + extraPayload
 * at dispatch time.
 *
 * Required fields: source_contact only.
 * All other fields are optional — a tech stack signal can be minimal.
 *
 * Contact field uses AsyncContactSelect scoped to the account via
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
  source_contact: Yup.object()
    .nullable()
    .required("Source contact is required"),
  tech_name: Yup.string().nullable(),
  category: Yup.string().nullable(),
  usage: Yup.string().nullable(),
  satisfaction: Yup.string().nullable(),
  limitations: Yup.string().nullable(),
  workarounds: Yup.string().nullable(),
  integrations: Yup.string().nullable(),
  renewal_date: Yup.string().nullable(),
  source_department: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
  signal_category: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues(defaultContact) {
  return {
    source_contact: defaultContact ?? null,
    tech_name: "",
    category: "",
    usage: "",
    satisfaction: "",
    limitations: "",
    workarounds: "",
    integrations: "",
    renewal_date: "",
    source_department: "",
    source_quote: "",
    signal_category: "",
  };
}

// ==============================|| INLINE TECH STACK FORM ||============================== //

/**
 * InlineTechStackForm
 *
 * @param {Object}   choices         - Choices from useGetSignalChoices()
 * @param {boolean}  choicesLoading  - True while choices are loading
 * @param {string}   accountId       - Account UUID — scopes contact search
 * @param {Object}   defaultContact  - Full contact object to pre-fill source_contact
 * @param {Function} onAdd           - (payload: Object) => void
 * @param {Function} onCancel        - () => void
 */
export default function InlineTechStackForm({
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
        // Keep full contact object — UUID is extracted at dispatch time
        // (wizard dispatch or SignalEditDialog PATCH)
        source_contact: values.source_contact,
      };

      if (values.tech_name) payload.tech_name = values.tech_name.trim();
      if (values.category) payload.category = values.category;
      if (values.usage) payload.usage = values.usage.trim();
      if (values.satisfaction) payload.satisfaction = values.satisfaction;
      if (values.limitations) payload.limitations = values.limitations.trim();
      if (values.workarounds) payload.workarounds = values.workarounds.trim();
      if (values.integrations)
        payload.integrations = values.integrations.trim();
      if (values.renewal_date) payload.renewal_date = values.renewal_date;
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
        borderColor: "primary.light",
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
            New Tech Stack Signal
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

        {/* ---- Tech Name + Category (optional) ---- */}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <TextField
            fullWidth
            size="small"
            id="tech-name"
            name="tech_name"
            label="Tool Name"
            placeholder="e.g. Salesforce, HubSpot, Notion…"
            value={formik.values.tech_name}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.tech_name && Boolean(formik.errors.tech_name)}
            helperText={
              (formik.touched.tech_name && formik.errors.tech_name) ||
              "Name of the tool as mentioned"
            }
          />

          <FormControl fullWidth size="small" disabled={choicesLoading}>
            <InputLabel id="tech-category-label">Category</InputLabel>
            <Select
              labelId="tech-category-label"
              id="tech-category"
              name="category"
              value={formik.values.category}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Category"
            >
              <MenuItem value="">
                <em>None</em>
              </MenuItem>
              {(choices?.tech_categories ?? []).map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Stack>

        {/* ---- Satisfaction (optional) ---- */}
        <FormControl fullWidth size="small" disabled={choicesLoading}>
          <InputLabel id="tech-satisfaction-label">Satisfaction</InputLabel>
          <Select
            labelId="tech-satisfaction-label"
            id="tech-satisfaction"
            name="satisfaction"
            value={formik.values.satisfaction}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            label="Satisfaction"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {(choices?.satisfaction ?? []).map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {/* ---- Usage (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="tech-usage"
          name="usage"
          label="Usage"
          placeholder="How do they use it?…"
          multiline
          minRows={2}
          value={formik.values.usage}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.usage && Boolean(formik.errors.usage)}
          helperText={formik.touched.usage && formik.errors.usage}
        />

        {/* ---- Limitations + Workarounds (optional) ---- */}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <TextField
            fullWidth
            size="small"
            id="tech-limitations"
            name="limitations"
            label="Limitations"
            placeholder="What doesn't work well?…"
            multiline
            minRows={2}
            value={formik.values.limitations}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={
              formik.touched.limitations && Boolean(formik.errors.limitations)
            }
            helperText={formik.touched.limitations && formik.errors.limitations}
          />

          <TextField
            fullWidth
            size="small"
            id="tech-workarounds"
            name="workarounds"
            label="Workarounds"
            placeholder="How do they compensate?…"
            multiline
            minRows={2}
            value={formik.values.workarounds}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={
              formik.touched.workarounds && Boolean(formik.errors.workarounds)
            }
            helperText={formik.touched.workarounds && formik.errors.workarounds}
          />
        </Stack>

        {/* ---- Integrations (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="tech-integrations"
          name="integrations"
          label="Integrations"
          placeholder="Connected tools or APIs…"
          value={formik.values.integrations}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={
            formik.touched.integrations && Boolean(formik.errors.integrations)
          }
          helperText={formik.touched.integrations && formik.errors.integrations}
        />

        {/* ---- Renewal Date + Source Department (optional) ---- */}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <TextField
            fullWidth
            size="small"
            id="tech-renewal-date"
            name="renewal_date"
            label="Renewal Date"
            type="date"
            value={formik.values.renewal_date}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={
              formik.touched.renewal_date && Boolean(formik.errors.renewal_date)
            }
            helperText={
              formik.touched.renewal_date && formik.errors.renewal_date
            }
            InputLabelProps={{ shrink: true }}
          />

          <FormControl fullWidth size="small">
            <InputLabel id="tech-source-dept-label">
              Source Department
            </InputLabel>
            <Select
              labelId="tech-source-dept-label"
              id="tech-source-department"
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

        {/* ---- Source Quote (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="tech-source-quote"
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
          <InputLabel id="tech-signal-category-label">
            Signal Category
          </InputLabel>
          <Select
            labelId="tech-signal-category-label"
            id="tech-signal-category"
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
            {submitLabel ?? "Add Tech Stack"}
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

InlineTechStackForm.propTypes = {
  choices: PropTypes.shape({
    tech_categories: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    satisfaction: PropTypes.arrayOf(
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
