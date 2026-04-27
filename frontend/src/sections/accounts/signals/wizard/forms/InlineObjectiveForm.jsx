// frontend/src/sections/accounts/signals/wizard/forms/InlineObjectiveForm.jsx
/**
 * InlineObjectiveForm — inline form for staging a single ObjectiveSignal.
 *
 * Objective = a structured goal observed at an account. Unlike Pain
 * (qualitative problem + quantitative impacts), Objective captures the
 * desired outcome in a single flat form — no child sub-resource.
 *
 * This form captures strictly:
 *   S1 — Goal:    what × dimension + summary   (canonical axes + narrative)
 *   S2 — Scope:   scope_level + conditional target_contact OR target_department
 *   S3 — Success: success_criteria + target_date + notes
 *   S4 — Source:  source_activity (optional — MVP link to activity only)
 *
 * The form does NOT call createSignal directly. It calls onAdd(payload)
 * with a ready-to-dispatch payload — the wizard injects account + source
 * at dispatch time. Contact and activity objects are kept whole; UUIDs
 * are extracted by the wizard at dispatch time.
 *
 * Scope-conditional rules (mirror of backend ObjectiveSignal.clean()):
 *   PERSONAL   → target_contact required, target_department forbidden
 *   DEPARTMENT → target_department required, target_contact forbidden
 *   BUSINESS   → neither target_contact nor target_department
 *
 * Validation is enforced here via Yup AND on the backend via model/serializer —
 * the UI rules mirror the server contract for a fast feedback loop.
 */

"use client";

import PropTypes from "prop-types";
import { useMemo, useEffect } from "react";
import { useFormik } from "formik";
import * as Yup from "yup";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormHelperText from "@mui/material/FormHelperText";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";
import AsyncActivitySelect from "components/AsyncSelection/AsyncActivitySelect";
import { useGetContactChoices } from "api/businessData/contacts";

// ==============================|| CONSTANTS ||============================== //

/**
 * Scope level enum values — must match backend ScopeLevel constants.
 * Hard-coded here because the RadioGroup is visually tied to the 3
 * specific options and we want the labels to be form-friendly (short
 * buttons), not the verbose enum labels from the choices endpoint.
 */
const SCOPE_OPTIONS = [
  {
    value: "BUSINESS",
    label: "Business",
    helper: "The whole company is driving this goal",
  },
  {
    value: "DEPARTMENT",
    label: "Department",
    helper: "A specific department owns this goal",
  },
  {
    value: "PERSONAL",
    label: "Personal",
    helper: "A single contact is pushing this goal",
  },
];

// ==============================|| VALIDATION SCHEMA ||============================== //

/**
 * Yup schema — scope-conditional rules handled with Yup's .when()
 * to produce clean field-level error messages.
 */
