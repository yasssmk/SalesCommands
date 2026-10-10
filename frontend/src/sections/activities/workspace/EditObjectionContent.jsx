// frontend/src/sections/activities/workspace/EditObjectionContent.jsx
//
// Objection S2 — the Objection (BlockerSignal, front key "blockers") EDIT drawer
// content, on the standard chassis, a clone of EditConstraintContent: numbered
// SectionHeaders + InlineEditableValue on DrawerContentLayout (global
// Save/Cancel). The coque owns the "Edit objection" title. Save PATCHes via
// updateSignal("blockers", id, payload) — front type key is PLURAL "blockers";
// onSaved(updatedSignal) returns to the detail.
//
// Deltas vs Constraint:
//   - Fields: summary + contact + source_quote. NO nature/rigidity, NO scope,
//     NO notes (BlockerSignal has none).
//   - contact: the manual attribution (never set by the LLM), picked with the
//     SHARED AsyncContactSelect scoped to the activity's account (same usage as
//     EditActivityContent), clearable (→ null). The payload sends its UUID only.
//
// Theme tokens only. InlineEditableValue supports text / textarea / select.

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { updateSignal } from "api/signals/signals";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SectionHeader from "components/display/SectionHeader";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";

// ==============================|| HELPERS ||============================== //

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

// ==============================|| VALIDATION ||============================== //
//
// summary required (identical to Constraint). contact optional (clearable).

const validationSchema = Yup.object({
  summary: Yup.string()
    .trim()
    .min(10, "Summary must be at least 10 characters")
    .required("Summary is required"),
  contact: Yup.object().nullable(),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT OBJECTION CONTENT ||============================== //

export default function EditObjectionContent({ objection, accountId, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();

  const initialValues = useMemo(
    () => ({
      summary: objection?.summary || "",
      // Held as the contact OBJECT (the picker's value); the id is extracted
      // only at payload time.
      contact: objection?.contact || null,
      source_quote: objection?.source_quote || "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [objection?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only Objection's writable fields (BlockerSignal PATCH): summary,
      // contact (UUID | null), source_quote.
      const payload = {
        summary: values.summary.trim(),
        contact: values.contact?.id ?? null,
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("blockers", objection.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Objection updated");
        if (onSaved) {
          const updatedSignal = {
            ...objection,
            summary: payload.summary,
            contact: toCompactContact(values.contact),
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
        {/* ---- SECTION 1 — What's the objection? ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="What's the objection?"
            subtitle="Describe the objection raised by the prospect."
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
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Who raised it? (optional, clearable) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="Who raised it?"
            subtitle="Optional — a contact of this account."
          />
          <AsyncContactSelect
            data-testid="objection-contact-select"
            value={values.contact}
            onChange={(_event, contact) => setFieldValue("contact", contact ?? null)}
            filters={{ account_id: accountId }}
            label=""
            placeholder="Search contacts…"
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

EditObjectionContent.propTypes = {
  /** The objection (blocker) signal to edit (the full detail payload). */
  objection: PropTypes.shape({
    id: PropTypes.string.isRequired,
    summary: PropTypes.string,
    contact: PropTypes.shape({
      id: PropTypes.string,
      first_name: PropTypes.string,
      last_name: PropTypes.string,
      job_title: PropTypes.string,
    }),
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
