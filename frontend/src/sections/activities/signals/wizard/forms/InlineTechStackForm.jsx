// frontend/src/sections/activities/signals/wizard/forms/InlineTechStackForm.jsx
/**
 * InlineTechStackForm — inline form for staging a single TechStackSignal.
 *
 * Captures structured intelligence about a tool used by the account,
 * identified by free text (tech_name). The form mirrors the
 * * This form captures strictly:
 *
 *   S1 — Which tool?      tech_name (REQUIRED) + 3 qualification toggles
 *   S2 — How is it used?  usage_scope (scale) + usage_departments (WHO,
 *                         multi-department, independent of scope)
 *   S3 — Lifecycle        usage_start_year, renewal_date, cost_description
 *   S4 — State            is_discontinued + discontinued_date (conditional)
 *   S5 — Narrative        source_quote, notes
 *
 * Conditional rule — mirror of TechStackSignal.clean() and the
 * Create / Update serializers:
 *
 *   - is_discontinued = true
 *       → discontinued_date REQUIRED
 *   - is_discontinued = false (default)
 *       → discontinued_date FORBIDDEN
 *
 * usage_departments carries NO conditional rule — it is a multi-select of
 * StandardDepartment ids, independent of usage_scope (the WHO is orthogonal
 * to the SCALE). The legacy single usage_department FK was dropped.
 *
 * The form does NOT call createSignal directly. It calls onAdd(payload)
 * with a ready-to-dispatch payload — the wizard injects account + source
 * + extraPayload at dispatch time. usage_departments is emitted as a list
 * of department ids.
 *
 * Edit mode is supported via initialValues + submitLabel — when set, the
 * form reinitializes from the prefilled values and the submit button
 * label is overridden ("Save changes" instead of "Add Tech Stack").
 *
 ** source_activity is NOT a form field
 * -----------------------------------
 * A signal is always created from an activity context — the wizard
 * injects source_activity into the dispatch payload via extraPayload.
 * The form does not surface a picker for it.
 *
 * Note on usage_scope = '' (empty string)
 * ---------------------------------------
 * Yup treats '' as a present-but-empty string. We use null in initial
 * values to represent "not set" so the conditional rule (DEPARTMENT
 * vs others) reads cleanly. The MUI RadioGroup binds to '' for "no
 * selection", so we coerce '' → null before submit.
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
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// ant-design icons
import CloseOutlined from "@ant-design/icons/CloseOutlined";
import PlusOutlined from "@ant-design/icons/PlusOutlined";

// project imports
import { useGetContactChoices } from "api/businessData/contacts";

// ==============================|| CONSTANTS ||============================== //

/**
 * UsageScope options — must match the backend UsageScope enum.
 * Hard-coded here (not pulled from choices) because we want a fixed
 * order and human-friendly helper text per option.
 */
const USAGE_SCOPE_OPTIONS = [
  {
    value: "TEAM",
    label: "Team",
    helper: "Used by a single team within a department",
  },
  {
    value: "DEPARTMENT",
    label: "Department",
    helper: "Used by an identifiable department",
  },
  {
    value: "COMPANY",
    label: "Company-wide",
    helper: "Used across the whole organisation",
  },
  {
    value: "UNKNOWN",
    label: "Unknown",
    helper: "Scope not yet clarified",
  },
];

/** Year bounds for usage_start_year — defensive against typos. */
const MIN_USAGE_YEAR = 1980;
const MAX_USAGE_YEAR = new Date().getFullYear() + 1;

// ==============================|| VALIDATION SCHEMA ||============================== //

/**
 * Yup schema — scope-conditional and discontinued-conditional rules
 * implemented via .when() so error messages surface on the right fields.
 *
 * Backend has the final say (TechStackSignalCreateSerializer.validate)
 * but the UI rules mirror it for instant feedback.
 */
