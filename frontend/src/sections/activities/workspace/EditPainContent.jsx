// frontend/src/sections/activities/workspace/EditPainContent.jsx
//
// S3 — the Pain EDIT drawer content, on the standard chassis, a mirror of
// EditObjectiveContent: numbered SectionHeaders + InlineEditableValue
// (read → double-click → inline edit) on DrawerContentLayout (global Save/Cancel).
// The coque owns the "Edit pain" title (passed to openDrawer), so this content
// sets no DrawerContentLayout title. Save PATCHes via updateSignal("pain", id,
// payload); onSaved(updatedSignal) returns to the Pain detail.
//
// The ONE structural difference vs Objective: the department scope is a
// MULTI-department M2M (target_departments, a list of ids), NOT a single FK. So:
//   - the ObjectiveScopePill drives ONLY scope_level (Company / Department) — its
//     FK emissions (target_department / target_contact) are ignored (those fields
//     do not exist on Pain);
//   - the department picker is the TechStack-style Select-multiple, ALWAYS present
//     and NEVER required (target_departments is independent of scope_level, like
//     TechStackSignal.usage_departments). No .when() conditional on the scope.
//
// Theme tokens only. InlineEditableValue supports text / textarea / select.

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
import Typography from "@mui/material/Typography";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateSignal, useGetSignalChoices } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SectionHeader from "components/display/SectionHeader";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import ObjectiveScopePill from "components/signals/ObjectiveScopePill";
import { OBJECTIVE_SCOPE } from "utils/objectiveScope";

// ==============================|| HELPERS ||============================== //

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// Normalise the detail payload's target_departments ([{id,name}] | [id]) to the
// list of id strings the form + PATCH use.
function toDepartmentIds(list) {
  if (!Array.isArray(list)) return [];
  return list.map((d) => String(typeof d === "object" ? d?.id : d)).filter(Boolean);
}

// ==============================|| VALIDATION ||============================== //
//
// Mirror of Objective for the shared fields. The DEPARTMENTS are deliberately
// NOT validated against the scope: target_departments is an independent M2M
// (never required), so there is NO .when() on scope_level here.

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),
  target_departments: Yup.array().of(Yup.string()).nullable(),
  notes: Yup.string().nullable(),
  related_techstack_mention: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT PAIN CONTENT ||============================== //

