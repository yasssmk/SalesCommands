// frontend/src/sections/activities/workspace/EditObjectiveContent.jsx
//
// SIG-5d / SIG-5d-fix — the Objective EDIT drawer content. It reproduces the
// ORIGINAL InlineObjectiveForm FAITHFULLY (same 3 sections + subtitles, same MUI
// TextField/Select fields, the "Domain × Dimension" recap, the same Yup
// validation) — ported onto DrawerContentLayout (global Save/Cancel). Only two
// things change vs the original:
//   (a) the scope block → the shared ObjectiveScopePill (Company / Department);
//       the DEPARTMENT department picker is the ORIGINAL MUI Select, rendered
//       here next to the pill (not an ad-hoc widget).
//   (b) source_quote is added as an editable field (free text; the transcript
//       block picker is deferred to the post-deploy roadmap).
//
// Save PATCHes every field via the existing generic updateSignal("objective",
// id, patch), then snackbars + closes the coque + lets the caller revalidate.
// The old InlineObjectiveForm / SignalEditDrawer stay on disk (dead for
// Objective — traced, not deleted). Theme tokens; the only literal px are copied
// verbatim from the original SectionHeader chip to stay pixel-faithful.

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateSignal, useGetSignalChoices } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import ObjectiveScopePill from "components/signals/ObjectiveScopePill";
import { OBJECTIVE_SCOPE } from "utils/objectiveScope";

// ==============================|| HELPERS (reproduced from InlineObjectiveForm) ||=========== //

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

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

// ==============================|| VALIDATION (preserved from InlineObjectiveForm) ||=========== //

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),
  // DEPARTMENT scope requires a department; every other scope leaves it nullable
  // (so the error NEVER shows in Company). Mirror of the original + backend clean().
  target_department: Yup.string()
    .nullable()
    .when("scope_level", {
      is: OBJECTIVE_SCOPE.DEPARTMENT,
      then: (schema) => schema.required("Department objectives require a target department"),
      otherwise: (schema) => schema.nullable(),
    }),
  success_criteria: Yup.string().nullable(),
  target_date: Yup.string().nullable(),
  notes: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// Normalise a target FK that may arrive as a compact {id,name} object (detail
// serializer) or a bare id — to the id string the form/patch use.
function fkId(v) {
  if (v == null) return "";
  return typeof v === "object" ? v.id ?? "" : v;
}

// ==============================|| EDIT OBJECTIVE CONTENT ||============================== //

