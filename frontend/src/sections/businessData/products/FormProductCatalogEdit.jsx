// frontend/src/sections/businessData/products/FormProductCatalogEdit.jsx

import PropTypes from "prop-types";
import React, { useState } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import Grid from "@mui/material/Grid";
import InputLabel from "@mui/material/InputLabel";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// third-party
import * as Yup from "yup";
import { useFormik, Form, FormikProvider } from "formik";

// project imports
import CircularWithPath from "components/@extended/progress/CircularWithPath";
import { displaySuccessSnackbar } from "utils/displayError";
import { handleFormikError } from "utils/formErrorHandler";

// api
import { updateProductCatalogEntry } from "api/businessData/productCatalog";

// ==============================|| SECTION TITLE ||============================== //

const SectionTitle = ({ children }) => (
  <Grid item xs={12}>
    <Typography
      variant="subtitle2"
      color="text.secondary"
      sx={{ mt: 1, mb: -1 }}
    >
      {children}
    </Typography>
  </Grid>
);

SectionTitle.propTypes = {
  children: PropTypes.node,
};

// ==============================|| VALIDATION SCHEMA ||============================== //

const EditSchema = Yup.object().shape({
  name: Yup.string()
    .trim()
    .required("Product name is required")
    .min(2, "Product name must be at least 2 characters")
    .max(255, "Product name must be less than 255 characters"),

  description: Yup.string().trim().nullable(),

  value_proposition: Yup.string().trim().nullable(),

  default_unit_price: Yup.number()
    .transform((value, originalValue) =>
      String(originalValue).trim() === "" ? null : value,
    )
    .typeError("Default unit price must be a number")
    .min(0, "Default unit price cannot be negative")
    .nullable(),
});

// ==============================|| INITIAL VALUES ||============================== //

const buildInitialValues = (entry) => ({
  name: entry?.name || "",
  description: entry?.description || "",
  value_proposition: entry?.value_proposition || "",
  default_unit_price:
    entry?.default_unit_price === null || entry?.default_unit_price === undefined
      ? ""
      : String(entry.default_unit_price),
});

// ==============================|| SANITIZE PAYLOAD ||============================== //

/**
 * Build a PATCH payload from form values.
 *
 * Behaviour:
 *   - name: required, trimmed.
 *   - description / value_proposition: trimmed; empty string is sent so
 *     the admin can explicitly clear a previously set value (the columns
 *     default to '' server-side).
 *   - default_unit_price: sent as a Number when provided, or explicit
 *     null to clear it (the column is nullable server-side).
 */
function sanitizePayload(values) {
  const payload = {
    name: values.name.trim(),
    description: (values.description || "").trim(),
    value_proposition: (values.value_proposition || "").trim(),
  };

  const price = String(values.default_unit_price ?? "").trim();
  payload.default_unit_price = price === "" ? null : Number(price);

  return payload;
}

// ==============================|| FORM PRODUCT CATALOG EDIT ||============================== //

function FormProductCatalogEdit({ closeModal, entry }) {
  const [loading, setLoading] = useState(false);

  const formik = useFormik({
    initialValues: buildInitialValues(entry),
    validationSchema: EditSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        setLoading(true);
        const payload = sanitizePayload(values);
        const result = await updateProductCatalogEntry(entry.id, payload);

        if (result.success) {
          displaySuccessSnackbar("Product updated successfully");
          closeModal?.();
        } else {
          handleFormikError(result, formik);
        }
      } catch (err) {
        handleFormikError(err, formik);
      } finally {
        setLoading(false);
        setSubmitting(false);
      }
    },
  });

  const {
    errors,
    touched,
    handleSubmit,
    isSubmitting,
    getFieldProps,
  } = formik;

  // Guard against a missing record — the edit form is seeded from the
  // row object passed by the list; render a spinner if it's absent.
  if (!entry) {
    return (
      <Box sx={{ p: 5 }}>
        <Stack direction="row" justifyContent="center">
          <CircularWithPath />
        </Stack>
      </Box>
    );
  }

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        <DialogTitle>Edit Product</DialogTitle>
        <Divider />

        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={2.5}>
            {/* ==================== IDENTITY ==================== */}
            <SectionTitle>Identity</SectionTitle>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="name">Product Name *</InputLabel>
                <TextField
                  fullWidth
                  id="name"
                  placeholder="e.g. Enterprise License"
                  {...getFieldProps("name")}
                  error={Boolean(touched.name && errors.name)}
                  helperText={touched.name && errors.name}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="default_unit_price">
                  Default Unit Price
                </InputLabel>
                <TextField
                  fullWidth
                  id="default_unit_price"
                  type="number"
                  placeholder="e.g. 1200.00"
                  inputProps={{ min: 0, step: "0.01" }}
                  {...getFieldProps("default_unit_price")}
                  error={Boolean(
                    touched.default_unit_price && errors.default_unit_price,
                  )}
                  helperText={
                    touched.default_unit_price && errors.default_unit_price
                  }
                />
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="description">Description</InputLabel>
                <TextField
                  fullWidth
                  id="description"
                  multiline
                  minRows={2}
                  placeholder="Optional description of the product"
                  {...getFieldProps("description")}
                  error={Boolean(touched.description && errors.description)}
                  helperText={touched.description && errors.description}
                />
              </Stack>
            </Grid>

            {/* ==================== SALES PITCH ==================== */}
            <SectionTitle>Sales Pitch</SectionTitle>

            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="value_proposition">
                  Value Proposition
                </InputLabel>
                <TextField
                  fullWidth
                  id="value_proposition"
                  multiline
                  minRows={3}
                  placeholder="Benefits and value for the sales pitch"
                  {...getFieldProps("value_proposition")}
                  error={Boolean(
                    touched.value_proposition && errors.value_proposition,
                  )}
                  helperText={
                    touched.value_proposition && errors.value_proposition
                  }
                />
              </Stack>
            </Grid>
          </Grid>
        </DialogContent>

        <Divider />

        <DialogActions sx={{ p: 2.5 }}>
          <Grid container justifyContent="flex-end" alignItems="center">
            <Grid item>
              <Stack direction="row" spacing={2} alignItems="center">
                <Button color="error" onClick={closeModal}>
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant="contained"
                  disabled={isSubmitting || loading}
                >
                  {isSubmitting || loading ? "Updating..." : "Update"}
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </DialogActions>
      </Form>
    </FormikProvider>
  );
}

FormProductCatalogEdit.propTypes = {
  closeModal: PropTypes.func,
  entry: PropTypes.object,
};

export default React.memo(FormProductCatalogEdit);