export default function EditPainContent({ pain, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices, choicesLoading } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  const whatOptions = choices?.signal_whats ?? [];
  const dimensionOptions = choices?.signal_dimensions ?? [];
  const scopeLevelOptions = choices?.scope_levels ?? [];

  // Same source + normalisation as InlineTechStackForm's usage_departments: the
  // choices endpoint mixes {value,label} and {id,name}, so map to {value,label}.
  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: d.value ?? d.id,
        label: d.label ?? d.name,
      })),
    [standardDepartments],
  );

  const initialValues = useMemo(
    () => ({
      summary: pain?.summary || "",
      what: pain?.what || "",
      dimension: pain?.dimension || "",
      scope_level: pain?.scope_level || OBJECTIVE_SCOPE.BUSINESS,
      target_departments: toDepartmentIds(pain?.target_departments),
      notes: pain?.notes || "",
      related_techstack_mention: pain?.related_techstack_mention || "",
      source_quote: pain?.source_quote || "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [pain?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only Pain's writable fields (PainSignalUpdateSerializer). NO FK fields
      // (target_department / target_contact do not exist on Pain). Always emit
      // target_departments so an edit that clears every department replaces the
      // set on the backend (mirror of TechStack usage_departments).
      const payload = {
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
        scope_level: values.scope_level,
        target_departments: Array.isArray(values.target_departments)
          ? values.target_departments
          : [],
        notes: values.notes || "",
        related_techstack_mention: values.related_techstack_mention || "",
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("pain", pain.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Pain updated");
        // Return to the detail with the updated signal (display-friendly merge:
        // re-resolve the axis + scope labels + rebuild the departments [{id,name}]
        // list) so the read drawer renders the new values immediately.
        if (onSaved) {
          const updatedSignal = {
            ...pain,
            summary: payload.summary,
            what: values.what,
            dimension: values.dimension,
            what_display: resolveLabel(whatOptions, values.what) ?? pain?.what_display,
            dimension_display:
              resolveLabel(dimensionOptions, values.dimension) ?? pain?.dimension_display,
            scope_level: values.scope_level,
            scope_level_display:
              resolveLabel(scopeLevelOptions, values.scope_level) ?? pain?.scope_level_display,
            target_departments: payload.target_departments.map((id) => ({
              id,
              name: resolveLabel(departmentOptions, id),
            })),
            notes: payload.notes,
            related_techstack_mention: payload.related_techstack_mention,
            source_quote: payload.source_quote,
          };
          onSaved(updatedSignal);
        } else {
          closeDrawer();
        }
      } catch (err) {
        displayErrorSnackbar(err);
      } finally {
        setSubmitting(false);
      }
    },
  });

  const { values, errors, setFieldValue } = formik;
  const set = (name) => (v) => setFieldValue(name, v);

  // Live "Domain × Dimension" recap (guidance, mirror of Objective).
  const canonicalPreview = useMemo(() => {
    if (!values.what || !values.dimension) return null;
    return `pain:${values.what}:${values.dimension}`;
  }, [values.what, values.dimension]);

  const axisPreview = useMemo(() => {
    const whatLabel = resolveLabel(whatOptions, values.what);
    const dimensionLabel = resolveLabel(dimensionOptions, values.dimension);
    if (!whatLabel || !dimensionLabel) return null;
    return `${whatLabel} × ${dimensionLabel}`;
  }, [whatOptions, dimensionOptions, values.what, values.dimension]);

  // The scope pill raises a draft patch; on Pain we consume ONLY scope_level from
  // it (its FK emissions are for Objective and are intentionally ignored).
  const applyScope = (patch) => {
    if (patch?.scope_level != null) setFieldValue("scope_level", patch.scope_level);
  };

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => (onCancel ? onCancel() : closeDrawer())}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={2.5}>
        {/* ---- SECTION 1 — What's the pain? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the pain?"
            subtitle="Describe the pain and pick its canonical axes."
          />

          <InlineEditableValue
            name="summary"
            label="Summary"
            type="textarea"
            value={values.summary}
            onChange={set("summary")}
            placeholder="Required"
            error={Boolean(errors.summary)}
            helperText={errors.summary}
          />
          <InlineEditableValue
            name="what"
            label="Domain"
            type="select"
            options={whatOptions}
            value={values.what}
            onChange={set("what")}
            placeholder="No domain"
            disabled={choicesLoading}
            error={Boolean(errors.what)}
            helperText={errors.what}
          />
          <InlineEditableValue
            name="dimension"
            label="Dimension"
            type="select"
            options={dimensionOptions}
            value={values.dimension}
            onChange={set("dimension")}
            placeholder="No dimension"
            disabled={choicesLoading}
            error={Boolean(errors.dimension)}
            helperText={errors.dimension}
          />

          {/* Live canonical preview */}
          {axisPreview && (
            <Box
              sx={{
                px: 1.5,
                py: 1,
                bgcolor: "action.hover",
                borderRadius: 1,
              }}
            >
              <Typography variant="caption" color="text.secondary">
                This is a{" "}
                <Box component="span" sx={{ fontWeight: 600, color: "text.primary" }}>
                  {axisPreview}
                </Box>{" "}
                pain
              </Typography>
              <Typography
                variant="caption"
                color="text.disabled"
                display="block"
                sx={{ fontFamily: "monospace", mt: 0.25 }}
              >
                canonical_key: {canonicalPreview}
              </Typography>
            </Box>
          )}
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Which scope? (scope_level pill + M2M departments) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Which scope?"
            subtitle="Pick the organisational scope, and the departments this pain concerns."
          />

          {/* The pill drives ONLY scope_level (Company / Department). */}
          <ObjectiveScopePill
            value={{ scope_level: values.scope_level }}
            onChange={applyScope}
          />

          {/* Departments — ALWAYS present, NEVER required (independent M2M). The
              TechStack usage_departments pattern: Select multiple + chips. */}
          <Box data-testid="pain-departments-field" sx={{ pt: 1 }}>
            <FormControl
              fullWidth
              size="small"
              error={formik.touched.target_departments && Boolean(errors.target_departments)}
            >
              <InputLabel id="pain-target-depts-label">Department(s)</InputLabel>
              <Select
                multiple
                labelId="pain-target-depts-label"
                id="pain-target-departments"
                name="target_departments"
                value={values.target_departments}
                onChange={(e) => setFieldValue("target_departments", e.target.value)}
                onBlur={formik.handleBlur}
                label="Department(s)"
                renderValue={(selected) => (
                  <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                    {selected.map((val) => {
                      const opt = departmentOptions.find((o) => o.value === val);
                      return <Chip key={val} size="small" label={opt ? opt.label : val} />;
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
              {formik.touched.target_departments && errors.target_departments && (
                <FormHelperText>{errors.target_departments}</FormHelperText>
              )}
            </FormControl>
          </Box>
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — Related tool + Notes (optional) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="Related tool"
            subtitle="Optional — a tool involved in this pain, and any extra notes."
          />
          <InlineEditableValue
            name="related_techstack_mention"
            label="Related tool"
            type="text"
            value={values.related_techstack_mention}
            onChange={set("related_techstack_mention")}
            placeholder="No related tool"
          />
          <InlineEditableValue
            name="notes"
            label="Notes"
            type="textarea"
            value={values.notes}
            onChange={set("notes")}
            placeholder="No notes"
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 4 — Source quote ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={4}
            title="Source quote"
            subtitle="Where does this signal come from"
          />
          <InlineEditableValue
            name="source_quote"
            label="Quote"
            type="textarea"
            value={values.source_quote}
            onChange={set("source_quote")}
            placeholder="No source quote"
          />
        </Stack>
      </Stack>
    </DrawerContentLayout>
  );
}

EditPainContent.propTypes = {
  /** The pain signal to edit (the full detail payload). */
  pain: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string,
    what: PropTypes.string,
    dimension: PropTypes.string,
    scope_level: PropTypes.string,
    target_departments: PropTypes.array,
    notes: PropTypes.string,
    related_techstack_mention: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account the pain belongs to (reserved for future scoped pickers). */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes (legacy). */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes (legacy). */
  onCancel: PropTypes.func,
};
