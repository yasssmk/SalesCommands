// frontend/src/sections/activities/workspace/EditPeopleContent.jsx
//
// People S3 — the People (PeopleSignal, front key "people") EDIT drawer
// content, on the standard chassis, a clone of EditObjectionContent: numbered
// SectionHeaders + InlineEditableValue on DrawerContentLayout (global
// Save/Cancel). The coque owns the "Edit people" title. Save PATCHes via
// updateSignal("people", id, payload); onSaved(updatedSignal) returns to the
// detail.
//
// Deltas vs Objection:
//   - §1 "Who is this person?": contact (the SHARED AsyncContactSelect scoped
//     to the activity's account, clearable → null), the name as mentioned
//     (full_name) and the department (single-FK select, pattern Objective,
//     with an empty "—" option → null).
//   - §2 "What is their role?": role (select, REQUIRED) and influence (select,
//     clearable "—" → null) — options from the choices endpoint ONLY
//     (people_roles / people_influences, no hard-coded list) — and why (notes).
//   - Identity invariant (mirror of PeopleSignalUpdateSerializer.validate):
//     contact OR name OR department. None → Save disabled + a warning help
//     (business rule, not a red error).
//   - Department ids: the contacts choices emit INT values while the signal
//     payload carries the id as a STRING; options are stringified and the form
//     holds the {value,label} OBJECT (pattern EditPainContent, TD-241).
//
// Theme tokens only. InlineEditableValue supports text / textarea / select.

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import Alert from "@mui/material/Alert";
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
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";
import { formatContact } from "sections/activities/signals/utils/signalDisplay";

// ==============================|| HELPERS ||============================== //

// Empty option prepended to the clearable selects (mirror of EditConstraintContent).
const EMPTY_OPTION = { value: "", label: "—" };

function resolveLabel(options, value) {
  if (!value || !options) return null;
  return options.find((o) => o.value === value)?.label ?? value;
}

// The compact contact shape the detail payload carries ({id, first_name,
// last_name, job_title}) — rebuilt from the picked contact for onSaved.
function toCompactContact(contact) {
  if (!contact) return null;
  return {
    id: contact.id,
    first_name: contact.first_name,
    last_name: contact.last_name,
    job_title: contact.job_title,
  };
}

// The detail payload's compact department ({id, name}) → the {value,label}
// OBJECT the form holds (id kept as a string — str(dept.id)).
function toDepartmentObject(dept) {
  if (!dept) return null;
  return typeof dept === "object"
    ? { value: String(dept.id), label: dept.name ?? String(dept.id) }
    : { value: String(dept), label: String(dept) };
}

// Identity invariant: at least one of contact / name / department.
function hasIdentity(values) {
  return Boolean(values.contact || (values.full_name || "").trim() || values.department);
}

// ==============================|| VALIDATION ||============================== //
//
// role required. Everything else optional (the identity invariant is checked
// separately so it surfaces as a warning help, not a field error).

