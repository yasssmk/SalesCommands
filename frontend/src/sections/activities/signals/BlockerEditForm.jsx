// frontend/src/sections/activities/signals/BlockerEditForm.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Button from "@mui/material/Button";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";

// Formik + Yup
import { Formik, Form } from "formik";
import * as Yup from "yup";

// Project imports
import AsyncContactSelect from "components/AsyncSelection/AsyncContactSelect";

const validationSchema = Yup.object().shape({
  summary: Yup.string().required("Summary is required"),
  contact: Yup.mixed().nullable(),
});

// ==============================|| BLOCKER EDIT FORM ||============================== //

export default function BlockerEditForm({
  initialValues,
  onAdd,
  onCancel,
  accountId,
  submitLabel = "Save changes",
}) {
  const defaults = {
    summary: initialValues?.summary || "",
    contact: initialValues?.contact || null,
  };

  const handleSubmit = async (values, { setSubmitting }) => {
    const payload = {
      summary: values.summary,
      contact: values.contact?.id || values.contact || null,
    };
    try {
      await onAdd(payload);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Formik
      initialValues={defaults}
      validationSchema={validationSchema}
      onSubmit={handleSubmit}
      enableReinitialize
    >
      {({
        values,
        errors,
        touched,
        handleChange,
        handleBlur,
        setFieldValue,
        isSubmitting,
      }) => (
        <Form>
          <Stack spacing={2.5}>
            <TextField
              name="summary"
              label="Summary"
              multiline
              minRows={2}
              maxRows={6}
              value={values.summary}
              onChange={handleChange}
              onBlur={handleBlur}
              error={touched.summary && Boolean(errors.summary)}
              helperText={touched.summary && errors.summary}
              fullWidth
              required
            />

            <AsyncContactSelect
              value={values.contact}
              onChange={(val) => setFieldValue("contact", val)}
              accountId={accountId}
              label="Contact (optional)"
              placeholder="Search contacts..."
            />

            <Stack direction="row" spacing={1.5} justifyContent="flex-end">
              <Button
                variant="outlined"
                color="secondary"
                onClick={onCancel}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="contained"
                disabled={isSubmitting}
              >
                {submitLabel}
              </Button>
            </Stack>
          </Stack>
        </Form>
      )}
    </Formik>
  );
}

BlockerEditForm.propTypes = {
  initialValues: PropTypes.shape({
    summary: PropTypes.string,
    contact: PropTypes.oneOfType([PropTypes.object, PropTypes.string]),
  }),
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  accountId: PropTypes.string,
  submitLabel: PropTypes.string,
};
