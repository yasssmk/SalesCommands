// frontend/src/sections/activities/workspace/EditContactContent.jsx
//
// CT-3 — the Contact EDIT drawer content, cloned from EditActivityContent: a
// shell-less node injected into the WorkspaceDrawer coque (title "Edit contact"
// from openDrawer). Built on Formik + DrawerContentLayout (global Save/Cancel) +
// InlineEditableValue (double-click a value to edit). Opened by the ✎ of the
// read-only Contact fiche.
//
// Editable (V0): identity (first_name*, last_name*, job_title) + the normalised
// department (standard_department, a bounded select) + coordinates (email,
// phone_number, linkedin). NOT influence_level / has_buying_authority, NOT the
// free-text `department`.
//
// Save PATCHes via updateContact with exactly that field set (never account_id —
// the account does not change here), trimming phone/linkedin (the hook only
// sanitises first/last/email/job_title/notes). A duplicate email surfaces the
// backend error via displayErrorSnackbar; the coque stays open. Theme tokens
// only, no hardcoded hex/px.

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

// Project
import { useWorkspaceDrawer } from "contexts/WorkspaceDrawerContext";
import { useGetContact, useGetContactChoices, updateContact } from "api/businessData/contacts";
import { displaySuccessSnackbar, displayErrorSnackbar } from "utils/displayError";
import DrawerContentLayout from "components/drawer/DrawerContentLayout";
import InlineEditableValue from "components/drawer/InlineEditableValue";

// ==============================|| VALIDATION ||============================== //

const validationSchema = Yup.object({
  first_name: Yup.string().trim().required("First name is required"),
  last_name: Yup.string().trim().required("Last name is required"),
  email: Yup.string().trim().email("Must be a valid email").nullable(),
});

// ==============================|| EDIT CONTACT CONTENT ||============================== //

export default function EditContactContent({ contactId, onSaved }) {
  const theme = useTheme();
  const { closeDrawer } = useWorkspaceDrawer();

  const { contact, contactLoading } = useGetContact(contactId);
  const { standardDepartments } = useGetContactChoices();
  const departmentOptions = standardDepartments || [];

  // Stable per contact id — enableReinitialize refills the form once the fetch
  // (SWR-cached from the fiche) resolves.
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
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [contact?.id],
  );

  const formik = useFormik({
    enableReinitialize: true,
    validationSchema,
    initialValues,
    onSubmit: async (values, { setSubmitting }) => {
      // Exactly the V0 field set — never account_id. Optional STRING fields are
      // sent as "" when empty, never null: the write serializer
      // (core.serializers.ContactDetailsSerializer) declares email/phone/linkedin
      // with allow_blank=True but NOT allow_null, so null is rejected ("may not
      // be null") while "" clears the value (mirrors the old FormContactEdit).
      // Only the department FK clears with null (its field is allow_null). phone/
      // linkedin are trimmed here since updateContact's sanitize list omits them.
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
        if (result?.success) {
          displaySuccessSnackbar("Contact updated");
          onSaved?.();
          closeDrawer();
        } else {
          displayErrorSnackbar(result);
        }
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
      <Stack spacing={1.5}>
        {/* Identity */}
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

        {/* Coordinates */}
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
    </DrawerContentLayout>
  );
}

EditContactContent.propTypes = {
  /** UUID of the contact to edit (fetched fresh via useGetContact). */
  contactId: PropTypes.string.isRequired,
  /** Optional callback fired after a successful save (before the coque closes). */
  onSaved: PropTypes.func,
};
