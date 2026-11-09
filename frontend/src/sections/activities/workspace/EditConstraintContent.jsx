// frontend/src/sections/activities/workspace/EditConstraintContent.jsx
//
// S3 — the Constraint EDIT drawer content, on the standard chassis, a mirror of
// EditImpactContent: numbered SectionHeaders + InlineEditableValue on
// DrawerContentLayout (global Save/Cancel). The coque owns the "Edit constraint"
// title. Save PATCHes via updateSignal("constraints", id, payload) — front type
// key is PLURAL "constraints"; onSaved(updatedSignal) returns to the detail.
//
// Deltas vs Pain/Impact:
//   - Fields: nature (select, REQUIRED) + rigidity (select, OPTIONAL & clearable
//     with an empty "—" option, backend allow_blank since S1a) + summary + notes.
//     NO what/dimension (legacy), NO metric/impact_type.
//   - SCOPE: Constraint has NO scope_level. The Company/Department pills are a
//     PURE UI AFFORDANCE (kept in the form's local `scope_level` field to drive
//     show/hide of the departments — THE shared ScopeDepartmentsField gesture,
//     TD-271) and are NEVER persisted. The
//     payload emits ONLY target_departments (ids when Department, [] when
//     Company). No scope_level, no FK.
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

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateSignal, useGetSignalChoices } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SectionHeader from "components/display/SectionHeader";
import InlineEditableValue from "components/drawer/InlineEditableValue";
// Reuse the SHARED scope constants + pill colour tokens (objectiveScope is NOT
// modified). For Constraint the pills are a pure UI affordance (no scope_level).
import { OBJECTIVE_SCOPE, SCOPE_PILL_OPTIONS } from "utils/objectiveScope";
import ScopeDepartmentsField, { toDepartmentObjects } from "components/drawer/ScopeDepartmentsField";
import { SIGNAL_SUMMARY_MIN_LENGTH } from "sections/activities/signals/signalValidationRules";
import { withEmptyOption } from "utils/selectOptions";
import { SIGNAL_NO_NOTES, SIGNAL_NO_SOURCE_QUOTE } from "sections/activities/signals/utils/signalDisplay";

// ==============================|| HELPERS ||============================== //

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// ==============================|| VALIDATION ||============================== //
//
// nature REQUIRED, summary required. rigidity OPTIONAL (clearable). departments
// are an independent M2M (never required) — no .when() on the scope affordance.

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(
      SIGNAL_SUMMARY_MIN_LENGTH,
      `Summary must be at least ${SIGNAL_SUMMARY_MIN_LENGTH} characters`,
    )
    .required("Summary is required"),
  nature: Yup.string().required("Nature is required"),
  rigidity: Yup.string().nullable(),
  target_departments: Yup.array().nullable(),
  notes: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT CONSTRAINT CONTENT ||============================== //

export default function EditConstraintContent({ constraint, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices, choicesLoading } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  // nature is REQUIRED → no empty option.
  const natureOptions = choices?.constraint_natures ?? [];
  // rigidity is OPTIONAL & clearable → prepend an empty "—" option (mirror of
  // Impact's human_impact) so a rep can clear it (backend allow_blank, S1a).
  const rigidityOptions = useMemo(
    () => withEmptyOption(choices?.rigidities),
    [choices?.rigidities],
  );

  // Department multi-select options — stringified (choices endpoint emits int
  // ids, the signal payload strings). Same anti-mismatch stance as Pain/Impact.
  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: String(d.value ?? d.id),
        label: String(d.label ?? d.name),
      })),
    [standardDepartments],
  );

  const initialValues = useMemo(() => {
    const departments = toDepartmentObjects(constraint?.target_departments);
    // scope_level here is a PURE UI AFFORDANCE (Constraint has no scope_level
    // field): DEPARTMENT when it already carries departments, else BUSINESS.
    const scope_level =
      departments.length > 0 ? OBJECTIVE_SCOPE.DEPARTMENT : OBJECTIVE_SCOPE.BUSINESS;
    return {
      summary: constraint?.summary || "",
      // Raw values (not *_display).
      nature: constraint?.nature || "",
      rigidity: constraint?.rigidity || "",
      scope_level,
      // Stored as {value,label} objects (ids extracted only at payload time).
      target_departments: departments,
      notes: constraint?.notes || "",
      source_quote: constraint?.source_quote || "",
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [constraint?.id]);

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only Constraint's writable fields (ConstraintSignalUpdateSerializer):
      // nature, summary, rigidity, notes, target_departments. NO scope_level
      // (the field does not exist on Constraint — the pill is UI-only), NO FK,
      // NO what/dimension (legacy). rigidity "" is a real clearing (allow_blank).
      const isDepartment = values.scope_level === OBJECTIVE_SCOPE.DEPARTMENT;
      const departmentIds = isDepartment
        ? (values.target_departments || []).map((d) => d.value)
        : [];
      const payload = {
        summary: values.summary.trim(),
        nature: values.nature,
        rigidity: values.rigidity ?? "",
        notes: values.notes || "",
        target_departments: departmentIds,
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("constraints", constraint.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Constraint updated");
        if (onSaved) {
          const updatedSignal = {
            ...constraint,
            summary: payload.summary,
            nature: payload.nature,
            nature_display: resolveLabel(natureOptions, payload.nature) ?? constraint?.nature_display,
            rigidity: payload.rigidity,
            rigidity_display: payload.rigidity
              ? resolveLabel(rigidityOptions, payload.rigidity)
              : null,
            notes: payload.notes,
            target_departments: payload.target_departments.map((id) => ({
              id,
              name: resolveLabel(departmentOptions, id),
            })),
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

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => (onCancel ? onCancel() : closeDrawer())}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={2.5}>
        {/* ---- SECTION 1 — What's the constraint? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the constraint?"
            subtitle="Describe the constraint and pick its nature."
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
            name="nature"
            label="Nature"
            type="select"
            options={natureOptions}
            value={values.nature}
            onChange={set("nature")}
            placeholder="Required"
            disabled={choicesLoading}
            error={Boolean(errors.nature)}
            helperText={errors.nature}
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Rigidity (optional, clearable) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Rigidity"
            subtitle="Firm (non-negotiable) or flexible — optional."
          />
          <InlineEditableValue
            name="rigidity"
            label="Rigidity"
            type="select"
            options={rigidityOptions}
            value={values.rigidity}
            onChange={set("rigidity")}
            placeholder="No rigidity"
            disabled={choicesLoading}
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — Which scope? (UI affordance — not persisted) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
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
            testIdPrefix="constraint"
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 4 — Notes (optional) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader index={4} title="Notes" subtitle="Optional — additional context." />
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

        {/* ---- SECTION 5 — Source quote ---- */}
        <Stack spacing={1.5}>
          <SectionHeader index={5} title="Source quote" subtitle="Where does this signal come from" />
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

EditConstraintContent.propTypes = {
  /** The constraint signal to edit (the full detail payload). */
  constraint: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string,
    nature: PropTypes.string,
    rigidity: PropTypes.string,
    target_departments: PropTypes.array,
    notes: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account the constraint belongs to — passed by the caller, currently unused. */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes (legacy). */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes (legacy). */
  onCancel: PropTypes.func,
};
