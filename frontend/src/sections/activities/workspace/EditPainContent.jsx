// frontend/src/sections/activities/workspace/EditPainContent.jsx
//
// S3 — the Pain EDIT drawer content, on the standard chassis, a mirror of
// EditObjectiveContent: numbered SectionHeaders + InlineEditableValue
// (read → click → inline edit) on DrawerContentLayout (global Save/Cancel).
// The coque owns the "Edit pain" title (passed to openDrawer), so this content
// sets no DrawerContentLayout title. Save PATCHes via updateSignal("pain", id,
// payload); onSaved(updatedSignal) returns to the Pain detail.
//
// The ONE structural difference vs Objective: the department scope is a
// MULTI-department M2M (target_departments), NOT a single FK. Scope model:
//   - two EXCLUSIVE scope pills Company | Department — THE shared gesture
//     components/drawer/ScopeDepartmentsField.jsx (TD-271, as TechStack), with
//     the objectiveScope options. scope_level is a single value, so exactly one
//     pill is pressed;
//   - Company  → scope_level BUSINESS; the departments are MASKED (not cleared)
//     so switching back to Department restores them; the payload sends [] for
//     Company regardless (derived from scope_level);
//   - Department → the chosen departments as real pills, each with a ×, and a
//     "+ add department" picker whose options EXCLUDE the already-chosen ones.
// Selected departments are stored as {value,label} OBJECTS (the ids are extracted
// only at payload time) to avoid the int(option)/string(id) type mismatch. The
// payload never carries a target_department / target_contact FK.
//
// Theme tokens only. InlineEditableValue supports text / textarea / select.

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
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
import { OBJECTIVE_SCOPE, SCOPE_PILL_OPTIONS } from "utils/objectiveScope";
import ScopeDepartmentsField, { toDepartmentObjects } from "components/drawer/ScopeDepartmentsField";
import { SIGNAL_SUMMARY_MIN_LENGTH } from "sections/activities/signals/signalValidationRules";
import { SIGNAL_NO_NOTES, SIGNAL_NO_SOURCE_QUOTE } from "sections/activities/signals/utils/signalDisplay";

// ==============================|| HELPERS ||============================== //

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// ==============================|| VALIDATION ||============================== //
//
// Mirror of Objective for the shared fields. The DEPARTMENTS are deliberately
// NOT validated against the scope: target_departments is an independent M2M
// (never required), so there is NO .when() on scope_level here.

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(
      SIGNAL_SUMMARY_MIN_LENGTH,
      `Summary must be at least ${SIGNAL_SUMMARY_MIN_LENGTH} characters`,
    )
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),
  target_departments: Yup.array().nullable(),
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

  // Options for the department multi-select. The choices endpoint mixes
  // {value,label} and {id,name}, and — crucially — emits the id as an INTEGER
  // (backend contacts choices: {'value': dept.id}) while the signal payload
  // carries department ids as STRINGS (str(d.id)). MultiSelectFilter matches by
  // strict value identity, so BOTH sides must be the same type: stringify the
  // option value (and label) so they line up with the string form ids.
  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: String(d.value ?? d.id),
        label: String(d.label ?? d.name),
      })),
    [standardDepartments],
  );

  const initialValues = useMemo(() => {
    const departments = toDepartmentObjects(pain?.target_departments);
    // Explicit scope from the signal; default DEPARTMENT when it already carries
    // departments, else BUSINESS.
    const scope_level =
      pain?.scope_level === OBJECTIVE_SCOPE.DEPARTMENT || departments.length > 0
        ? OBJECTIVE_SCOPE.DEPARTMENT
        : OBJECTIVE_SCOPE.BUSINESS;
    return {
      summary: pain?.summary || "",
      what: pain?.what || "",
      dimension: pain?.dimension || "",
      scope_level,
      // Stored as {value,label} objects (ids extracted only at payload time).
      target_departments: departments,
      notes: pain?.notes || "",
      related_techstack_mention: pain?.related_techstack_mention || "",
      source_quote: pain?.source_quote || "",
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pain?.id]);

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only Pain's writable fields (PainSignalUpdateSerializer). NO FK fields
      // (target_department / target_contact do not exist on Pain).
      //
      // scope_level is EXPLICIT (the chosen pill). Extract the department ids from
      // the stored {value,label} objects; Company (BUSINESS) always sends [] so an
      // edit that switches to company-wide replaces the set on the backend.
      const isDepartment = values.scope_level === OBJECTIVE_SCOPE.DEPARTMENT;
      const departmentIds = isDepartment
        ? (values.target_departments || []).map((d) => d.value)
        : [];
      const payload = {
        summary: values.summary.trim(),
        what: values.what,
        dimension: values.dimension,
        scope_level: values.scope_level,
        target_departments: departmentIds,
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
            scope_level: payload.scope_level,
            scope_level_display:
              resolveLabel(scopeLevelOptions, payload.scope_level) ?? pain?.scope_level_display,
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

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => (onCancel ? onCancel() : closeDrawer())}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
      dirty={formik.dirty && !formik.isSubmitting}
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

        {/* ---- SECTION 2 — Which scope? (explicit Company | Department) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Which scope?"
            subtitle="Company-wide, or one or more departments."
          />

          {/* The shared exclusive-scope gesture (components/drawer/ScopeDepartmentsField.jsx,
              as EditTechStackContent — TD-271): Company | Department pills; the
              department scope shows the chosen departments as pills + "+ add
              department". Company MASKS the departments (not cleared); the payload
              sends [] for it. NEVER required. */}
          <ScopeDepartmentsField
            scopeOptions={SCOPE_PILL_OPTIONS}
            scope={values.scope_level}
            onScopeChange={set("scope_level")}
            departmentScope={OBJECTIVE_SCOPE.DEPARTMENT}
            departments={values.target_departments}
            onDepartmentsChange={set("target_departments")}
            departmentOptions={departmentOptions}
            testIdPrefix="pain"
          />
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
            placeholder={SIGNAL_NO_NOTES}
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
            placeholder={SIGNAL_NO_SOURCE_QUOTE}
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
  /** Account the pain belongs to — passed by the caller, currently unused. */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes (legacy). */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes (legacy). */
  onCancel: PropTypes.func,
};