const validationSchema = Yup.object({
  // --- S1: Goal ---
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),

  // --- S2: Scope ---
  scope_level: Yup.string()
    .oneOf(
      SCOPE_OPTIONS.map((o) => o.value),
      "Invalid scope level",
    )
    .required("Scope is required"),

  // Conditional: PERSONAL requires target_contact, forbids target_department
  target_contact: Yup.object()
    .nullable()
    .when("scope_level", {
      is: "PERSONAL",
      then: (schema) =>
        schema
          .required("Personal objectives require a target contact")
          .typeError("Personal objectives require a target contact"),
      otherwise: (schema) => schema.nullable(),
    }),

  // Conditional: DEPARTMENT requires target_department, forbids target_contact
  target_department: Yup.string()
    .nullable()
    .when("scope_level", {
      is: "DEPARTMENT",
      then: (schema) =>
        schema.required("Department objectives require a target department"),
      otherwise: (schema) => schema.nullable(),
    }),

  // --- S3: Success ---
  success_criteria: Yup.string().nullable(),
  target_date: Yup.string().nullable(), // ISO yyyy-mm-dd, stored as string
  notes: Yup.string().nullable(),

  // --- S4: Source ---
  source_activity: Yup.object().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues() {
  return {
    // S1: Goal
    summary: "",
    what: "",
    dimension: "",

    // S2: Scope
    scope_level: "",
    target_contact: null,
    target_department: "",

    // S3: Success
    success_criteria: "",
    target_date: "",
    notes: "",

    // S4: Source
    source_activity: null,
  };
}

// ==============================|| HELPERS ||============================== //

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// ==============================|| SECTION HEADER ||============================== //

function SectionHeader({ index, title, subtitle }) {
  return (
    <Stack spacing={0.25}>
      <Stack direction="row" spacing={1} alignItems="center">
        <Chip
          label={index}
          size="small"
          color="info"
          sx={{
            height: 18,
            width: 18,
            fontSize: "0.65rem",
            fontWeight: 700,
            "& .MuiChip-label": { px: 0 },
          }}
        />
        <Typography variant="body2" fontWeight={600}>
          {title}
        </Typography>
      </Stack>
      {subtitle && (
        <Typography variant="caption" color="text.secondary" sx={{ pl: 3.25 }}>
          {subtitle}
        </Typography>
      )}
    </Stack>
  );
}

SectionHeader.propTypes = {
  index: PropTypes.number.isRequired,
  title: PropTypes.string.isRequired,
  subtitle: PropTypes.string,
};

// ==============================|| INLINE OBJECTIVE FORM ||============================== //

/**
 * InlineObjectiveForm
 *
 * @param {Object}   choices          - From useGetSignalChoices()
 *                                      Expected keys: signal_whats, signal_dimensions
 * @param {boolean}  choicesLoading   - True while choices are loading
 * @param {string}   accountId        - Account UUID — scopes contact & activity search
 * @param {Object}   defaultContact   - Full contact object (not used for source_contact
 *                                      here — kept for signature parity with other
 *                                      inline forms that drive source_contact)
 * @param {Function} onAdd            - (payload: Object) => void
 * @param {Function} onCancel         - () => void
 * @param {Object}   initialValues    - Pre-filled values for edit mode
 * @param {string}   submitLabel      - Override submit button label (default: "Add Objective")
 */
export default function InlineObjectiveForm({
  choices,
  choicesLoading,
  accountId,
  // eslint-disable-next-line no-unused-vars
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

  /** Contact + activity search scoped to this account only */
  const scopedFilters = useMemo(() => ({ account_id: accountId }), [accountId]);

  // ==============================|| FORMIK ||============================== //

  const formik = useFormik({
    initialValues: initialValuesProp ?? buildInitialValues(),
    validationSchema,
    enableReinitialize: true,
    onSubmit: (values, { resetForm }) => {
      // Build payload — strip empty strings so the backend never sees ""
      // for optional text fields. Contact / activity objects sent whole;
      // the wizard extracts UUIDs at dispatch time.
      const payload = {
        // Required
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
        scope_level: values.scope_level,
      };

      // Scope-conditional target — ALWAYS emit both fields in the payload
      // so that a scope change during Edit explicitly clears the stale
      // field on the backend. In Create this is also correct — sending
      // null for the non-applicable field is accepted by the serializer
      // (allow_null=True on both target_contact and target_department).
      //
      // Without this, editing DEPARTMENT → BUSINESS would leave the
      // previous target_department on the DB row and the model's clean()
      // would reject with OBJECTIVE_BUSINESS_NO_DEPT.
      payload.target_contact =
        values.scope_level === "PERSONAL" && values.target_contact
          ? values.target_contact
          : null;

      payload.target_department =
        values.scope_level === "DEPARTMENT" && values.target_department
          ? values.target_department
          : null;

      // Optional extras
      if (values.success_criteria && values.success_criteria.trim()) {
        payload.success_criteria = values.success_criteria.trim();
      }
      if (values.target_date) {
        payload.target_date = values.target_date;
      }
      if (values.notes && values.notes.trim()) {
        payload.notes = values.notes.trim();
      }
      if (values.source_activity) {
        payload.source_activity = values.source_activity;
      }

      onAdd(payload);
      resetForm({ values: buildInitialValues() });
    },
  });

  // ==============================|| CLEAR CONDITIONAL FIELDS ON SCOPE CHANGE ||============================== //

  /**
   * When scope_level switches, clear the fields that no longer apply.
   * This prevents stale values from being submitted and keeps the
   * UI in sync with the backend's scope-conditional validation.
   */
  useEffect(() => {
    const scope = formik.values.scope_level;
    if (scope !== "PERSONAL" && formik.values.target_contact) {
      formik.setFieldValue("target_contact", null);
    }
    if (scope !== "DEPARTMENT" && formik.values.target_department) {
      formik.setFieldValue("target_department", "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formik.values.scope_level]);

  // ==============================|| DERIVED ||============================== //

  /** Live canonical preview — shown once both axes are chosen */
  const canonicalPreview = useMemo(() => {
    if (!formik.values.what || !formik.values.dimension) return null;
    return `objective:${formik.values.what}:${formik.values.dimension}`;
  }, [formik.values.what, formik.values.dimension]);

  const axisPreview = useMemo(() => {
    const whatLabel = resolveLabel(choices?.signal_whats, formik.values.what);
    const dimensionLabel = resolveLabel(
      choices?.signal_dimensions,
      formik.values.dimension,
    );
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [choices, formik.values.what, formik.values.dimension]);

  const isEditMode = Boolean(initialValuesProp);

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
      <Stack spacing={2.5}>
        {/* ---- Header ---- */}
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          <Typography variant="subtitle2" fontWeight={600}>
            {isEditMode ? "Edit Objective Signal" : "New Objective Signal"}
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

        {/* =================================================================
            SECTION 1 — What's the goal?
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the goal?"
            subtitle="Describe the objective and pick its canonical axes."
          />

          <TextField
            fullWidth
            size="small"
            id="objective-summary"
            name="summary"
            label="Summary *"
            placeholder="e.g. Reduce onboarding time by 30%"
            multiline
            minRows={2}
            value={formik.values.summary}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.summary && Boolean(formik.errors.summary)}
            helperText={formik.touched.summary && formik.errors.summary}
          />

          {/* What × Dimension side by side */}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <FormControl
              fullWidth
              size="small"
              error={formik.touched.what && Boolean(formik.errors.what)}
              disabled={choicesLoading}
            >
              <InputLabel id="objective-what-label">Domain *</InputLabel>
              <Select
                labelId="objective-what-label"
                id="objective-what"
                name="what"
                value={formik.values.what}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                label="Domain *"
              >
                {(choices?.signal_whats ?? []).map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
              {formik.touched.what && formik.errors.what && (
                <FormHelperText>{formik.errors.what}</FormHelperText>
              )}
            </FormControl>

            <FormControl
              fullWidth
              size="small"
              error={
                formik.touched.dimension && Boolean(formik.errors.dimension)
              }
              disabled={choicesLoading}
            >
              <InputLabel id="objective-dimension-label">
                Dimension *
              </InputLabel>
              <Select
                labelId="objective-dimension-label"
                id="objective-dimension"
                name="dimension"
                value={formik.values.dimension}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                label="Dimension *"
              >
                {(choices?.signal_dimensions ?? []).map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
              {formik.touched.dimension && formik.errors.dimension && (
                <FormHelperText>{formik.errors.dimension}</FormHelperText>
              )}
            </FormControl>
          </Stack>

          {/* Live canonical preview */}
          {axisPreview && (
            <Box
              sx={{
                px: 1.5,
                py: 1,
                bgcolor: "action.hover",
                borderRadius: 1,
                borderLeft: "3px solid",
                borderLeftColor: "info.main",
              }}
            >
              <Typography variant="caption" color="text.secondary">
                This is a{" "}
                <Box
                  component="span"
                  sx={{ fontWeight: 600, color: "text.primary" }}
                >
                  {axisPreview}
                </Box>{" "}
                goal
              </Typography>
              <Typography
                variant="caption"
                color="text.disabled"
                display="block"
                sx={{ fontFamily: "monospace", fontSize: "0.7rem", mt: 0.25 }}
              >
                canonical_key: {canonicalPreview}
              </Typography>
            </Box>
          )}
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 2 — Who owns it?
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Who owns it?"
            subtitle="Pick the organisational scope driving this goal."
          />

          <FormControl
            component="fieldset"
            error={
              formik.touched.scope_level && Boolean(formik.errors.scope_level)
            }
          >
            <RadioGroup
              row
              name="scope_level"
              value={formik.values.scope_level}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              sx={{ gap: 0.5 }}
            >
              {SCOPE_OPTIONS.map((opt) => (
                <FormControlLabel
                  key={opt.value}
                  value={opt.value}
                  control={<Radio size="small" />}
                  label={
                    <Stack spacing={0}>
                      <Typography variant="body2" fontWeight={500}>
                        {opt.label}
                      </Typography>
                      <Typography variant="caption" color="text.disabled">
                        {opt.helper}
                      </Typography>
                    </Stack>
                  }
                  sx={{
                    flex: 1,
                    minWidth: 0,
                    alignItems: "flex-start",
                    m: 0,
                    p: 1,
                    border: "1px solid",
                    borderColor:
                      formik.values.scope_level === opt.value
                        ? "info.main"
                        : "divider",
                    borderRadius: 1,
                    bgcolor:
                      formik.values.scope_level === opt.value
                        ? "info.lighter"
                        : "transparent",
                    transition: "border-color 0.15s, background-color 0.15s",
                  }}
                />
              ))}
            </RadioGroup>
            {formik.touched.scope_level && formik.errors.scope_level && (
              <FormHelperText>{formik.errors.scope_level}</FormHelperText>
            )}
          </FormControl>

          {/* Conditional: PERSONAL → target_contact */}
          {formik.values.scope_level === "PERSONAL" && (
            <AsyncContactSelect
              label="Target Contact *"
              value={formik.values.target_contact}
              onChange={(_e, contact) =>
                formik.setFieldValue("target_contact", contact)
              }
              onBlur={() => formik.setFieldTouched("target_contact", true)}
              filters={scopedFilters}
              disabled={!accountId}
              error={
                formik.touched.target_contact &&
                Boolean(formik.errors.target_contact)
              }
              helperText={
                (formik.touched.target_contact &&
                  formik.errors.target_contact) ||
                "The person driving this objective."
              }
            />
          )}

          {/* Conditional: DEPARTMENT → target_department */}
          {formik.values.scope_level === "DEPARTMENT" && (
            <FormControl
              fullWidth
              size="small"
              error={
                formik.touched.target_department &&
                Boolean(formik.errors.target_department)
              }
            >
              <InputLabel id="objective-target-dept-label">
                Target Department *
              </InputLabel>
              <Select
                labelId="objective-target-dept-label"
                id="objective-target-department"
                name="target_department"
                value={formik.values.target_department}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                label="Target Department *"
              >
                {departmentOptions.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
              {formik.touched.target_department &&
                formik.errors.target_department && (
                  <FormHelperText>
                    {formik.errors.target_department}
                  </FormHelperText>
                )}
            </FormControl>
          )}
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 3 — How is success measured?
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="How is success measured?"
            subtitle="Optional — success criteria, deadline, and notes."
          />

          <TextField
            fullWidth
            size="small"
            id="objective-success-criteria"
            name="success_criteria"
            label="Success Criteria"
            placeholder="e.g. Onboarding NPS > 40, measured quarterly"
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

          <TextField
            fullWidth
            size="small"
            id="objective-target-date"
            name="target_date"
            label="Target Date"
            type="date"
            value={formik.values.target_date}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            InputLabelProps={{ shrink: true }}
            error={
              formik.touched.target_date && Boolean(formik.errors.target_date)
            }
            helperText={
              (formik.touched.target_date && formik.errors.target_date) ||
              "When the goal should be achieved (optional)."
            }
          />

          <TextField
            fullWidth
            size="small"
            id="objective-notes"
            name="notes"
            label="Notes"
            placeholder="Source quotes, caveats, or anything else worth remembering…"
            multiline
            minRows={2}
            value={formik.values.notes}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.notes && Boolean(formik.errors.notes)}
            helperText={formik.touched.notes && formik.errors.notes}
          />
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 4 — Source
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={4}
            title="Source"
            subtitle="Link this objective to the conversation where it surfaced."
          />

          <AsyncActivitySelect
            label="Source Activity"
            value={formik.values.source_activity}
            onChange={(_e, activity) =>
              formik.setFieldValue("source_activity", activity)
            }
            onBlur={() => formik.setFieldTouched("source_activity", true)}
            filters={scopedFilters}
            disabled={!accountId}
            error={
              formik.touched.source_activity &&
              Boolean(formik.errors.source_activity)
            }
            helperText={
              (formik.touched.source_activity &&
                formik.errors.source_activity) ||
              "Optional — the call or meeting where this goal was discussed."
            }
          />
        </Stack>

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
            color="info"
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
    /**
     * Shared canonical-axis enums exposed by the backend since Wave A.
     * The model fields `what` and `dimension` read their options from
     * signal_whats / signal_dimensions respectively.
     */
    signal_whats: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    signal_dimensions: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
  }),
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
  /** Unused by Objective — kept for interface parity with other inline forms */
  defaultContact: PropTypes.object,
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  /** Pre-filled values for edit mode — triggers enableReinitialize */
  initialValues: PropTypes.object,
  /** Override submit button label (default: "Add Objective") */
  submitLabel: PropTypes.string,
};
