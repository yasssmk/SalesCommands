// frontend/src/sections/activities/workspace/EditTechStackContent.jsx
//
// Sprint TechStack T2b — the TechStack EDIT drawer content on the standard
// chassis (Activity surface), same 5 sections and order as the T1 detail
// (TechStackDetailView): Technology → Usage → Lifecycle → Notes → Source.
// Pattern "value → 1 click → editor" everywhere (InlineEditableValue, its
// renderEditor for the year / boolean, the shared InlineDateField for dates) on
// DrawerContentLayout (global Save / Cancel). The coque owns the
// "Edit tech stack" title. Save PATCHes via updateSignal("tech-stack", id,
// payload); onSaved(updatedSignal) returns to the detail.
//
//   §1 Technology — tech_name (required, never blank).
//   §2 Usage — the shared exclusive-scope gesture (ScopeDepartmentsField) in its
//      deselectable mode: 2 pills Department · Company (labels from the
//      choices); NO pill pressed = UNKNOWN (not said) — a click on the active
//      pill deselects it;
//      Department → department pills + "+ add department" (options stringified,
//      TD-241); Company / no pill (Unknown) mask the departments (not cleared)
//      and send [].
//      Department ⇒ at least one department (same rule as the backend, T0).
//   §3 Lifecycle — start year (bounds below, erasable → null), renewal date,
//      cost, discontinued as a Switch shown directly (+ its date, required when
//      on, cleared when off). Empty values read "Unknown" (not said).
//   §4 Notes. §5 Source quote.
// The payload NEVER carries is_to_replace (kept in the DB, out of the UI).
//
// Theme tokens only.

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormHelperText from "@mui/material/FormHelperText";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateSignal, useGetSignalChoices } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SectionHeader from "components/display/SectionHeader";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import InlineDateField from "components/drawer/InlineDateField";
import ScopeDepartmentsField, { toDepartmentObjects } from "components/drawer/ScopeDepartmentsField";
import {
  USAGE_SCOPE,
  getUsageScopeLabel,
} from "sections/activities/signals/utils/signalDisplay";

// ==============================|| CONSTANTS ||============================== //

// Bounds of usage_start_year — defensive against typos (same values as the
// wizard's InlineTechStackForm).
const MIN_USAGE_YEAR = 1980;
const MAX_USAGE_YEAR = new Date().getFullYear() + 1;

// ==============================|| VALIDATION ||============================== //

