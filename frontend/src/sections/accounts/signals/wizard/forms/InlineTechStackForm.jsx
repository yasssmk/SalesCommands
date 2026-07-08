// frontend/src/sections/accounts/signals/wizard/forms/InlineTechStackForm.jsx
/**
 * InlineTechStackForm — inline form for staging a single TechStackSignal.
 *
 * Captures structured intelligence about a tool used by the account,
 * anchored to a tenant-level TechCatalog entry. The form mirrors the
 * 5-section product spec:
 *
 *   S1 — Which tool?      tech_catalog_entry (REQUIRED)
 *   S2 — How is it used?  usage_scope + usage_department (conditional)
 *   S3 — Lifecycle        usage_start_year, renewal_date, cost_description
 *   S4 — State            is_discontinued + discontinued_date (conditional)
 *   S5 — Source           source_activity, source_quote, notes
 *
 * Conditional rules — strict mirror of TechStackSignal.clean() and the
 * Create / Update serializers:
 *
 *   - usage_scope = DEPARTMENT
 *       → usage_department REQUIRED
 *   - usage_scope ∈ {TEAM, COMPANY, UNKNOWN, null}
 *       → usage_department FORBIDDEN
 *   - is_discontinued = true
 *       → discontinued_date REQUIRED
 *   - is_discontinued = false (default)
 *       → discontinued_date FORBIDDEN
 *
 * The form does NOT call createSignal directly. It calls onAdd(payload)
 * with a ready-to-dispatch payload — the wizard injects account + source
 * + extraPayload at dispatch time and extracts UUIDs from object refs
 * (tech_catalog_entry, usage_department, source_activity).
 *
 * Edit mode is supported via initialValues + submitLabel — when set, the
 * form reinitializes from the prefilled values and the submit button
 * label is overridden ("Save changes" instead of "Add Tech Stack").
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
import AsyncTechCatalogSelect from "components/AsyncSelection/AsyncTechCatalogSelect";
import { canEditCatalogEntry } from "sections/activities/signals/signalValidationRules";
import AsyncActivitySelect from "components/AsyncSelection/AsyncActivitySelect";
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
  tech_catalog_entry: Yup.object()
    .nullable()
    .required("Pick a tool from the catalog"),

  // S2 — Scope
  // null is the "not set" sentinel; '' is coerced to null at submit time.
  usage_scope: Yup.string()
    .nullable()
    .oneOf(
      [...USAGE_SCOPE_OPTIONS.map((o) => o.value), null, ""],
      "Invalid scope",
    ),

  // Conditional: DEPARTMENT requires usage_department, others forbid it.
  usage_department: Yup.string()
    .nullable()
    .when("usage_scope", {
      is: "DEPARTMENT",
      then: (schema) => schema.required("Pick the department using this tool"),
      otherwise: (schema) =>
        schema.test(
          "no-department-outside-scope",
          "Department can only be set when scope is Department",
          (val) => !val,
        ),
    }),

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

  // S5 — Source
  source_activity: Yup.object().nullable(),
  source_quote: Yup.string().nullable(),
  notes: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues() {
  return {
    // S1
    tech_catalog_entry: null,
    // S2
    usage_scope: "",
    usage_department: "",
    // S3
    usage_start_year: "",
    renewal_date: "",
    cost_description: "",
    // S4
    is_discontinued: false,
    discontinued_date: "",
    // S5
    source_activity: null,
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

// ==============================|| CATALOG PREVIEW CARD ||============================== //

/**
 * Compact preview shown below the AsyncTechCatalogSelect once an entry
 * is picked. Reinforces the choice and surfaces strategic flags so
 * the rep can spot a competitor or integration target at a glance.
 *
 * Hidden when no entry is selected — the picker carries its own empty
 * state.
 */
function CatalogPreview({ entry }) {
  if (!entry) return null;

  const company = entry.company_name?.trim() || "";
  const product = entry.product_name?.trim() || "";
  const sameName = !product || product === company;

  return (
    <Box
      sx={{
        px: 1.5,
        py: 1,
        bgcolor: "action.hover",
        borderRadius: 1,
        borderLeft: "3px solid",
        borderLeftColor: "primary.main",
      }}
    >
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
      >
        <Typography
          variant="body2"
          fontWeight={600}
          sx={{ color: "text.primary" }}
        >
          {sameName ? company : `${company} ${product}`}
        </Typography>
        {entry.is_competitor && (
          <Chip
            label="Competitor"
            size="small"
            color="error"
            variant="outlined"
            sx={{ fontSize: "0.62rem", height: 18 }}
          />
        )}
        {entry.is_integration_target && (
          <Chip
            label="Integration target"
            size="small"
            color="info"
            variant="outlined"
            sx={{ fontSize: "0.62rem", height: 18 }}
          />
        )}
      </Stack>
    </Box>
  );
}

