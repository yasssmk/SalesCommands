// frontend/src/sections/accounts/signals/wizard/forms/InlinePainForm.jsx
/**
 * InlinePainForm — inline form for staging a single PainSignal.
 *
 * Pain = the DIAGNOSIS (qualitative, narrative).
 * Metrics, departments, humans, and impact-related data all live on
 * PainImpact and are captured separately via AddPainImpactDialog in the
 * Account Workspace — NOT here.
 *
 * This form captures strictly:
 *   - What × Dimension   → canonical axes (drive canonical_key)
 *   - Summary            → qualitative narrative
 *   - Source Activity    → conversation where the pain was identified (required)
 *   - Source Contact     → person who reported it (required)
 *   - Source Quote       → verbatim excerpt (optional)
 *   - Notes              → additional qualitative context (optional)
 *
 * The form does NOT call createSignal directly. It calls onAdd(payload) with
 * a ready-to-dispatch payload — the wizard injects account + source at
 * dispatch time. Contact and activity objects are kept whole; UUIDs are
 * extracted by the wizard at dispatch time.
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
import AsyncActivitySelect from "components/AsyncSelection/AsyncActivitySelect";

// ==============================|| VALIDATION SCHEMA ||============================== //

/**
 * All required fields are marked explicitly. Optional text fields are
 * declared nullable so Yup does not complain on an empty string.
 */
