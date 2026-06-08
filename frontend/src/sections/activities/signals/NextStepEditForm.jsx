// frontend/src/sections/activities/signals/NextStepEditForm.jsx

"use client";

import PropTypes from "prop-types";

// MUI
import Button from "@mui/material/Button";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import InputLabel from "@mui/material/InputLabel";
import FormControl from "@mui/material/FormControl";
import FormHelperText from "@mui/material/FormHelperText";

// Formik + Yup
import { Formik, Form } from "formik";
import * as Yup from "yup";

// Project imports
import {
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
} from "api/accounts/activities";

// ==============================|| VALIDATION ||============================== //

const validationSchema = Yup.object().shape({
  suggested_title: Yup.string().required("Title is required"),
  suggested_activity_type: Yup.string().required("Activity type is required"),
  suggested_due_date: Yup.date()
    .nullable()
    .typeError("Please select a valid date"),
  source_quote: Yup.string().nullable(),
});

// ==============================|| NEXT STEP EDIT FORM ||============================== //

export default function NextStepEditForm({
  initialValues,
  onAdd,
  onCancel,
  submitLabel = "Save changes",
}) {
  const defaults = {
    suggested_title: initialValues?.suggested_title || "",
    suggested_activity_type: initialValues?.suggested_activity_type || "",
    suggested_due_date: initialValues?.suggested_due_date || "",
    source_quote: initialValues?.source_quote || "",
  };

  const handleSubmit = async (values, { setSubmitting }) => {
    const payload = {
      suggested_title: values.suggested_title,
      suggested_activity_type: values.suggested_activity_type,
      suggested_due_date: values.suggested_due_date || null,
      source_quote: values.source_quote || null,
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
        isSubmitting,
      }) => (
        <Form>
          <Stack spacing={2.5}>
            <TextField
              name="suggested_title"
              label="Suggested title"
              value={values.suggested_title}
              onChange={handleChange}
              onBlur={handleBlur}
              error={
                touched.suggested_title && Boolean(errors.suggested_title)
              }
              helperText={touched.suggested_title && errors.suggested_title}
              fullWidth
              required
            />

            <FormControl
              fullWidth
              required
              error={
                touched.suggested_activity_type &&
                Boolean(errors.suggested_activity_type)
              }
            >
              <InputLabel id="nextstep-type-label">Activity type</InputLabel>
              <Select
                labelId="nextstep-type-label"
                name="suggested_activity_type"
                value={values.suggested_activity_type}
                label="Activity type"
                onChange={handleChange}
                onBlur={handleBlur}
              >
                {Object.entries(ACTIVITY_TYPES).map(([key, value]) => (
                  <MenuItem key={key} value={value}>
                    {ACTIVITY_TYPE_LABELS[key] || key}
                  </MenuItem>
                ))}
              </Select>
              {touched.suggested_activity_type &&
                errors.suggested_activity_type && (
                  <FormHelperText>
                    {errors.suggested_activity_type}
                  </FormHelperText>
                )}
            </FormControl>

            <TextField
              name="suggested_due_date"
              label="Suggested due date"
              type="date"
              value={values.suggested_due_date}
              onChange={handleChange}
              onBlur={handleBlur}
              error={
                touched.suggested_due_date &&
                Boolean(errors.suggested_due_date)
              }
              helperText={
                touched.suggested_due_date && errors.suggested_due_date
              }
              fullWidth
              InputLabelProps={{ shrink: true }}
            />

            <TextField
              name="source_quote"
              label="Source quote"
              multiline
              minRows={2}
              maxRows={6}
              value={values.source_quote}
              onChange={handleChange}
              onBlur={handleBlur}
              fullWidth
            />

            <Stack direction="row" spacing={1.5} justifyContent="flex-end">
              <Button variant="outlined" onClick={onCancel}>
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

// ==============================|| PROP TYPES ||============================== //

NextStepEditForm.propTypes = {
  initialValues: PropTypes.shape({
    suggested_title: PropTypes.string,
    suggested_activity_type: PropTypes.string,
    suggested_due_date: PropTypes.string,
    source_quote: PropTypes.string,
  }),
  onAdd: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  submitLabel: PropTypes.string,
};
