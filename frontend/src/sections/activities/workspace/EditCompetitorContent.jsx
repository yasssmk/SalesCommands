// frontend/src/sections/activities/workspace/EditCompetitorContent.jsx
//
// Sprint Competitor C2 — the Competitor (CompetitorSignal, front key
// "competitors") EDIT drawer content, on the standard chassis, a clone of
// EditObjectionContent: numbered SectionHeaders + InlineEditableValue on
// DrawerContentLayout (global Save/Cancel). The coque owns the "Edit competitor"
// title. Save PATCHes via updateSignal("competitors", id, payload);
// onSaved(updatedSignal) returns to the detail.
//
// Deltas vs Objection:
//   - Fields: competitor_name + summary + source_quote. NO contact (no
//     attribution on Competitor), NO notes (CompetitorSignal has none).
//   - competitor_name: required, at most COMPETITOR_NAME_MAX_LENGTH (backend
//     model limit). summary: at least SIGNAL_SUMMARY_MIN_LENGTH (as Objection).
//
// Theme tokens only. Limits come from signalValidationRules.js.

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
import {
  COMPETITOR_NAME_MAX_LENGTH,
  SIGNAL_SUMMARY_MIN_LENGTH,
} from "sections/activities/signals/signalValidationRules";

// ==============================|| VALIDATION ||============================== //
//
// competitor_name required + bounded; summary as Objection; quote optional.

const validationSchema = Yup.object({
  competitor_name: Yup.string()
    .trim()
    .max(
      COMPETITOR_NAME_MAX_LENGTH,
      `Competitor name must be at most ${COMPETITOR_NAME_MAX_LENGTH} characters`,
    )
    .required("Competitor name is required"),
  summary: Yup.string()
    .trim()
    .min(
      SIGNAL_SUMMARY_MIN_LENGTH,
      `Summary must be at least ${SIGNAL_SUMMARY_MIN_LENGTH} characters`,
    )
    .required("Summary is required"),
  source_quote: Yup.string().nullable(),
});

// ==============================|| EDIT COMPETITOR CONTENT ||============================== //

export default function EditCompetitorContent({ competitor, onSaved, onCancel }) {
  const { closeDrawer } = useWorkspaceDrawer();

  const initialValues = useMemo(
    () => ({
      competitor_name: competitor?.competitor_name || "",
      summary: competitor?.summary || "",
      source_quote: competitor?.source_quote || "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [competitor?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Only Competitor's writable fields (CompetitorSignal PATCH).
      const payload = {
        competitor_name: values.competitor_name.trim(),
        summary: values.summary.trim(),
        source_quote: values.source_quote || "",
      };
      try {
        const result = await updateSignal("competitors", competitor.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Competitor updated");
        if (onSaved) {
          onSaved({ ...competitor, ...payload });
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
        {/* ---- SECTION 1 — Competitor ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={1}
            title="Competitor"
            subtitle="The competing tool or vendor."
          />
          <InlineEditableValue
            name="competitor_name"
            label="Name"
            value={values.competitor_name}
            onChange={set("competitor_name")}
            placeholder="Required"
            error={Boolean(errors.competitor_name)}
            helperText={errors.competitor_name}
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Summary (the AI sentence) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader
            index={2}
            title="What was said?"
            subtitle="How the prospect positions this competitor."
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

        {/* ---- SECTION 3 — Source quote (last) ---- */}
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

EditCompetitorContent.propTypes = {
  /** The competitor signal to edit (the full detail payload). */
  competitor: PropTypes.shape({
    id: PropTypes.string.isRequired,
    competitor_name: PropTypes.string,
    summary: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** Fired after a successful save with the updated signal — the caller
      revalidates and returns to the detail. Absent → the drawer closes. */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes. */
  onCancel: PropTypes.func,
};