const validationSchema = Yup.object({
  // --- Diagnosis ---
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),

  // --- Source (both strictly required for Pain) ---
  source_contact: Yup.object()
    .nullable()
    .required("Source contact is required"),
  source_activity: Yup.object()
    .nullable()
    .required("Source activity is required"),

  // --- Optional narrative extras ---
  source_quote: Yup.string().nullable(),
  notes: Yup.string().nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues(defaultContact) {
  return {
    // Diagnosis
    summary: "",
    what: "",
    dimension: "",

    // Source
    source_contact: defaultContact ?? null,
    source_activity: null,

    // Optional narrative extras
    source_quote: "",
    notes: "",
  };
}

// ==============================|| HELPERS ||============================== //

/**
 * Resolve a display label from a choices array by value.
 */
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
          color="error"
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

// ==============================|| INLINE PAIN FORM ||============================== //

/**
 * InlinePainForm
 *
 * @param {Object}   choices         - From useGetSignalChoices()
 *                                     Expected keys: pain_whats, pain_dimensions
 * @param {boolean}  choicesLoading  - True while choices are loading
 * @param {string}   accountId       - Account UUID — scopes contact & activity search
 * @param {Object}   defaultContact  - Full contact object to pre-fill source_contact
 * @param {Function} onAdd           - (payload: Object) => void
 * @param {Function} onCancel        - () => void
 * @param {Object}   initialValues   - Pre-filled values for edit mode
 * @param {string}   submitLabel     - Override submit button label (default: "Add Pain")
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
  // ==============================|| SCOPED FILTERS ||============================== //

  /**
   * Both contact and activity search are scoped to this account only —
   * prevents any cross-account data leakage in the dropdowns.
   */
  const scopedFilters = useMemo(() => ({ account_id: accountId }), [accountId]);

  // ==============================|| FORMIK ||============================== //

  const formik = useFormik({
    initialValues: initialValuesProp ?? buildInitialValues(defaultContact),
    validationSchema,
    enableReinitialize: true,
    onSubmit: (values, { resetForm }) => {
      // Build payload — strip empty strings so the backend never receives
      // "" for optional text fields. Send contact/activity objects as-is;
      // the wizard extracts UUIDs at dispatch time.
      const payload = {
        // Required
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
        source_contact: values.source_contact,
        source_activity: values.source_activity,
      };

      // source_quote is nullable at the DB level — null is the explicit
      // "clear this field" signal.
      payload.source_quote =
        values.source_quote && values.source_quote.trim()
          ? values.source_quote.trim()
          : null;

      // notes is NOT NULL with default '' — emit empty string to clear.
      // Sending null would be rejected by DRF (allow_null is False on
      // non-nullable TextField by default).
      payload.notes =
        values.notes && values.notes.trim() ? values.notes.trim() : "";

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

  // ==============================|| DERIVED ||============================== //

  /** Live preview of the canonical_key — shown once both axes are chosen */
  const canonicalPreview = useMemo(() => {
    if (!formik.values.what || !formik.values.dimension) return null;
    return `pain:${formik.values.what}:${formik.values.dimension}`;
  }, [formik.values.what, formik.values.dimension]);

  /** Human-readable preview sentence ("Operations × Time problem") */
  const axisPreview = useMemo(() => {
    const whatLabel = resolveLabel(choices?.signal_whats, formik.values.what);
    const dimensionLabel = resolveLabel(
      choices?.signal_dimensions,
      formik.values.dimension,
    );
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [choices, formik.values.what, formik.values.dimension]);

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
      <Stack spacing={2.5}>
        {/* ---- Header ---- */}
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
        >
          <Typography variant="subtitle2" fontWeight={600}>
            {initialValuesProp ? "Edit Pain Signal" : "New Pain Signal"}
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
            title="What's the problem?"
            subtitle="Describe the pain and pick its canonical axes."
          />

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

          {/* What × Dimension side by side */}
          {/*
            Options come from choices.signal_whats and choices.signal_dimensions
            (shared enums, backend exposes these since Wave A). The model
            fields are still `what` and `dimension` — we only renamed the
            source of enum options, not the fields. The canonical_key
            stored on the row remains "pain:<what>:<dimension>".
          */}
          <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5}>
            <FormControl
              fullWidth
              size="small"
              error={formik.touched.what && Boolean(formik.errors.what)}
              disabled={choicesLoading}
            >
              <InputLabel id="pain-what-label">Domain *</InputLabel>
              <Select
                labelId="pain-what-label"
                id="pain-what"
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
              <InputLabel id="pain-dimension-label">Dimension *</InputLabel>
              <Select
                labelId="pain-dimension-label"
                id="pain-dimension"
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

          {/* Live canonical preview — helps the rep understand what gets stored */}
          {axisPreview && (
            <Box
              sx={{
                px: 1.5,
                py: 1,
                bgcolor: "action.hover",
                borderRadius: 1,
                borderLeft: "3px solid",
                borderLeftColor: "error.main",
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
                problem
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
            SECTION 2 — Source
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Source of the pain"
            subtitle="Which conversation and which person surfaced this pain."
          />

          <AsyncActivitySelect
            label="Source Activity *"
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
              "The call, meeting, or email where this pain was identified."
            }
          />

          <AsyncContactSelect
            label="Source Contact *"
            value={formik.values.source_contact}
            onChange={(_e, contact) =>
              formik.setFieldValue("source_contact", contact)
            }
            onBlur={() => formik.setFieldTouched("source_contact", true)}
            filters={scopedFilters}
            disabled={!accountId}
            error={
              formik.touched.source_contact &&
              Boolean(formik.errors.source_contact)
            }
            helperText={
              (formik.touched.source_contact && formik.errors.source_contact) ||
              "The person who reported or surfaced this pain."
            }
          />
        </Stack>

        <Divider />

        {/* =================================================================
            SECTION 3 — Narrative (optional)
            ================================================================= */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="Narrative (optional)"
            subtitle="Exact words from the source, plus any extra context."
          />

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
            helperText={
              formik.touched.source_quote && formik.errors.source_quote
            }
          />

          <TextField
            fullWidth
            size="small"
            id="pain-notes"
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

        {/* ---- Hint: impacts come later ---- */}
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
            Once this pain is saved, you'll be able to add concrete{" "}
            <Box
              component="span"
              sx={{ fontWeight: 600, color: "text.primary" }}
            >
              impacts
            </Box>{" "}
            (metrics, affected departments or people) from the Account
            workspace.
          </Typography>
        </Box>

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
            color="error"
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
    /**
     * Shared canonical-axis enums exposed by the backend since Wave A.
     * The model fields are still `what` and `dimension`, only the source
     * of options changed (pain_whats → signal_whats, etc.).
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
  defaultContact: PropTypes.object,
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  /** Pre-filled values for edit mode — triggers enableReinitialize */
  initialValues: PropTypes.object,
  /** Override submit button label (default: "Add Pain") */
  submitLabel: PropTypes.string,
};
