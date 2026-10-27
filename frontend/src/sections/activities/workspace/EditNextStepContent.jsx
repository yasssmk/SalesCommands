// frontend/src/sections/activities/workspace/EditNextStepContent.jsx
//
// Sprint Next steps 5.5 — the next step (NextStepSignal, front key
// "next-steps") EDIT drawer content, on the standard chassis, a clone of
// EditCompetitorContent: numbered SectionHeaders + InlineEditableValue on
// DrawerContentLayout (global Save/Cancel). The coque owns the "Edit next step"
// title. Save PATCHes via updateSignal("next-steps", id, payload) with ONLY the
// changed fields; onSaved(updatedSignal) returns to the detail.
//
// Sections = EXACTLY the detail's (NextStepDetailView): §1 Proposal (title,
// type, date + the date as said, DC step, carried by) → §2 Purpose (long
// texts) → §3 Source (the quote).
//
// Writable fields = NextStepSignalUpdateSerializer's, minus those the UI never
// sends: suggested_contacts (dormant, TD-7), advice_rationale (dormant
// capacity, PO) and — 5.8g, PO — the names cited (suggested_people,
// suggested_people_names, suggested_internal_names): not shown, never sent, the
// data stays (used only by the activity creation pre-fill). The DC step is one
// of the cycle's steps (the server refuses any other).
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
import { useGetDecisionStepsByCycle } from "api/accounts/decisionCycles";
import { ACTIVITY_TYPE_LABELS } from "api/accounts/activities";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import SectionHeader from "components/display/SectionHeader";
import InlineEditableValue from "components/drawer/InlineEditableValue";
import InlineDateField from "components/drawer/InlineDateField";
import { NEXT_STEP_TITLE_MAX_LENGTH } from "sections/activities/signals/signalValidationRules";

// "Carried by" is a boolean on the model; the select holds these two keys.
const CARRIED_BY = { PROSPECT: "PROSPECT", SELLER: "SELLER" };
const CARRIED_BY_OPTIONS = [
  { value: CARRIED_BY.PROSPECT, label: "Prospect" },
  { value: CARRIED_BY.SELLER, label: "Seller" },
];

const TYPE_OPTIONS = Object.entries(ACTIVITY_TYPE_LABELS).map(([value, label]) => ({
  value,
  label,
}));

// ==============================|| VALIDATION ||============================== //

const validationSchema = Yup.object({
  suggested_title: Yup.string()
    .trim()
    .max(
      NEXT_STEP_TITLE_MAX_LENGTH,
      `Title must be at most ${NEXT_STEP_TITLE_MAX_LENGTH} characters`,
    )
    .required("Title is required"),
  suggested_activity_type: Yup.string().required("Type is required"),
});

// The form values → the PATCH fields (one place, used for the diff too).
function toPayload(values) {
  return {
    suggested_title: values.suggested_title.trim(),
    suggested_activity_type: values.suggested_activity_type,
    suggested_due_date: values.suggested_due_date || null,
    suggested_date_text: values.suggested_date_text,
    suggested_decision_step: values.suggested_decision_step || null,
    carried_by_prospect: values.carried_by === CARRIED_BY.PROSPECT,
    suggested_objective: values.suggested_objective,
    suggested_success_criterion: values.suggested_success_criterion,
    suggested_topics: values.suggested_topics,
    source_quote: values.source_quote,
  };
}

// Only the fields whose value changed.
function changedFields(initialValues, values) {
  const before = toPayload(initialValues);
  const after = toPayload(values);
  return Object.fromEntries(
    Object.entries(after).filter(([k, v]) => JSON.stringify(v) !== JSON.stringify(before[k])),
  );
}

// ==============================|| EDIT NEXT STEP CONTENT ||============================== //

