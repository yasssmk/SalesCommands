// frontend/src/sections/activities/workspace/EditContactContent.jsx
//
// CT-3 / CT-4 — the Contact EDIT drawer content, cloned from EditActivityContent
// (Formik + DrawerContentLayout global Save/Cancel + InlineEditableValue,
// double-click to edit). Opened by the ✎ of the read-only Contact fiche.
//
// Sectioned like the edit-activity drawer:
//   • Identity — first_name*, last_name*, then job_title + department (select).
//   • Contact — coordinates email / phone / linkedin, each always shown with a
//     "No …" placeholder when empty.
//   • Role in the decision — ONLY when the fiche was opened inside a Decision
//     Cycle (activity.decision_cycle). Role + Influence, pre-filled from the
//     contact's qualified entry in DC people. Editing it writes a MANUAL
//     PeopleSignal via createSignal("people", …) — the exact flow the DC
//     People tab uses — never the Contact record.
//
// Save: updateContact for identity + coordinates (optional string fields sent as
// "" not null — the write serializer allows blank but not null), then, only if
// the role/influence changed in a DC, createSignal("people", …) + revalidate DC
// people. account_id is never sent. Theme tokens only, no hardcoded hex/px.

"use client";

import PropTypes from "prop-types";
import { useMemo } from "react";

import { useFormik } from "formik";
import * as Yup from "yup";

// MUI
import { useTheme } from "@mui/material/styles";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { useGetContact, useGetContactChoices, updateContact } from "api/businessData/contacts";
import { useGetDCPeople } from "api/accounts/decisionCycles";
import { createSignal } from "api/signals/signals";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import InlineEditableValue from "components/drawer/InlineEditableValue";

// Mirror of the DC People tab's stakeholder role / influence enums
// (sections/accounts/dc-workspace/PeopleTab.jsx:44-61).
const ROLE_OPTIONS = [
  { value: "CHAMPION", label: "Champion" },
  { value: "ECONOMIC_BUYER", label: "Economic Buyer" },
  { value: "DECISION_MAKER", label: "Decision Maker" },
  { value: "INFLUENCER", label: "Influencer" },
  { value: "BLOCKER", label: "Blocker" },
  { value: "END_USER", label: "End User" },
  { value: "PROCUREMENT", label: "Procurement" },
];
const INFLUENCE_OPTIONS = [
  { value: "HIGH", label: "High" },
  { value: "MEDIUM", label: "Medium" },
  { value: "LOW", label: "Low" },
];

// ==============================|| VALIDATION ||============================== //

