// frontend/src/sections/activities/signals/wizard/forms/InlinePainForm.jsx
/**
 * InlinePainForm — inline form for staging a single PainSignal.
 *
 * Pain = the DIAGNOSIS (qualitative, narrative).
 * Metrics, departments, humans, and impact-related data all live on
 * PainImpact and are captured separately via AddPainImpactDialog in the
 * Account Workspace — NOT here.
 *
 * * This form captures strictly:
 *   - What × Dimension          → canonical axes (drive canonical_key)
 *   - Summary                   → qualitative narrative
 *   - Source Quote              → verbatim excerpt (optional)
 *   - Notes                     → additional qualitative context (optional)
 *   - Related tool              → optional free-text cross-reference
 *                                  entry — only surfaced when what === 'TECH'
 *   - Related TechStack mention → optional free-text fallback when the
 *                                  catalog doesn't include the tool yet
 *
 * source_activity is NOT a form field
 * -----------------------------------
 * A signal is always created from an activity context — the wizard
 * injects source_activity into the dispatch payload via extraPayload.
 * The form does not surface a picker for it. Pain provenance is then
 * derived server-side from source_activity.contacts (m2m) and exposed
 * back to the UI through the standardised `source_context` block.
 *
 * Cross-reference rule (UI-only)
 * ------------------------------
 * The related_techstack_mention field is independent at the model level
 * (see PainSignal model docstring) but the UI nudges the rep toward
 * the structured FK: the mention TextField is hidden as soon as a
 * catalog entry is picked. The rep can clear the FK to surface the
 * mention again. The backend accepts both being set simultaneously
 * for progressive enrichment scenarios.
 *
 * Activation rule (UI-only)
 * -------------------------
 * The cross-ref section is mounted only when `what === 'TECH'`.
 * Switching `what` away from TECH clears both fields automatically
 * via a useEffect — preserves write/dispatch idempotency.
 *
 * The form does NOT call createSignal directly. It calls onAdd(payload)
 * with a ready-to-dispatch payload — the wizard injects account + source
 * at dispatch time. Activity and tech catalog objects are kept whole;
 * UUIDs are extracted by the wizard at dispatch time.
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

  // --- Optional narrative extras ---
  source_quote: Yup.string().nullable(),
  notes: Yup.string().nullable(),

  // --- Cross-reference ---
  // Both optional and not mutually exclusive — see file docstring.
  // No .when() guard on `what`: the section is unmounted entirely when
  // what !== 'TECH', and useEffect clears both fields on transition,
  // so a stale value can never reach validation.
  related_techstack_mention: Yup.string()
    .nullable()
    .max(200, "Mention must be 200 characters or fewer"),
});

// ==============================|| INITIAL VALUES ||============================== //

function buildInitialValues() {
  return {
    // Diagnosis
    summary: "",
    what: "",
    dimension: "",

    // Optional narrative extras
    source_quote: "",
    notes: "",

    // Cross-reference — TechStack
    // empty string for the mention (TextField default).
    related_techstack_mention: "",
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
 *                                     Expected keys: signal_whats, signal_dimensions
 * @param {boolean}  choicesLoading  - True while choices are loading
 * @param {string}   accountId       - Account UUID — scopes activity search
 * @param {Function} onAdd           - (payload: Object) => void
 * @param {Function} onCancel        - () => void
 * @param {Object}   initialValues   - Pre-filled values for edit mode
 * @param {string}   submitLabel     - Override submit button label (default: "Add Pain")
 */
export default function InlinePainForm({
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
      // Build payload — strip empty strings so the backend never receives
      // "" for optional text fields. Send catalog objects as-is; the
      // wizard extracts UUIDs at dispatch time. source_activity is NOT
      // emitted here — the wizard injects it via extraPayload.
      const payload = {
        // Required
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
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

      // Cross-reference — TechStack
      //
      // Always emit BOTH fields so an Edit that clears a stale value
      // explicitly reaches the backend. The UI may have unmounted the
      // section (when what !== 'TECH'), in which case the useEffect
      // above has already cleared the fields to null / "".
      //
      //                                 .id at dispatch time (or sends null)
      //   related_techstack_mention  : string ('' allowed)
      //                                 The model field is CharField with
      //                                 blank=True, so '' is a valid
      //                                 "no mention" signal — never null.
      payload.related_techstack_mention =
        values.related_techstack_mention &&
        values.related_techstack_mention.trim()
          ? values.related_techstack_mention.trim()
          : "";

      onAdd(payload);
      resetForm({ values: buildInitialValues() });
    },
  });

  // ==============================|| CLEAR CROSS-REF ON `what` CHANGE ||============================== //

  /**
   * The TechStack cross-reference is conceptually scoped to what === 'TECH'.
   * When the rep switches `what` away from TECH (e.g. re-classifies a
   * pain from TECH × QUALITY to OPS × QUALITY), we silently clear both
   * cross-ref fields so a stale FK or mention does not reach dispatch.
   *
   * The section is also unmounted in that case, so the user does not
   * see a "ghost" value being kept — the clear is purely defensive
   * against the dispatch path. The backend would accept either a TECH
   * or non-TECH pain referencing a tool (the rule is UI-only), but
   * carrying a value across a re-classification is almost always a bug.
   */
  useEffect(() => {
    if (
      formik.values.what !== "TECH" &&
      formik.values.related_techstack_mention
    ) {
      formik.setFieldValue("related_techstack_mention", "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formik.values.what]);

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
            (shared enums exposed by the backend). The model
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
            SECTION 2 — Related tool
            =================================================================
            Mounted only when what === 'TECH'. The two fields are
            mutually-soft-exclusive in the UI: a structured catalog
            pick hides the mention TextField, freeing visual space.
            The mention re-appears as soon as the FK is cleared.
            ================================================================= */}
        {formik.values.what === "TECH" && (
          <>
            <Stack spacing={1.5}>
              <SectionHeader
                index={3}
                title="Related tool (optional)"
                subtitle="If this pain involves a specific tool, name it."
              />

              <TextField
                  fullWidth
                  size="small"
                  id="pain-related-techstack-mention"
                  name="related_techstack_mention"
                  label="Related tool"
                  placeholder="e.g. Salesforce, the legacy CRM, our scheduling tool…"
                  value={formik.values.related_techstack_mention}
                  onChange={formik.handleChange}
                  onBlur={formik.handleBlur}
                  error={
                    formik.touched.related_techstack_mention &&
                    Boolean(formik.errors.related_techstack_mention)
                  }
                  helperText={
                    (formik.touched.related_techstack_mention &&
                      formik.errors.related_techstack_mention) ||
                    "Type the tool's name as it came up. Free text — it is a trace on the pain, not a link."
                  }
                  inputProps={{ maxLength: 200 }}
              />
            </Stack>

            <Divider />
          </>
        )}

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
     * Shared canonical-axis enums exposed by the backend.
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
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  /** Pre-filled values for edit mode — triggers enableReinitialize */
  initialValues: PropTypes.object,
  /** Override submit button label (default: "Add Pain") */
  submitLabel: PropTypes.string,
};