CatalogPreview.propTypes = {
  entry: PropTypes.object,
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
 * @param {Object}   defaultContact  - Unused by TechStack (no source_contact
 *                                      on the model) — kept for signature parity
 * @param {Function} onAdd           - (payload: Object) => void
 * @param {Function} onCancel        - () => void
 * @param {Object}   initialValues   - Pre-filled values for edit mode
 * @param {string}   submitLabel     - Override submit button label
 */
export default function InlineTechStackForm({
  // eslint-disable-next-line no-unused-vars
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

  /** Activity search scoped to this account only. */
  const scopedFilters = useMemo(() => ({ account_id: accountId }), [accountId]);

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
        // S1 — required catalog anchor (object — wizard extracts UUID)
        tech_catalog_entry: values.tech_catalog_entry,

        // S2 — scope axis (always emit both for clean clear-on-change)
        usage_scope: values.usage_scope || null,
        usage_department:
          values.usage_scope === "DEPARTMENT" && values.usage_department
            ? values.usage_department
            : null,

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

        // S5 — source (object preserved — wizard extracts UUID)
        source_activity: values.source_activity ?? null,
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

  /**
   * When usage_scope leaves DEPARTMENT, clear usage_department so a
   * stale value doesn't get submitted. Mirrors InlineObjectiveForm.
   */
  useEffect(() => {
    if (
      formik.values.usage_scope !== "DEPARTMENT" &&
      formik.values.usage_department
    ) {
      formik.setFieldValue("usage_department", "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formik.values.usage_scope]);

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
  const catalogEditable = canEditCatalogEntry(initialValuesProp);

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
            subtitle="Pick the tool from your tenant's tech catalog."
          />

          <AsyncTechCatalogSelect
            label="Tool *"
            value={formik.values.tech_catalog_entry}
            onChange={(_e, entry) =>
              formik.setFieldValue("tech_catalog_entry", entry)
            }
            onBlur={() => formik.setFieldTouched("tech_catalog_entry", true)}
            error={
              formik.touched.tech_catalog_entry &&
              Boolean(formik.errors.tech_catalog_entry)
            }
            helperText={
              (formik.touched.tech_catalog_entry &&
                formik.errors.tech_catalog_entry) ||
              undefined
            }
            // Editable while PENDING (link an unmatched signal before
            // validation); locked once VALIDATED — mirrors the backend.
            disabled={!catalogEditable}
          />

          {/* Compact preview — reinforces the choice */}
          <CatalogPreview entry={formik.values.tech_catalog_entry} />

          {isEditMode && !catalogEditable && (
            <Typography
              variant="caption"
              color="text.disabled"
              sx={{ fontStyle: "italic" }}
            >
              The tool cannot be changed once the signal is validated. To point
              this signal at a different tool, delete it and create a new one.
            </Typography>
          )}
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

          {/* Conditional: DEPARTMENT → usage_department */}
          {formik.values.usage_scope === "DEPARTMENT" && (
            <FormControl
              fullWidth
              size="small"
              error={
                formik.touched.usage_department &&
                Boolean(formik.errors.usage_department)
              }
            >
              <InputLabel id="ts-usage-dept-label">
                Usage Department *
              </InputLabel>
              <Select
                labelId="ts-usage-dept-label"
                id="ts-usage-department"
                name="usage_department"
                value={formik.values.usage_department}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                label="Usage Department *"
              >
                {departmentOptions.map((opt) => (
                  <MenuItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </MenuItem>
                ))}
              </Select>
              {formik.touched.usage_department &&
                formik.errors.usage_department && (
                  <FormHelperText>
                    {formik.errors.usage_department}
                  </FormHelperText>
                )}
            </FormControl>
          )}
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
            SECTION 5 — Source
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={5}
            title="Source"
            subtitle="Optional — link to the conversation, exact words, additional context."
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
              "The call or meeting where this tool came up (optional)."
            }
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
   * choices object to all 4 inline forms uniformly.
   */
  choices: PropTypes.object,
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
  /** Unused by TechStack — kept for interface parity with sibling forms */
  defaultContact: PropTypes.object,
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  /** Pre-filled values for edit mode — triggers enableReinitialize */
  initialValues: PropTypes.object,
  /** Override submit button label (default: "Add Tech Stack") */
  submitLabel: PropTypes.string,
};