const validationSchema = Yup.object({
  first_name: Yup.string().trim().required("First name is required"),
  last_name: Yup.string().trim().required("Last name is required"),
  email: Yup.string().trim().email("Must be a valid email").nullable(),
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

// ==============================|| EDIT CONTACT CONTENT ||============================== //

export default function EditContactContent({ contactId, activity, onSaved }) {
  const theme = useTheme();
  const { closeDrawer } = useWorkspaceDrawer();

  const { contact, contactLoading } = useGetContact(contactId);
  const { standardDepartments } = useGetContactChoices();
  const departmentOptions = standardDepartments || [];

  // Decision-cycle context (only when the fiche was opened from a DC activity).
  const cycleId = activity?.decision_cycle || null;
  const accountId =
    activity?.account_detail?.id || activity?.account || contact?.account?.id || null;
  const { people, mutatePeople } = useGetDCPeople(cycleId);

  // The contact's current qualified entry in DC people → role/influence prefill.
  const dcEntry =
    (people?.qualified || []).find((q) => q?.target_contact?.id === contactId) || null;
  const dcRole = dcEntry?.role || "";
  const dcInfluence = dcEntry?.influence || "";
  const inDC = Boolean(cycleId);

  // enableReinitialize refills once the (SWR-cached) fetches resolve; keyed on
  // the values so the role fills in when DC people arrives.
  const initialValues = useMemo(
    () => ({
      first_name: contact?.first_name || "",
      last_name: contact?.last_name || "",
      job_title: contact?.job_title || "",
      standard_department_id:
        contact?.standard_department?.id || contact?.standard_department_id || "",
      email: contact?.email || "",
      phone_number: contact?.phone_number || "",
      linkedin: contact?.linkedin || "",
      role: dcRole,
      influence: dcInfluence,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [contact?.id, cycleId, dcRole, dcInfluence],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // (1) identity + coordinates → updateContact. Optional string fields go as
      // "" (not null); only the department FK clears with null.
      const payload = {
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        job_title: values.job_title?.trim() || "",
        standard_department_id: values.standard_department_id || null,
        email: values.email?.trim() || "",
        phone_number: values.phone_number?.trim() || "",
        linkedin: values.linkedin?.trim() || "",
      };
      try {
        const result = await updateContact(contactId, payload);
        if (!result?.success) {
          displayErrorSnackbar(result);
          return;
        }

        // (2) role in the decision — only in a DC, only when it actually changed
        // and a role is set. Same MANUAL PeopleSignal flow as the DC People tab.
        const roleChanged =
          inDC &&
          Boolean(values.role) &&
          (values.role !== dcRole || (values.influence || "") !== (dcInfluence || ""));
        if (roleChanged) {
          const signalPayload = {
            role: values.role,
            target_contact: contactId,
            account: accountId,
            source: "MANUAL",
            decision_cycle: cycleId,
          };
          if (values.influence) signalPayload.influence = values.influence;
          const signalResult = await createSignal("people", signalPayload);
          if (!signalResult?.success) {
            displayErrorSnackbar(signalResult);
            return;
          }
          mutatePeople?.();
        }

        displaySuccessSnackbar("Contact updated");
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

  if (contactLoading || !contact) {
    return (
      <DrawerContentLayout>
        <Box
          data-testid="edit-contact-loading"
          sx={{ display: "flex", justifyContent: "center", py: 4 }}
        >
          <CircularProgress size={theme.iconSizes.md} />
        </Box>
      </DrawerContentLayout>
    );
  }

  return (
    <DrawerContentLayout
      onSave={formik.handleSubmit}
      onCancel={() => closeDrawer()}
      saveDisabled={!formik.isValid || !formik.dirty || formik.isSubmitting}
    >
      <Stack spacing={2}>
        {/* Identity */}
        <Stack spacing={1.5}>
          <InlineEditableValue
            name="first_name"
            label="First name"
            value={values.first_name}
            onChange={(v) => setFieldValue("first_name", v)}
            placeholder="Required"
            error={Boolean(errors.first_name)}
            helperText={errors.first_name}
          />
          <InlineEditableValue
            name="last_name"
            label="Last name"
            value={values.last_name}
            onChange={(v) => setFieldValue("last_name", v)}
            placeholder="Required"
            error={Boolean(errors.last_name)}
            helperText={errors.last_name}
          />
          <InlineEditableValue
            name="job_title"
            label="Job title"
            value={values.job_title}
            onChange={(v) => setFieldValue("job_title", v)}
            placeholder="No job title"
          />
          <InlineEditableValue
            name="standard_department_id"
            label="Department"
            type="select"
            options={departmentOptions}
            value={values.standard_department_id}
            onChange={(v) => setFieldValue("standard_department_id", v)}
            placeholder="No department"
          />
        </Stack>

        <Rule />

        {/* Contact — coordinates */}
        <Stack spacing={1.5}>
          <SectionCaption>Contact</SectionCaption>
          <InlineEditableValue
            name="email"
            label="Email"
            value={values.email}
            onChange={(v) => setFieldValue("email", v)}
            placeholder="No email"
            error={Boolean(errors.email)}
            helperText={errors.email}
          />
          <InlineEditableValue
            name="phone_number"
            label="Phone"
            value={values.phone_number}
            onChange={(v) => setFieldValue("phone_number", v)}
            placeholder="No phone"
          />
          <InlineEditableValue
            name="linkedin"
            label="LinkedIn"
            value={values.linkedin}
            onChange={(v) => setFieldValue("linkedin", v)}
            placeholder="No LinkedIn"
          />
        </Stack>

        {/* Role in the decision — only inside a DC */}
        {inDC && (
          <>
            <Rule />
            <Stack spacing={1.5} data-testid="edit-contact-role-section">
              <SectionCaption>Role in the decision</SectionCaption>
              <InlineEditableValue
                name="role"
                label="Role"
                type="select"
                options={ROLE_OPTIONS}
                value={values.role}
                onChange={(v) => setFieldValue("role", v)}
                placeholder="No role defined"
              />
              <InlineEditableValue
                name="influence"
                label="Influence"
                type="select"
                options={INFLUENCE_OPTIONS}
                value={values.influence}
                onChange={(v) => setFieldValue("influence", v)}
                placeholder="No influence"
              />
            </Stack>
          </>
        )}
      </Stack>
    </DrawerContentLayout>
  );
}

EditContactContent.propTypes = {
  /** UUID of the contact to edit (fetched fresh via useGetContact). */
  contactId: PropTypes.string.isRequired,
  /** The activity the fiche was opened from — supplies decision_cycle + account
      for the "role in the decision" section (DC only). */
  activity: PropTypes.object,
  /** Optional callback fired after a successful save (before the coque closes). */
  onSaved: PropTypes.func,
};
