// frontend/src/sections/activities/signals/wizard/forms/InlineImpactForm.jsx
/**
 * InlineImpactForm — inline form for editing a single ImpactSignal.
 *
 * Impact = quantifiable evidence attached to a (what × dimension) canonical
 * axis. Created exclusively via the LLM extraction pipeline at the MVP
 * stage; this form surfaces ONLY in the Edit context (SignalEditDialog).
 *
 * This form captures strictly:
 *   S1 — Diagnosis:      summary + what × dimension (canonical axes)
 *   S2 — Characterisation: impact_type (REQUIRED) + human_impact + metric_text
 *   S3 — Scope:          scope_level (BUSINESS / DEPARTMENT / PERSONAL)
 *
 * Differences from InlineObjectiveForm (intentional):
 *   - NO target_contact (Impact has no PERSONAL owner FK)
 *   - NO target_department (Impact has no DEPARTMENT owner FK)
 *   - NO target_date (Impact has no deadline semantics)
 *   - NO success_criteria (Impact is the evidence itself, not a goal)
 *   - YES impact_type (REQUIRED — characterises the nature of the impact)
 *   - YES human_impact (optional — human consequence label)
 *   - YES metric_text (optional — quantitative free-text evidence)
 *
 * source_activity is NOT a form field
 * -----------------------------------
 * A signal is always created from an activity context — the LLM pipeline
 * sets source_activity at extraction time. PATCH is partial, so omitting
 * source_activity leaves the existing FK untouched.
 *
 * The form does NOT call updateSignal directly. It calls onAdd(payload)
 * with a ready-to-dispatch payload — SignalEditDialog dispatches the
 * PATCH and surfaces errors.
 */

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";
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

// ==============================|| CONSTANTS ||============================== //

/**
 * Scope level enum values — must match backend ScopeLevel constants.
 * Hard-coded here for form-friendly short labels and helper text.
 * Mirrors InlineObjectiveForm.
 */
const SCOPE_OPTIONS = [
  {
    value: "BUSINESS",
    label: "Business",
    helper: "The whole company is affected by this impact",
  },
  {
    value: "DEPARTMENT",
    label: "Department",
    helper: "A specific department feels this impact",
  },
  {
    value: "PERSONAL",
    label: "Personal",
    helper: "A single contact experiences this impact",
  },
];

// ==============================|| VALIDATION SCHEMA ||============================== //

/**
 * Yup schema — Impact has fewer conditional rules than Objective
 * (no target_* fields) but requires impact_type explicitly.
 */
