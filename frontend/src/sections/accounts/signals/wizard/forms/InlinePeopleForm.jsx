// frontend/src/sections/accounts/signals/wizard/forms/InlinePeopleForm.jsx
/**
 * InlinePeopleForm — inline form for staging a single PeopleSignal inside the wizard.
 *
 * This form does NOT call createSignal directly.
 * It calls onAdd(payload) with a ready-to-dispatch payload object.
 * The wizard container (WizardSignalAdd) injects account + extraPayload
 * at dispatch time.
 *
 * Required fields: role only.
 * source_contact is OPTIONAL for PeopleSignal.
 *
 * Contact fields use AsyncContactSelect scoped to the account via
 * filters={{ account_id: accountId }} — only contacts from this account
 * are shown. Formik stores the full contact object; .id is extracted
 * when building the payload.
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
  role: Yup.string().required("Role is required"),
  influence_level: Yup.string().nullable(),
  // Contact fields store full objects — .id extracted at payload build time
  target_contact: Yup.object().nullable(),
  target_department: Yup.string().nullable(),
  notes: Yup.string().nullable(),
  source_contact: Yup.object().nullable(),
  source_department: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
  signal_category: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues(defaultContact) {
  return {
    role: "",
    influence_level: "",
    target_contact: null,
    target_department: "",
    notes: "",
    source_contact: defaultContact ?? null,
    source_department: "",
    source_quote: "",
    signal_category: "",
  };
}

// ==============================|| INLINE PEOPLE FORM ||============================== //

/**
 * InlinePeopleForm
 *
 * @param {Object}   choices         - Choices from useGetSignalChoices()
 * @param {boolean}  choicesLoading  - True while choices are loading
 * @param {string}   accountId       - Account UUID — scopes contact search
 * @param {Object}   defaultContact  - Full contact object to pre-fill source_contact
 * @param {Function} onAdd           - (payload: Object) => void
 * @param {Function} onCancel        - () => void
 */
export default function InlinePeopleForm({
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
        role: values.role,
      };

      // Keep full contact objects — UUIDs are extracted at dispatch time
      // (wizard dispatch or SignalEditDialog PATCH)
      if (values.source_contact) payload.source_contact = values.source_contact;
      if (values.target_contact) payload.target_contact = values.target_contact;
      if (values.influence_level)
        payload.influence_level = values.influence_level;
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
        borderColor: "secondary.light",
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
            New People Signal
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

        {/* ---- Role (required) ---- */}
        <FormControl
          fullWidth
          size="small"
          error={formik.touched.role && Boolean(formik.errors.role)}
          disabled={choicesLoading}
        >
          <InputLabel id="people-role-label">Role *</InputLabel>
          <Select
            labelId="people-role-label"
            id="people-role"
            name="role"
            value={formik.values.role}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            label="Role *"
          >
            {(choices?.people_roles ?? []).map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
          {formik.touched.role && formik.errors.role && (
            <FormHelperText>{formik.errors.role}</FormHelperText>
          )}
        </FormControl>

        {/* ---- Influence Level (optional) ---- */}
        <FormControl fullWidth size="small" disabled={choicesLoading}>
          <InputLabel id="people-influence-label">Influence Level</InputLabel>
          <Select
            labelId="people-influence-label"
            id="people-influence-level"
            name="influence_level"
            value={formik.values.influence_level}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            label="Influence Level"
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {(choices?.influence_levels ?? []).map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

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
            <InputLabel id="people-target-dept-label">
              Target Department
            </InputLabel>
            <Select
              labelId="people-target-dept-label"
              id="people-target-department"
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

        {/* ---- Notes (optional) ---- */}
        <TextField
          fullWidth
          size="small"
          id="people-notes"
          name="notes"
          label="Notes"
          placeholder="Additional context about this stakeholder…"
          multiline
          minRows={2}
          value={formik.values.notes}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
          error={formik.touched.notes && Boolean(formik.errors.notes)}
          helperText={formik.touched.notes && formik.errors.notes}
        />

        {/* ---- Source Contact + Source Department (optional) ---- */}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
          <AsyncContactSelect
            label="Source Contact"
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

          <FormControl fullWidth size="small">
            <InputLabel id="people-source-dept-label">
              Source Department
            </InputLabel>
            <Select
              labelId="people-source-dept-label"
              id="people-source-department"
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
          id="people-source-quote"
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
          <InputLabel id="people-signal-category-label">
            Signal Category
          </InputLabel>
          <Select
            labelId="people-signal-category-label"
            id="people-signal-category"
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
            {submitLabel ?? "Add People"}
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

InlinePeopleForm.propTypes = {
  choices: PropTypes.shape({
    people_roles: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    influence_levels: PropTypes.arrayOf(
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