const validationSchema = Yup.object({
  // S1 — Which tool?
  tech_name: Yup.string()
    .trim()
    .required("Name the tool this signal is about"),

  // S2 — Scope
  // null is the "not set" sentinel; '' is coerced to null at submit time.
  usage_scope: Yup.string()
    .nullable()
    .oneOf(
      [...USAGE_SCOPE_OPTIONS.map((o) => o.value), null, ""],
      "Invalid scope",
    ),

  // WHO uses the tool — multi-department, independent of usage_scope.
  // A list of StandardDepartment ids (may be empty: nobody designated).
  usage_departments: Yup.array().of(
    Yup.mixed().test(
      "dept-id",
      "Invalid department",
      (v) => v !== null && v !== undefined && v !== "",
    ),
  ),

  // S3 — Lifecycle
  usage_start_year: Yup.number()
    .nullable()
    .transform((value, original) =>
      // Empty string → null. NaN → null (defensive).
      original === "" || Number.isNaN(value) ? null : value,
    )
    .integer("Year must be a whole number")
    .min(MIN_USAGE_YEAR, `Year must be ≥ ${MIN_USAGE_YEAR}`)
    .max(MAX_USAGE_YEAR, `Year must be ≤ ${MAX_USAGE_YEAR}`),

  renewal_date: Yup.string().nullable(),
  cost_description: Yup.string().nullable(),

  // S4 — State
  is_discontinued: Yup.boolean(),

  discontinued_date: Yup.string()
    .nullable()
    .when("is_discontinued", {
      is: true,
      then: (schema) => schema.required("Discontinued date is required"),
      otherwise: (schema) =>
        schema.test(
          "no-date-without-flag",
          "Discontinued date can only be set when the tool is discontinued",
          (val) => !val,
        ),
    }),

  // S5 — Narrative
  source_quote: Yup.string().nullable(),
  notes: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues() {
  return {
    // S1
    tech_name: "",
    is_competitor: false,
    is_integration: false,
    is_to_replace: false,
    // S2
    usage_scope: "",
    usage_departments: [],
    // S3
    usage_start_year: "",
    renewal_date: "",
    cost_description: "",
    // S4
    is_discontinued: false,
    discontinued_date: "",
    // S5
    source_quote: "",
    notes: "",
  };
}

// ==============================|| SECTION HEADER ||============================== //

function SectionHeader({ index, title, subtitle }) {
  return (
    <Stack spacing={0.25}>
      <Stack direction="row" spacing={1} alignItems="center">
        <Chip
          label={index}
          size="small"
          color="primary"
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

// ==============================|| INLINE TECH STACK FORM ||============================== //

/**
 * InlineTechStackForm
 *
 * @param {Object}   choices         - From useGetSignalChoices()
 *                                     Currently unused — TechStack scope
 *                                     options are hard-coded above.
 *                                     Kept in the signature for parity
 *                                     with sibling inline forms.
 * @param {boolean}  choicesLoading
 * @param {string}   accountId       - Required for source_activity scope
 * @param {Function} onAdd           - (payload: Object) => void
 * @param {Function} onCancel        - () => void
 * @param {Object}   initialValues   - Pre-filled values for edit mode
 * @param {string}   submitLabel     - Override submit button label
 */
export default function InlineTechStackForm({
  // eslint-disable-next-line no-unused-vars
  choices,
  choicesLoading,
  // eslint-disable-next-line no-unused-vars
  accountId,
  onAdd,
  onCancel,
  initialValues: initialValuesProp,
  submitLabel,
}) {
  // ==============================|| DATA ||============================== //

  /**
   * Departments come from the contact-choices endpoint — same source
   * as InlineObjectiveForm. The shape varies (some entries use
   * { value, label }, others { id, name }) so we normalise here.
   */
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
    initialValues: initialValuesProp ?? buildInitialValues(),
    validationSchema,
    enableReinitialize: true,

    onSubmit: (values, { resetForm }) => {
      // Build payload — ALWAYS emit the conditional pair fields so a
      // scope/discontinued change during Edit explicitly clears the
      // stale value on the backend (mirror of InlineObjectiveForm's
      // strategy). Empty strings → null for nullable fields.

      const payload = {
        // S1 — tech identity + qualification (S10). Always emitted:
        // tech_name is required on create and freely editable after,
        // and the three booleans are plain toggles with no lock.
        tech_name: values.tech_name?.trim() || "",
        is_competitor: Boolean(values.is_competitor),
        is_integration: Boolean(values.is_integration),
        is_to_replace: Boolean(values.is_to_replace),

        // S2 — usage scale + who (multi-department M2M, list of ids).
        // Always emit usage_departments so an edit that clears every
        // department explicitly replaces the set on the backend.
        usage_scope: values.usage_scope || null,
        usage_departments: Array.isArray(values.usage_departments)
          ? values.usage_departments
          : [],

        // S3 — lifecycle (omit empty strings → null / undefined)
        usage_start_year:
          values.usage_start_year === "" ||
          values.usage_start_year === null ||
          values.usage_start_year === undefined
            ? null
            : Number(values.usage_start_year),
        renewal_date: values.renewal_date || null,
        cost_description: values.cost_description?.trim() || "",

        // S4 — discontinuation (always emit both)
        is_discontinued: Boolean(values.is_discontinued),
        discontinued_date:
          values.is_discontinued && values.discontinued_date
            ? values.discontinued_date
            : null,

        // S5 — narrative
        source_quote: values.source_quote?.trim() || null,
        notes: values.notes?.trim() || "",
      };

      onAdd(payload);

      // Only reset in create mode — edit mode unmounts the form on success
      if (!initialValuesProp) {
        resetForm({ values: buildInitialValues() });
      }
    },
  });

  // ==============================|| CLEAR CONDITIONAL FIELDS ON SCOPE CHANGE ||============================== //
  //
  // usage_departments is independent of usage_scope (the WHO is orthogonal
  // to the SCALE), so there is no scope-driven clearing here anymore — the
  // former usage_department clear-on-leave-DEPARTMENT effect is gone.

  /**
   * When is_discontinued is toggled OFF, clear discontinued_date.
   */
  useEffect(() => {
    if (!formik.values.is_discontinued && formik.values.discontinued_date) {
      formik.setFieldValue("discontinued_date", "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formik.values.is_discontinued]);

  // ==============================|| DERIVED ||============================== //

  const isEditMode = Boolean(initialValuesProp);

  // Catalog anchor is editable in create mode and while the signal is
  // PENDING (so an LLM-extracted, unmatched signal can be linked before
  // validation); locked once VALIDATED — mirrors the backend rule.

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
      <Stack spacing={2.5}>
        {/* ---- Header ---- */}
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          <Typography variant="subtitle2" fontWeight={600}>
            {isEditMode ? "Edit Tech Stack Signal" : "New Tech Stack Signal"}
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
            SECTION 1 — Which tool?
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="Which tool?"
            subtitle="Name the tool as it came up in the conversation."
          />

          <TextField
            fullWidth
            size="small"
            id="ts-tech-name"
            name="tech_name"
            label="Tool *"
            placeholder="e.g. Salesforce"
            value={formik.values.tech_name}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.tech_name && Boolean(formik.errors.tech_name)}
            helperText={
              (formik.touched.tech_name && formik.errors.tech_name) ||
              "Write the tool's name as it was mentioned. Matching across signals is handled for you."
            }
          />

          {/* Qualification — three INDEPENDENT toggles. Any combination
              is valid, and all-off is the common case: a tool the
              account simply uses. Mirrors the Switch pattern used by
              `is_discontinued` in section 4 below. */}
          <Stack spacing={0.5}>
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={Boolean(formik.values.is_competitor)}
                  onChange={(e) =>
                    formik.setFieldValue("is_competitor", e.target.checked)
                  }
                  inputProps={{ "aria-label": "Tool is a competitor" }}
                />
              }
              label={
                <Typography variant="body2">
                  Competitor — overlaps with what we sell
                </Typography>
              }
              sx={{ m: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={Boolean(formik.values.is_integration)}
                  onChange={(e) =>
                    formik.setFieldValue("is_integration", e.target.checked)
                  }
                  inputProps={{ "aria-label": "Tool is an integration" }}
                />
              }
              label={
                <Typography variant="body2">
                  Integration — our product connects to it
                </Typography>
              }
              sx={{ m: 0 }}
            />
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={Boolean(formik.values.is_to_replace)}
                  onChange={(e) =>
                    formik.setFieldValue("is_to_replace", e.target.checked)
                  }
                  inputProps={{ "aria-label": "Tool is to be replaced" }}
                />
              }
              label={
                <Typography variant="body2">
                  To replace — the account intends to move off it
                </Typography>
              }
              sx={{ m: 0 }}
            />
          </Stack>

        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 2 — How is it used?
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="How is it used?"
            subtitle="Pick the organisational scope of usage at this account."
          />

          <FormControl
            component="fieldset"
            error={
              formik.touched.usage_scope && Boolean(formik.errors.usage_scope)
            }
          >
            <RadioGroup
              row
              name="usage_scope"
              value={formik.values.usage_scope}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              sx={{ gap: 0.5, flexWrap: "wrap" }}
            >
              {USAGE_SCOPE_OPTIONS.map((opt) => (
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
                    flex: { xs: "1 1 45%", sm: "1 1 22%" },
                    minWidth: 0,
                    alignItems: "flex-start",
                    m: 0,
                    p: 1,
                    border: "1px solid",
                    borderColor:
                      formik.values.usage_scope === opt.value
                        ? "primary.main"
                        : "divider",
                    borderRadius: 1,
                    bgcolor:
                      formik.values.usage_scope === opt.value
                        ? "primary.lighter"
                        : "transparent",
                    transition: "border-color 0.15s, background-color 0.15s",
                  }}
                />
              ))}
            </RadioGroup>
            {formik.touched.usage_scope && formik.errors.usage_scope && (
              <FormHelperText>{formik.errors.usage_scope}</FormHelperText>
            )}
          </FormControl>

          {/* WHO uses the tool — multi-department, independent of scope.
              Always available; empty means nobody designated. */}
          <FormControl
            fullWidth
            size="small"
            error={
              formik.touched.usage_departments &&
              Boolean(formik.errors.usage_departments)
            }
          >
            <InputLabel id="ts-usage-depts-label">
              Which department(s) use this tool?
            </InputLabel>
            <Select
              multiple
              labelId="ts-usage-depts-label"
              id="ts-usage-departments"
              name="usage_departments"
              value={formik.values.usage_departments}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Which department(s) use this tool?"
              renderValue={(selected) => (
                <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                  {selected.map((val) => {
                    const opt = departmentOptions.find((o) => o.value === val);
                    return (
                      <Chip
                        key={val}
                        size="small"
                        label={opt ? opt.label : val}
                      />
                    );
                  })}
                </Stack>
              )}
            >
              {departmentOptions.map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
            {formik.touched.usage_departments &&
              formik.errors.usage_departments && (
                <FormHelperText>
                  {formik.errors.usage_departments}
                </FormHelperText>
              )}
          </FormControl>
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 3 — Lifecycle
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="Lifecycle"
            subtitle="Optional — when did they start, when does it renew, what does it cost."
          />

          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <TextField
              fullWidth
              size="small"
              id="ts-usage-start-year"
              name="usage_start_year"
              label="Usage Start Year"
              type="number"
              placeholder="e.g. 2019"
              value={formik.values.usage_start_year}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={
                formik.touched.usage_start_year &&
                Boolean(formik.errors.usage_start_year)
              }
              helperText={
                formik.touched.usage_start_year &&
                formik.errors.usage_start_year
              }
              inputProps={{ min: MIN_USAGE_YEAR, max: MAX_USAGE_YEAR, step: 1 }}
            />
            <TextField
              fullWidth
              size="small"
              id="ts-renewal-date"
              name="renewal_date"
              label="Renewal Date"
              type="date"
              value={formik.values.renewal_date}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={
                formik.touched.renewal_date &&
                Boolean(formik.errors.renewal_date)
              }
              helperText={
                formik.touched.renewal_date && formik.errors.renewal_date
              }
              InputLabelProps={{ shrink: true }}
            />
          </Stack>

          <TextField
            fullWidth
            size="small"
            id="ts-cost-description"
            name="cost_description"
            label="Cost Description"
            placeholder="e.g. around 3000€/month, 80k€/year, free tier"
            multiline
            minRows={2}
            value={formik.values.cost_description}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={
              formik.touched.cost_description &&
              Boolean(formik.errors.cost_description)
            }
            helperText={
              (formik.touched.cost_description &&
                formik.errors.cost_description) ||
              "Free-text cost as expressed during the conversation."
            }
          />
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 4 — State
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={4}
            title="State"
            subtitle="Is this tool still in use, or being phased out?"
          />

          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={Boolean(formik.values.is_discontinued)}
                onChange={(e) =>
                  formik.setFieldValue("is_discontinued", e.target.checked)
                }
                inputProps={{ "aria-label": "Tool is discontinued" }}
              />
            }
            label={
              <Stack spacing={0}>
                <Typography variant="body2" fontWeight={500}>
                  This tool is discontinued
                </Typography>
                <Typography variant="caption" color="text.disabled">
                  The account has stopped, or plans to stop, using this tool.
                </Typography>
              </Stack>
            }
            sx={{ alignItems: "flex-start", m: 0 }}
          />

          {/* Conditional: is_discontinued → discontinued_date */}
          {formik.values.is_discontinued && (
            <TextField
              fullWidth
              size="small"
              id="ts-discontinued-date"
              name="discontinued_date"
              label="Discontinued Date *"
              type="date"
              value={formik.values.discontinued_date}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              error={
                formik.touched.discontinued_date &&
                Boolean(formik.errors.discontinued_date)
              }
              helperText={
                (formik.touched.discontinued_date &&
                  formik.errors.discontinued_date) ||
                "Past dates indicate already-stopped usage; future dates indicate a planned phase-out."
              }
              InputLabelProps={{ shrink: true }}
            />
          )}
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 5 — Narrative
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={5}
            title="Narrative"
            subtitle="Optional — exact words from the conversation, additional context."
          />

          <TextField
            fullWidth
            size="small"
            id="ts-source-quote"
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
            helperText={
              formik.touched.source_quote && formik.errors.source_quote
            }
          />

          <TextField
            fullWidth
            size="small"
            id="ts-notes"
            name="notes"
            label="Notes"
            placeholder="Additional qualitative context about this observation…"
            multiline
            minRows={2}
            value={formik.values.notes}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={formik.touched.notes && Boolean(formik.errors.notes)}
            helperText={formik.touched.notes && formik.errors.notes}
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
            color="primary"
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
  /**
   * Currently unused — TechStack scope options are hard-coded in this
   * file. Kept in the signature so the wizard can pass the same shared
   * choices object to all inline forms uniformly.
   */
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  /** Pre-filled values for edit mode — triggers enableReinitialize */
  initialValues: PropTypes.object,
  /** Override submit button label (default: "Add Tech Stack") */
  submitLabel: PropTypes.string,
};