const validationSchema = Yup.object({
  // --- S1: Diagnosis ---
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),

  // --- S2: Characterisation ---
  impact_type: Yup.string().required("Impact type is required"),
  human_impact: Yup.string().nullable(),
  metric_text: Yup.string().nullable(),

  // --- S3: Scope ---
  scope_level: Yup.string()
    .oneOf(
      SCOPE_OPTIONS.map((o) => o.value),
      "Invalid scope level",
    )
    .required("Scope is required"),

  // --- Optional narrative ---
  notes: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues() {
  return {
    // S1: Diagnosis
    summary: "",
    what: "",
    dimension: "",

    // S2: Characterisation
    impact_type: "",
    human_impact: "",
    metric_text: "",

    // S3: Scope
    scope_level: "",

    // Narrative
    notes: "",
    source_quote: "",
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
          color="secondary"
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

// ==============================|| INLINE IMPACT FORM ||============================== //

/**
 * InlineImpactForm
 *
 * @param {Object}   choices          - From useGetSignalChoices()
 *                                      Expected keys: signal_whats, signal_dimensions,
 *                                      impact_types, human_impacts
 * @param {boolean}  choicesLoading   - True while choices are loading
 * @param {string}   accountId        - Account UUID (kept for signature parity)
 * @param {Function} onAdd            - (payload: Object) => void
 *                                      In edit context (SignalEditDialog),
 *                                      this is the save handler.
 * @param {Function} onCancel         - () => void
 * @param {Object}   initialValues    - Pre-filled values for edit mode
 * @param {string}   submitLabel      - Override submit button label (default: "Add Impact")
 */
export default function InlineImpactForm({
  choices,
  choicesLoading,
  // eslint-disable-next-line no-unused-vars
  accountId,
  onAdd,
  onCancel,
  initialValues: initialValuesProp,
  submitLabel,
}) {
  // ==============================|| FORMIK ||============================== //

  const formik = useFormik({
    initialValues: initialValuesProp ?? buildInitialValues(),
    validationSchema,
    enableReinitialize: true,
    onSubmit: (values, { resetForm }) => {
      // Build payload — strip empty strings so the backend never sees
      // "" for optional text fields. Send all conditional fields
      // explicitly so an Edit that clears a value reaches the backend.
      const payload = {
        // Required
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
        impact_type: values.impact_type,
        scope_level: values.scope_level,
      };

      // Optional fields — null is the explicit "clear this field" signal
      // for nullable backend fields. human_impact is nullable on the model.
      payload.human_impact = values.human_impact || null;

      // metric_text is a CharField(blank=True) — NOT NULL. Emit an empty
      // string to clear it; sending null triggers a 400 "may not be null".
      payload.metric_text =
        values.metric_text && values.metric_text.trim()
          ? values.metric_text.trim()
          : "";

      // source_quote is nullable at the DB level
      payload.source_quote =
        values.source_quote && values.source_quote.trim()
          ? values.source_quote.trim()
          : null;

      // notes is NOT NULL with default '' — emit empty string to clear
      payload.notes =
        values.notes && values.notes.trim() ? values.notes.trim() : "";

      onAdd(payload);

      // Only reset in create mode — edit mode unmounts the form on success
      if (!initialValuesProp) {
        resetForm({ values: buildInitialValues() });
      }
    },
  });

  // ==============================|| DERIVED ||============================== //

  /** Live canonical preview — shown once both axes are chosen */
  const canonicalPreview = useMemo(() => {
    if (!formik.values.what || !formik.values.dimension) return null;
    return `impact:${formik.values.what}:${formik.values.dimension}`;
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
        borderColor: "secondary.light",
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
            {isEditMode ? "Edit Impact Signal" : "New Impact Signal"}
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
            SECTION 1 — Diagnosis
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the impact?"
            subtitle="Describe the impact and pick its canonical axes."
          />

          <TextField
            fullWidth
            size="small"
            id="impact-summary"
            name="summary"
            label="Summary *"
            placeholder="e.g. Sales team loses 3 hours per week on manual reporting"
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
              <InputLabel id="impact-what-label">Domain *</InputLabel>
              <Select
                labelId="impact-what-label"
                id="impact-what"
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
              <InputLabel id="impact-dimension-label">Dimension *</InputLabel>
              <Select
                labelId="impact-dimension-label"
                id="impact-dimension"
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
                borderLeftColor: "secondary.main",
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
                impact
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
            SECTION 2 — Characterisation
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="How does it manifest?"
            subtitle="Characterise the nature of the impact and its measurable evidence."
          />

          <FormControl
            fullWidth
            size="small"
            error={
              formik.touched.impact_type && Boolean(formik.errors.impact_type)
            }
            disabled={choicesLoading}
          >
            <InputLabel id="impact-type-label">Impact Type *</InputLabel>
            <Select
              labelId="impact-type-label"
              id="impact-type"
              name="impact_type"
              value={formik.values.impact_type}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Impact Type *"
            >
              {(choices?.impact_types ?? []).map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
            {formik.touched.impact_type && formik.errors.impact_type && (
              <FormHelperText>{formik.errors.impact_type}</FormHelperText>
            )}
          </FormControl>

          <FormControl
            fullWidth
            size="small"
            error={
              formik.touched.human_impact && Boolean(formik.errors.human_impact)
            }
            disabled={choicesLoading}
          >
            <InputLabel id="impact-human-label">Human Impact</InputLabel>
            <Select
              labelId="impact-human-label"
              id="impact-human-impact"
              name="human_impact"
              value={formik.values.human_impact}
              onChange={formik.handleChange}
              onBlur={formik.handleBlur}
              label="Human Impact"
            >
              <MenuItem value="">
                <em>None</em>
              </MenuItem>
              {(choices?.human_impacts ?? []).map((opt) => (
                <MenuItem key={opt.value} value={opt.value}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
            <FormHelperText>
              {(formik.touched.human_impact && formik.errors.human_impact) ||
                "Optional — the human consequence (e.g. frustration, overload)."}
            </FormHelperText>
          </FormControl>

          <TextField
            fullWidth
            size="small"
            id="impact-metric-text"
            name="metric_text"
            label="Metric"
            placeholder="e.g. 3h/week lost, 120k€/year, 5 missed deals per quarter"
            multiline
            minRows={2}
            value={formik.values.metric_text}
            onChange={formik.handleChange}
            onBlur={formik.handleBlur}
            error={
              formik.touched.metric_text && Boolean(formik.errors.metric_text)
            }
            helperText={
              (formik.touched.metric_text && formik.errors.metric_text) ||
              "Optional — quantitative evidence in free-text form."
            }
          />
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 3 — Scope
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="Who feels it?"
            subtitle="Pick the organisational scope of this impact."
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
                        ? "secondary.main"
                        : "divider",
                    borderRadius: 1,
                    bgcolor:
                      formik.values.scope_level === opt.value
                        ? "secondary.lighter"
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
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 4 — Narrative (optional)
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={4}
            title="Narrative (optional)"
            subtitle="Exact words from the source, plus any extra context."
          />

          <TextField
            fullWidth
            size="small"
            id="impact-source-quote"
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
            id="impact-notes"
            name="notes"
            label="Notes"
            placeholder="Additional qualitative context…"
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
            color="secondary"
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
            {submitLabel ?? "Add Impact"}
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

InlineImpactForm.propTypes = {
  choices: PropTypes.shape({
    /**
     * Shared canonical-axis enums exposed by the backend.
     * The model fields `what` and `dimension` read their options from
     * signal_whats / signal_dimensions respectively.
     */
    signal_whats: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    signal_dimensions: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    /**
     * Impact-specific enums exposed by SignalChoicesView (W3.8).
     */
    impact_types: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
    human_impacts: PropTypes.arrayOf(
      PropTypes.shape({ value: PropTypes.string, label: PropTypes.string }),
    ),
  }),
  choicesLoading: PropTypes.bool,
  accountId: PropTypes.string.isRequired,
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  /** Pre-filled values for edit mode — triggers enableReinitialize */
  initialValues: PropTypes.object,
  /** Override submit button label (default: "Add Impact") */
  submitLabel: PropTypes.string,
};