const validationSchema = Yup.object({
  role: Yup.string().required("Role is required"),
  influence: Yup.string().nullable(),
  contact: Yup.object().nullable(),
  full_name: Yup.string().nullable(),
  department: Yup.object().nullable(),
  notes: Yup.string().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT PEOPLE CONTENT ||============================== //

export default function EditPeopleContent({ people, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();
  const { choices } = useGetSignalChoices();
  const { standardDepartments } = useGetContactChoices();

  const roleOptions = choices?.people_roles ?? [];
  // influence is OPTIONAL & clearable → prepend the empty "—" option.
  const influenceOptions = useMemo(
    () => [EMPTY_OPTION, ...(choices?.people_influences ?? [])],
    [choices?.people_influences],
  );
  // Stringified so they line up with the string ids of the signal payload.
  const departmentOptions = useMemo(
    () =>
      (standardDepartments ?? []).map((d) => ({
        value: String(d.value ?? d.id),
        label: String(d.label ?? d.name),
      })),
    [standardDepartments],
  );
  // department is OPTIONAL & clearable → prepend the empty "—" option.
  const departmentSelectOptions = useMemo(
    () => [EMPTY_OPTION, ...departmentOptions],
    [departmentOptions],
  );

  const initialValues = useMemo(
    () => ({
      // Held as the contact OBJECT (the picker's value); the id is extracted
      // only at payload time.
      contact: people?.target_contact || null,
      full_name: people?.full_name || "",
      department: toDepartmentObject(people?.target_department),
      role: people?.role || "",
      influence: people?.influence || "",
      notes: people?.notes || "",
      source_quote: people?.source_quote || "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [people?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only People's writable fields (PeopleSignal PATCH).
      const payload = {
        role: values.role,
        influence: values.influence || null,
        target_contact: values.contact?.id ?? null,
        target_department: values.department?.value ?? null,
        full_name: (values.full_name || "").trim(),
        notes: values.notes || "",
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("people", people.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("People updated");
        if (onSaved) {
          const updatedSignal = {
            ...people,
            role: payload.role,
            role_display: resolveLabel(roleOptions, payload.role) ?? people?.role_display,
            influence: payload.influence,
            influence_display: payload.influence
              ? resolveLabel(influenceOptions, payload.influence)
              : null,
            target_contact: toCompactContact(values.contact),
            target_department: values.department
              ? { id: values.department.value, name: values.department.label }
              : null,
            full_name: payload.full_name,
            notes: payload.notes,
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
  const identityMissing = !hasIdentity(values);

  // InlineEditableValue raises the picked option VALUE (the string id); the form
  // keeps the {value,label} object ("" — the empty option — clears it).
  const handleDepartmentChange = (value) => {
    const picked = departmentOptions.find((o) => o.value === value) ?? null;
    setFieldValue("department", picked);
  };

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => (onCancel ? onCancel() : closeDrawer())}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting || identityMissing}
    >
      <Stack spacing={2.5}>
        {/* ---- SECTION 1 — Who is this person? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="Who is this person?"
            subtitle="Link a contact of this account, or keep the name as mentioned."
          />
          {/* Contact on the click-to-edit pattern: name in read → one click →
              focused search with the list open → a choice (or Clear, which
              unlinks) returns to read. */}
          <InlineEditableValue
            name="contact"
            label="Contact"
            value={values.contact}
            onChange={(contact) => setFieldValue("contact", contact ?? null)}
            formatValue={formatContact}
            renderEditor={({ value, onChange, commit }) => (
              <AsyncContactSelect
                data-testid="people-contact-select"
                value={value}
                onChange={(_event, contact) => {
                  onChange(contact ?? null);
                  commit();
                }}
                filters={{ account_id: accountId }}
                label=""
                placeholder="Search contacts…"
                autoFocus
                openOnFocus
              />
            )}
          />
          <InlineEditableValue
            name="full_name"
            label="Name as mentioned"
            type="text"
            value={values.full_name}
            onChange={set("full_name")}
            placeholder="No name mentioned"
          />
          <InlineEditableValue
            name="department"
            label="Department"
            type="select"
            value={values.department?.value ?? ""}
            options={departmentSelectOptions}
            onChange={handleDepartmentChange}
          />
          {identityMissing && (
            <Alert severity="warning" data-testid="people-identity-warning">
              Link a contact, or give a name or a department to identify this person.
            </Alert>
          )}
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — What is their role? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="What is their role?"
            subtitle="Their part in the buying decision, and why."
          />
          <InlineEditableValue
            name="role"
            label="Role"
            type="select"
            options={roleOptions}
            value={values.role}
            onChange={set("role")}
            placeholder="Required"
            error={Boolean(errors.role)}
            helperText={errors.role}
          />
          <InlineEditableValue
            name="influence"
            label="Influence"
            type="select"
            options={influenceOptions}
            value={values.influence}
            onChange={set("influence")}
            placeholder="Not assessed"
          />
          <InlineEditableValue
            name="notes"
            label="Why"
            type="textarea"
            value={values.notes}
            onChange={set("notes")}
            placeholder="No notes"
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — Source quote ---- */}
        <Stack spacing={1.5}>
          <SectionHeader index={3} title="Source quote" subtitle="Where does this signal come from" />
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

EditPeopleContent.propTypes = {
  /** The people signal to edit (the full detail payload). */
  people: PropTypes.shape({
    id: PropTypes.string.isRequired,
    role: PropTypes.string,
    role_display: PropTypes.string,
    influence: PropTypes.string,
    influence_display: PropTypes.string,
    full_name: PropTypes.string,
    target_contact: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      job_title: PropTypes.string,
    }),
    target_department: PropTypes.shape({
      id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
      name: PropTypes.string,
    }),
    notes: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Account of the activity — scopes the contact picker to its contacts. */
  accountId: PropTypes.string,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes (legacy). */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes (legacy). */
  onCancel: PropTypes.func,
};