const validationSchema = Yup.object({
  tech_name: Yup.string().trim().required("Tool name is required"),
  usage_scope: Yup.string().required(),
  // Department ⇒ at least one department (backend T0 rule, mirrored here so the
  // save is blocked with a message instead of a 400).
  usage_departments: Yup.array().when("usage_scope", {
    is: USAGE_SCOPE.DEPARTMENT,
    then: (schema) => schema.min(1, "Pick at least one department"),
    otherwise: (schema) => schema,
  }),
  usage_start_year: Yup.mixed().test(
    "usage-year",
    `Year must be between ${MIN_USAGE_YEAR} and ${MAX_USAGE_YEAR}`,
    (v) => {
      if (v === "" || v === null || v === undefined) return true;
      const n = Number(v);
      return Number.isInteger(n) && n >= MIN_USAGE_YEAR && n <= MAX_USAGE_YEAR;
    },
  ),
  renewal_date: Yup.string().nullable(),
  cost_description: Yup.string().nullable(),
  is_discontinued: Yup.boolean(),
  discontinued_date: Yup.string()
    .nullable()
    .when("is_discontinued", {
      is: true,
      then: (schema) => schema.required("Discontinued date is required"),
      otherwise: (schema) => schema,
    }),
  notes: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT TECHSTACK CONTENT ||============================== //

export default function EditTechStackContent({ techstack, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  // The usage pills, in the backend order, labels from the choices — WITHOUT
  // UNKNOWN: "not said" is represented by NO pill pressed.
  const scopeOptions = useMemo(
    () =>
      (choices?.usage_scopes ?? [])
        .filter((o) => o.value !== USAGE_SCOPE.UNKNOWN)
        .map((o) => ({ key: o.value, label: o.label })),
    [choices],
  );
  // "Unknown" = the backend label of the UNKNOWN usage scope (not said).
  const unknownLabel = getUsageScopeLabel(USAGE_SCOPE.UNKNOWN, choices) ?? undefined;

  // Department options — the contacts choices emit the id as an INTEGER while
  // the signal payload carries STRING ids: stringify so both sides match (TD-241).
  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: String(d.value ?? d.id),
        label: String(d.label ?? d.name),
      })),
    [standardDepartments],
  );

  const initialValues = useMemo(
    () => ({
      tech_name: techstack?.tech_name || "",
      usage_scope: techstack?.usage_scope || USAGE_SCOPE.UNKNOWN,
      // Stored as {value,label} objects (ids extracted only at payload time).
      usage_departments: toDepartmentObjects(techstack?.usage_departments),
      usage_start_year: techstack?.usage_start_year ?? "",
      renewal_date: techstack?.renewal_date || "",
      cost_description: techstack?.cost_description || "",
      is_discontinued: Boolean(techstack?.is_discontinued),
      discontinued_date: techstack?.discontinued_date || "",
      notes: techstack?.notes || "",
      source_quote: techstack?.source_quote || "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [techstack?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // TechStack's writable fields (TechStackSignalUpdateSerializer) — NEVER
      // is_to_replace. Departments only for the Department scope (Company /
      // Unknown send [] so the masked list never leaks into the save).
      const isDepartment = values.usage_scope === USAGE_SCOPE.DEPARTMENT;
      const payload = {
        tech_name: values.tech_name.trim(),
        usage_scope: values.usage_scope,
        usage_departments: isDepartment
          ? (values.usage_departments || []).map((d) => d.value)
          : [],
        usage_start_year:
          values.usage_start_year === "" || values.usage_start_year === null
            ? null
            : Number(values.usage_start_year),
        renewal_date: values.renewal_date || null,
        cost_description: values.cost_description || "",
        is_discontinued: values.is_discontinued,
        discontinued_date: values.is_discontinued ? values.discontinued_date || null : null,
        notes: values.notes || "",
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("tech-stack", techstack.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Tech stack updated");
        // Return to the detail with the updated signal (display-friendly merge:
        // scope label + departments rebuilt as [{id,name}]).
        if (onSaved) {
          const labelOf = (id) => departmentOptions.find((o) => o.value === id)?.label ?? id;
          onSaved({
            ...techstack,
            ...payload,
            usage_scope_display:
              getUsageScopeLabel(payload.usage_scope, choices) ?? techstack?.usage_scope_display,
            usage_departments: payload.usage_departments.map((id) => ({ id, name: labelOf(id) })),
          });
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

  // Unticking "discontinued" also clears its date (backend: date forbidden).
  const setDiscontinued = (v) => {
    setFieldValue("is_discontinued", v);
    if (!v) setFieldValue("discontinued_date", "");
  };

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => (onCancel ? onCancel() : closeDrawer())}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={2.5} data-testid="techstack-edit">
        {/* ---- SECTION 1 — Technology ---- */}
        <Stack spacing={1.5}>
          <SectionHeader index={1} title="Technology" subtitle="Which tool does the prospect use?" />
          <InlineEditableValue
            name="tech_name"
            label="Tool name"
            type="text"
            value={values.tech_name}
            onChange={set("tech_name")}
            placeholder="Required"
            error={Boolean(errors.tech_name)}
            helperText={errors.tech_name}
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Usage (exclusive scope: Department · Company · Unknown) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Usage"
            subtitle="Used by one or more departments, company-wide, or unknown."
          />
          <ScopeDepartmentsField
            scopeOptions={scopeOptions}
            scope={values.usage_scope}
            // Deselecting the active pill (null) = UNKNOWN (not said).
            onScopeChange={(key) => setFieldValue("usage_scope", key ?? USAGE_SCOPE.UNKNOWN)}
            deselectable
            departmentScope={USAGE_SCOPE.DEPARTMENT}
            departments={values.usage_departments}
            onDepartmentsChange={set("usage_departments")}
            departmentOptions={departmentOptions}
            testIdPrefix="techstack"
            error={typeof errors.usage_departments === "string" ? errors.usage_departments : undefined}
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — Lifecycle ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={3}
            title="Lifecycle"
            subtitle="Since when, next renewal, cost and whether it is discontinued."
          />
          <InlineEditableValue
            name="usage_start_year"
            label="Used since"
            value={values.usage_start_year}
            onChange={set("usage_start_year")}
            placeholder={unknownLabel}
            error={Boolean(errors.usage_start_year)}
            helperText={errors.usage_start_year}
            renderEditor={({ value, onChange, commit }) => (
              <TextField
                fullWidth
                size="small"
                type="number"
                autoFocus
                value={value ?? ""}
                onChange={(e) => onChange(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    commit();
                  }
                }}
                error={Boolean(errors.usage_start_year)}
                helperText={errors.usage_start_year}
                inputProps={{
                  "data-testid": "inline-input-usage_start_year",
                  min: MIN_USAGE_YEAR,
                  max: MAX_USAGE_YEAR,
                  step: 1,
                }}
              />
            )}
          />
          <InlineDateField
            label="Renewal date"
            name="renewal_date"
            value={values.renewal_date}
            onChange={set("renewal_date")}
            emptyText={unknownLabel}
          />
          <InlineEditableValue
            name="cost_description"
            label="Cost"
            type="text"
            value={values.cost_description}
            onChange={set("cost_description")}
            placeholder={unknownLabel}
          />
          {/* A Switch shown directly (a toggle needs no click-to-reveal). */}
          <FormControlLabel
            label="Discontinued"
            control={
              <Switch
                checked={Boolean(values.is_discontinued)}
                onChange={(e) => setDiscontinued(e.target.checked)}
              />
            }
          />
          {values.is_discontinued && (
            <Stack spacing={0.5}>
              <InlineDateField
                label="Discontinued date"
                name="discontinued_date"
                value={values.discontinued_date}
                onChange={set("discontinued_date")}
                emptyText={unknownLabel}
              />
              {errors.discontinued_date && (
                <FormHelperText error>{errors.discontinued_date}</FormHelperText>
              )}
            </Stack>
          )}
        </Stack>

        <Divider />

        {/* ---- SECTION 4 — Notes ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={4}
            title="Notes"
            subtitle="What the prospect thinks of the tool (satisfaction, pain points)."
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

        {/* ---- SECTION 5 — Source (LAST) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader index={5} title="Source" subtitle="Where does this signal come from" />
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

EditTechStackContent.propTypes = {
  /** The tech-stack signal to edit (the list / detail payload). */
  techstack: PropTypes.shape({
    id: PropTypes.string.isRequired,
    tech_name: PropTypes.string,
    usage_scope: PropTypes.string,
    usage_scope_display: PropTypes.string,
    usage_departments: PropTypes.array,
    usage_start_year: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
    renewal_date: PropTypes.string,
    cost_description: PropTypes.string,
    is_discontinued: PropTypes.bool,
    discontinued_date: PropTypes.string,
    notes: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account the signal belongs to (reserved for future scoped pickers). */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes. */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes. */
  onCancel: PropTypes.func,
};
