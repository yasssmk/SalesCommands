// frontend/src/sections/activities/workspace/EditObjectiveContent.jsx
//
// SIG-5d — the Objective EDIT drawer content on the NEW pattern
// (DrawerContentLayout + InlineEditableValue + Formik global Save), cloned from
// EditContactContent. It migrates the old InlineObjectiveForm behaviour and
// validation; the ONLY functional changes are:
//   (1) scope → the shared ObjectiveScopePill (SIG-5b): Company / Department
//       (+ department select). PERSONAL is legacy (kept as-is, never offered).
//   (2) source_quote is now editable (free text — the transcript block picker is
//       deferred to the post-deploy roadmap).
//
// Save PATCHes every field via the existing generic updateSignal("objective",
// id, patch) then snackbars + closes the coque + lets the caller revalidate.
// The old SignalEditDrawer dialog is no longer opened for Objective (the file
// stays on disk as dead code for Objective — traced, not deleted).
//
// InlineEditableValue supports only text / textarea / select, so target_date is
// a small native date field here (InlineEditableValue is reused untouched).
// Theme tokens only — no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateSignal, useGetSignalChoices } from "api/signals/signals";
import { useGetContactChoices } from "api/businessData/contacts";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import ObjectiveScopePill from "components/signals/ObjectiveScopePill";
import { OBJECTIVE_SCOPE } from "utils/objectiveScope";

// ==============================|| VALIDATION (preserved from InlineObjectiveForm) ||=========== //

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  what: Yup.string().required("Domain is required"),
  dimension: Yup.string().required("Dimension is required"),
  // Department scope requires a department (mirror of the old form + backend clean()).
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

// ==============================|| SMALL PIECES ||============================== //

function Rule() {
  const aq = useTheme().aphoriQ;
  return (
    <Box
      sx={{
        borderTopStyle: "solid",
        borderTopWidth: aq.border.width.hairline,
        borderTopColor: aq.border.color,
      }}
    />
  );
}

function SectionCaption({ children }) {
  const aq = useTheme().aphoriQ;
  return (
    <Typography variant="caption" sx={{ color: aq.text.muted, fontWeight: "bold", display: "block" }}>
      {children}
    </Typography>
  );
}
SectionCaption.propTypes = { children: PropTypes.node };

// A small labelled native date field (InlineEditableValue has no date type and
// is reused untouched). Draft-bound like the inline fields.
function DateField({ label, value, onChange }) {
  const aq = useTheme().aphoriQ;
  return (
    <Box>
      <Typography variant="caption" sx={{ color: aq.text.muted, display: "block", mb: 0.25 }}>
        {label}
      </Typography>
      <TextField
        type="date"
        size="small"
        fullWidth
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        inputProps={{ "data-testid": "objective-target-date" }}
      />
    </Box>
  );
}
DateField.propTypes = {
  label: PropTypes.string,
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
};

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

  const { values, errors, setFieldValue } = formik;

  // The scope pill raises a draft patch of scope fields (scope_level,
  // target_department, target_contact) — apply each to the form draft.
  const applyScopePatch = (patch) => {
    Object.entries(patch).forEach(([k, v]) => setFieldValue(k, v));
  };

  return (
    <DrawerContentLayout
      title="Edit objective"
      onSave={formik.handleSubmit}
      onCancel={() => closeDrawer()}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={2}>
        {/* Goal */}
        <Stack spacing={1.5}>
          <InlineEditableValue
            name="summary"
            label="Summary"
            type="textarea"
            value={values.summary}
            onChange={(v) => setFieldValue("summary", v)}
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
            onChange={(v) => setFieldValue("what", v)}
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
            onChange={(v) => setFieldValue("dimension", v)}
            placeholder="No dimension"
            disabled={choicesLoading}
            error={Boolean(errors.dimension)}
            helperText={errors.dimension}
          />
        </Stack>

        <Rule />

        {/* Scope — the shared pill (Company / Department) */}
        <Stack spacing={1}>
          <SectionCaption>Scope</SectionCaption>
          <ObjectiveScopePill
            value={{ scope_level: values.scope_level, target_department: values.target_department }}
            onChange={applyScopePatch}
            departmentOptions={departmentOptions}
          />
          {errors.target_department && (
            <Typography variant="caption" color="error">
              {errors.target_department}
            </Typography>
          )}
        </Stack>

        <Rule />

        {/* Success */}
        <Stack spacing={1.5}>
          <SectionCaption>Success</SectionCaption>
          <InlineEditableValue
            name="success_criteria"
            label="Success criteria"
            type="textarea"
            value={values.success_criteria}
            onChange={(v) => setFieldValue("success_criteria", v)}
            placeholder="No success criteria"
          />
          <DateField
            label="Target date"
            value={values.target_date}
            onChange={(v) => setFieldValue("target_date", v)}
          />
          <InlineEditableValue
            name="notes"
            label="Notes"
            type="textarea"
            value={values.notes}
            onChange={(v) => setFieldValue("notes", v)}
            placeholder="No notes"
          />
        </Stack>

        <Rule />

        {/* Source quote — now editable (free text). */}
        <InlineEditableValue
          name="source_quote"
          label="Source quote"
          type="textarea"
          value={values.source_quote}
          onChange={(v) => setFieldValue("source_quote", v)}
          placeholder="No source quote"
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