export default function EditObjectiveContent({ objective, accountId, onSaved }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices, choicesLoading } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  const whatOptions = choices?.signal_whats ?? [];
  const dimensionOptions = choices?.signal_dimensions ?? [];
  const departmentOptions = standardDepartments || [];

  const initialValues = useMemo(
    () => ({
      summary: objective?.summary || "",
      what: objective?.what || "",
      dimension: objective?.dimension || "",
      scope_level: objective?.scope_level || OBJECTIVE_SCOPE.BUSINESS,
      target_department: fkId(objective?.target_department),
      target_contact: fkId(objective?.target_contact),
      success_criteria: objective?.success_criteria || "",
      target_date: objective?.target_date || "",
      notes: objective?.notes || "",
      source_quote: objective?.source_quote || "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [objective?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      const payload = {
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
        scope_level: values.scope_level,
        target_department: values.target_department || null,
        target_contact: values.target_contact || null,
        success_criteria: values.success_criteria || "",
        target_date: values.target_date || null,
        notes: values.notes || "",
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("objective", objective.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Objective updated");
        onSaved?.();
        closeDrawer();
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setSubmitting(false);
      }
    },
  });

  // Live "Domain × Dimension" recap (reproduced from the original).
  const canonicalPreview = useMemo(() => {
    if (!formik.values.what || !formik.values.dimension) return null;
    return `objective:${formik.values.what}:${formik.values.dimension}`;
  }, [formik.values.what, formik.values.dimension]);

  const axisPreview = useMemo(() => {
    const whatLabel = resolveLabel(whatOptions, formik.values.what);
    const dimensionLabel = resolveLabel(dimensionOptions, formik.values.dimension);
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [whatOptions, dimensionOptions, formik.values.what, formik.values.dimension]);

  // The scope pill raises a draft patch of scope fields — apply each to the draft.
  const applyScopePatch = (patch) => {
    Object.entries(patch).forEach(([k, v]) => formik.setFieldValue(k, v));
  };

  const isDepartment = formik.values.scope_level === OBJECTIVE_SCOPE.DEPARTMENT;

  return (
    <DrawerContentLayout
      title="Edit objective"
      onSave={formik.handleSubmit}
      onCancel={() => closeDrawer()}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={2.5}>
        {/* ---- SECTION 1 — What's the goal? ---- */}
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
                {whatOptions.map((opt) => (
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
              error={formik.touched.dimension && Boolean(formik.errors.dimension)}
              disabled={choicesLoading}
            >
              <InputLabel id="objective-dimension-label">Dimension *</InputLabel>
              <Select
                labelId="objective-dimension-label"
                id="objective-dimension"
                name="dimension"
                value={formik.values.dimension}
                onChange={formik.handleChange}
                onBlur={formik.handleBlur}
                label="Dimension *"
              >
                {dimensionOptions.map((opt) => (
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
                borderLeftStyle: "solid",
                borderLeftWidth: 3,
                borderLeftColor: "info.main",
              }}
            >
              <Typography variant="caption" color="text.secondary">
                This is a{" "}
                <Box component="span" sx={{ fontWeight: 600, color: "text.primary" }}>
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

        {/* ---- SECTION 2 — Who owns it? (scope → pill + original dept Select) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Who owns it?"
            subtitle="Pick the organisational scope driving this goal."
          />

          <ObjectiveScopePill
            value={{ scope_level: formik.values.scope_level }}
            onChange={applyScopePatch}
          />

          {/* DEPARTMENT → target_department: the ORIGINAL MUI Select. */}
          {isDepartment && (
            <FormControl
              fullWidth
              size="small"
              error={
                formik.touched.target_department &&
                Boolean(formik.errors.target_department)
              }
            >
              <InputLabel id="objective-target-dept-label">Target Department *</InputLabel>
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
              {formik.touched.target_department && formik.errors.target_department && (
                <FormHelperText>{formik.errors.target_department}</FormHelperText>
              )}
            </FormControl>
          )}
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — How is success measured? ---- */}
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
            error={formik.touched.success_criteria && Boolean(formik.errors.success_criteria)}
            helperText={formik.touched.success_criteria && formik.errors.success_criteria}
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
            inputProps={{ "data-testid": "objective-target-date" }}
            error={formik.touched.target_date && Boolean(formik.errors.target_date)}
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

        {/* ---- Source quote (added, editable free text) ---- */}
        <TextField
          fullWidth
          size="small"
          id="objective-source-quote"
          name="source_quote"
          label="Source Quote"
          placeholder="The transcript excerpt that supports this objective…"
          multiline
          minRows={2}
          value={formik.values.source_quote}
          onChange={formik.handleChange}
          onBlur={formik.handleBlur}
        />
      </Stack>
    </DrawerContentLayout>
  );
}

EditObjectiveContent.propTypes = {
  /** The objective signal to edit (the full detail payload). */
  objective: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string,
    what: PropTypes.string,
    dimension: PropTypes.string,
    scope_level: PropTypes.string,
    target_department: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    target_contact: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
    success_criteria: PropTypes.string,
    target_date: PropTypes.string,
    notes: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account the objective belongs to (reserved for future scoped pickers). */
  accountId: PropTypes.string,
  /** Fired after a successful save (before the coque closes) — caller revalidates. */
  onSaved: PropTypes.func,
};
