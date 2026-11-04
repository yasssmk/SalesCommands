// frontend/src/sections/activities/workspace/EditImpactContent.jsx
//
// S3 — the Impact EDIT drawer content, on the standard chassis, a mirror of
// EditPainContent: numbered SectionHeaders + InlineEditableValue (read →
// click → inline edit) on DrawerContentLayout (global Save/Cancel). The
// coque owns the "Edit impact" title (passed to openDrawer), so this content
// sets no DrawerContentLayout title. Save PATCHes via updateSignal("impact",
// id, payload); onSaved(updatedSignal) returns to the Impact detail.
//
// Scope model is IDENTICAL to Pain (Impact scope == Pain scope): two EXCLUSIVE
// scope pills Company | Department (THE shared ScopeDepartmentsField gesture,
// TD-271, with the objectiveScope options),
// Company → scope_level BUSINESS with departments MASKED (not cleared), Department
// → a "+ add department" grouped multi-select whose options EXCLUDE the already
// chosen, chosen departments as real pills each with a ×. Departments are stored
// as {value,label} OBJECTS (ids extracted only at payload time) to avoid the
// int(option)/string(id) type mismatch. The payload never carries a FK.
//
// Deltas vs Pain: NO notes, NO related_techstack_mention (absent on Impact).
// Adds the Metrics section — impact_type (select, OPTIONAL & CLEARABLE since S5b
// Voie B; the empty "—" option sends impact_type: "" to clear it, migration 0043
// + serializers allow_blank) and metric_text (textarea, optional, labelled
// "Describe the impact"; the help is its placeholder, read AND edit). human_impact is NOT
// edited on this surface and is OMITTED from the payload (non-destructive: the
// stored value is left untouched).
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
import { withEmptyOption } from "utils/selectOptions";
import { SIGNAL_NO_SOURCE_QUOTE } from "sections/activities/signals/utils/signalDisplay";

// ==============================|| HELPERS ||============================== //

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// ==============================|| VALIDATION ||============================== //
//
// Mirror of Pain for the shared fields. impact_type / metric_text are both
// OPTIONAL (S3-fix). The DEPARTMENTS are deliberately NOT validated
// against the scope: target_departments is an independent M2M (never required),
// so there is NO .when() on scope_level here.

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
  impact_type: Yup.string().nullable(),
  metric_text: Yup.string().nullable(),
  target_departments: Yup.array().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT IMPACT CONTENT ||============================== //

export default function EditImpactContent({ impact, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices, choicesLoading } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  const whatOptions = choices?.signal_whats ?? [];
  const dimensionOptions = choices?.signal_dimensions ?? [];
  const scopeLevelOptions = choices?.scope_levels ?? [];
  // impact_type is optional & clearable (Voie B) → prepend an empty option so a
  // rep can clear a mis-categorised value.
  const impactTypeOptions = useMemo(
    () => withEmptyOption(choices?.impact_types),
    [choices?.impact_types],
  );

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
    const departments = toDepartmentObjects(impact?.target_departments);
    // Explicit scope from the signal; default DEPARTMENT when it already carries
    // departments, else BUSINESS.
    const scope_level =
      impact?.scope_level === OBJECTIVE_SCOPE.DEPARTMENT || departments.length > 0
        ? OBJECTIVE_SCOPE.DEPARTMENT
        : OBJECTIVE_SCOPE.BUSINESS;
    return {
      summary: impact?.summary || "",
      what: impact?.what || "",
      dimension: impact?.dimension || "",
      scope_level,
      // Stored as {value,label} objects (ids extracted only at payload time).
      target_departments: departments,
      // Metrics — raw values (not *_display).
      impact_type: impact?.impact_type || "",
      metric_text: impact?.metric_text || "",
      source_quote: impact?.source_quote || "",
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [impact?.id]);

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only Impact's writable fields (ImpactSignalUpdateSerializer). NO FK
      // fields (target_department / target_contact do not exist on Impact); NO
      // notes / related_techstack_mention (absent on Impact). human_impact is
      // deliberately OMITTED (not sent as "") so the stored value is untouched.
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
        metric_text: values.metric_text || "",
        source_quote: values.source_quote || "",
      };
      // impact_type is OPTIONAL & CLEARABLE (Voie B, migration 0043 + serializers
      // allow_blank). ALWAYS send it — an empty "" is a real clearing (the backend
      // accepts blank), so a rep can fix a mis-categorised impact_type.
      payload.impact_type = values.impact_type ?? "";
      try {
        const result = await updateSignal("impact", impact.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Impact updated");
        // Return to the detail with the updated signal (display-friendly merge:
        // re-resolve the axis + scope + metrics labels + rebuild the departments
        // [{id,name}] list) so the read drawer renders the new values immediately.
        if (onSaved) {
          const updatedSignal = {
            ...impact,
            summary: payload.summary,
            what: values.what,
            dimension: values.dimension,
            what_display: resolveLabel(whatOptions, values.what) ?? impact?.what_display,
            dimension_display:
              resolveLabel(dimensionOptions, values.dimension) ?? impact?.dimension_display,
            scope_level: payload.scope_level,
            scope_level_display:
              resolveLabel(scopeLevelOptions, payload.scope_level) ?? impact?.scope_level_display,
            target_departments: payload.target_departments.map((id) => ({
              id,
              name: resolveLabel(departmentOptions, id),
            })),
            // Voie B: impact_type is sent verbatim (incl. "") — reflect the real
            // saved value so an empty impact_type renders "No metric defined" on
            // the detail (no fallback to the pre-edit value).
            impact_type: payload.impact_type,
            impact_type_display: payload.impact_type
              ? resolveLabel(impactTypeOptions, payload.impact_type) ?? impact?.impact_type_display
              : null,
            metric_text: payload.metric_text,
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

  // Live "Domain × Dimension" recap (guidance, mirror of Pain).
  const canonicalPreview = useMemo(() => {
    if (!values.what || !values.dimension) return null;
    return `impact:${values.what}:${values.dimension}`;
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
    >
      <Stack spacing={2.5}>
        {/* ---- SECTION 1 — What's the impact? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the impact?"
            subtitle="Describe the impact and pick its canonical axes."
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
                impact
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
            testIdPrefix="impact"
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — Metrics ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="Metrics"
            subtitle="The type of impact and its concrete consequences."
          />
          <InlineEditableValue
            name="impact_type"
            label="Impact type"
            type="select"
            options={impactTypeOptions}
            value={values.impact_type}
            onChange={set("impact_type")}
            placeholder="No impact type"
            disabled={choicesLoading}
            error={Boolean(errors.impact_type)}
            helperText={errors.impact_type}
          />
          {/* metric_text — free description. The guidance is the placeholder in
              BOTH modes: read (empty, closed) and edit (the open textarea). */}
          <InlineEditableValue
            name="metric_text"
            label="Describe the impact"
            type="textarea"
            value={values.metric_text}
            onChange={set("metric_text")}
            placeholder="Be specific about the consequences, with numbers whenever possible"
            inputPlaceholder="Be specific about the consequences, with numbers whenever possible"
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

EditImpactContent.propTypes = {
  /** The impact signal to edit (the full detail payload). */
  impact: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string,
    what: PropTypes.string,
    dimension: PropTypes.string,
    scope_level: PropTypes.string,
    target_departments: PropTypes.array,
    impact_type: PropTypes.string,
    metric_text: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account the impact belongs to — passed by the caller, currently unused. */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes (legacy). */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes (legacy). */
  onCancel: PropTypes.func,
};