export default function EditNextStepContent({
  nextStep,
  decisionCycleId,
  onSaved,
  onCancel,
}) {
  const { closeDrawer } = useWorkspaceDrawer();

  // The DC step = one of the cycle's steps — those only (5.8g): no "Unknown"
  // choice (an unset step still READS "Unknown", the placeholder).
  const { steps } = useGetDecisionStepsByCycle(decisionCycleId);
  const stepOptions = useMemo(
    () =>
      [...steps]
        .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
        .map((s) => ({ value: String(s.id), label: s.name })),
    [steps],
  );

  const initialValues = useMemo(
    () => ({
      suggested_title: nextStep?.suggested_title || "",
      suggested_activity_type: nextStep?.suggested_activity_type || "",
      suggested_due_date: nextStep?.suggested_due_date || "",
      suggested_date_text: nextStep?.suggested_date_text || "",
      suggested_decision_step: nextStep?.suggested_decision_step
        ? String(nextStep.suggested_decision_step)
        : "",
      carried_by: nextStep?.carried_by_prospect ? CARRIED_BY.PROSPECT : CARRIED_BY.SELLER,
      suggested_objective: nextStep?.suggested_objective || "",
      suggested_success_criterion: nextStep?.suggested_success_criterion || "",
      suggested_topics: nextStep?.suggested_topics || "",
      source_quote: nextStep?.source_quote || "",
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nextStep?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      const payload = changedFields(initialValues, values);
      try {
        const result = await updateSignal("next-steps", nextStep.id, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }
        displaySuccessSnackbar("Next step updated");
        if (onSaved) {
          // The PATCH answers with the detail payload (People as objects).
          onSaved({ ...nextStep, ...result.data });
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
      <Stack spacing={2.5} data-testid="next-step-edit">
        {/* ---- SECTION 1 — Proposal (as the detail) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader index={1} title="Proposal" subtitle="The activity this next step proposes." />
          <InlineEditableValue
            name="suggested_title"
            label="Title"
            value={values.suggested_title}
            onChange={set("suggested_title")}
            placeholder="Required"
            error={Boolean(errors.suggested_title)}
            helperText={errors.suggested_title}
          />
          <InlineEditableValue
            name="suggested_activity_type"
            label="Type"
            type="select"
            options={TYPE_OPTIONS}
            value={values.suggested_activity_type}
            onChange={set("suggested_activity_type")}
            placeholder="Required"
            error={Boolean(errors.suggested_activity_type)}
            helperText={errors.suggested_activity_type}
          />
          <InlineDateField
            name="suggested_due_date"
            label="Date"
            value={values.suggested_due_date}
            onChange={set("suggested_due_date")}
            emptyText="Unknown"
          />
          <InlineEditableValue
            name="suggested_date_text"
            label="Date as said"
            value={values.suggested_date_text}
            onChange={set("suggested_date_text")}
            placeholder="Unknown"
          />
          <InlineEditableValue
            name="suggested_decision_step"
            label="DC step"
            type="select"
            options={stepOptions}
            value={values.suggested_decision_step}
            onChange={set("suggested_decision_step")}
            placeholder="Unknown"
          />
          <InlineEditableValue
            name="carried_by_prospect"
            label="Carried by"
            type="select"
            options={CARRIED_BY_OPTIONS}
            value={values.carried_by}
            onChange={set("carried_by")}
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 2 — Purpose (as the detail) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader index={2} title="Purpose" subtitle="What the proposed activity is for." />
          <InlineEditableValue
            name="suggested_objective"
            label="Objective"
            type="textarea"
            value={values.suggested_objective}
            onChange={set("suggested_objective")}
            placeholder="Unknown"
          />
          <InlineEditableValue
            name="suggested_success_criterion"
            label="Success criterion"
            type="textarea"
            value={values.suggested_success_criterion}
            onChange={set("suggested_success_criterion")}
            placeholder="Unknown"
          />
          <InlineEditableValue
            name="suggested_topics"
            label="Topics"
            type="textarea"
            value={values.suggested_topics}
            onChange={set("suggested_topics")}
            placeholder="Unknown"
          />
        </Stack>

        <Divider />

        {/* ---- SECTION 3 — Source (last, as the detail) ---- */}
        <Stack spacing={1.5}>
          <SectionHeader index={3} title="Source" subtitle="Where does this signal come from" />
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

EditNextStepContent.propTypes = {
  /** The next step to edit (the list / detail payload). */
  nextStep: PropTypes.shape({
    id: PropTypes.string.isRequired,
    suggested_title: PropTypes.string,
    suggested_activity_type: PropTypes.string,
    suggested_due_date: PropTypes.string,
    suggested_date_text: PropTypes.string,
    suggested_decision_step: PropTypes.string,
    carried_by_prospect: PropTypes.bool,
    suggested_objective: PropTypes.string,
    suggested_success_criterion: PropTypes.string,
    suggested_topics: PropTypes.string,
    source_quote: PropTypes.string,
  }).isRequired,
  /** The decision cycle — its steps. */
  decisionCycleId: PropTypes.string,
  /** Fired after a successful save with the updated next step — the caller
      revalidates and returns to the detail. Absent → the drawer closes. */
  onSaved: PropTypes.func,
  /** Fired on Cancel — the caller returns to the detail without saving.
      Absent → the drawer closes. */
  onCancel: PropTypes.func,
};
