// frontend/src/sections/businessData/products/FormProductCatalogAdd.jsx

import PropTypes from "prop-types";
import React, { useState } from "react";

// material-ui
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
import { displaySuccessSnackbar } from "utils/displayError";
import { handleFormikError } from "utils/formErrorHandler";

// api
import { createProductCatalogEntry } from "api/businessData/productCatalog";

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

const CreateSchema = Yup.object().shape({
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

const buildInitialValues = () => ({
  name: "",
  description: "",
  value_proposition: "",
  default_unit_price: "",
});

// ==============================|| SANITIZE PAYLOAD ||============================== //

/**
 * Build a clean payload from form values.
 *
 * Behaviour:
 *   - name: required, trimmed.
 *   - description / value_proposition: trimmed; if blank, omitted.
 *   - default_unit_price: sent as a Number when provided; if blank,
 *     omitted (the column is nullable server-side).
 */
function sanitizePayload(values) {
  const payload = {
    name: values.name.trim(),
  };

  const description = (values.description || "").trim();
  if (description) {
    payload.description = description;
  }

  const valueProposition = (values.value_proposition || "").trim();
  if (valueProposition) {
    payload.value_proposition = valueProposition;
  }

  const price = String(values.default_unit_price ?? "").trim();
  if (price !== "") {
    payload.default_unit_price = Number(price);
  }

  return payload;
}

// ==============================|| FORM PRODUCT CATALOG ADD ||============================== //

function FormProductCatalogAdd({ closeModal }) {
  const [loading, setLoading] = useState(false);

  const formik = useFormik({
    initialValues: buildInitialValues(),
    validationSchema: CreateSchema,
    enableReinitialize: false,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        setLoading(true);
        const payload = sanitizePayload(values);
        const result = await createProductCatalogEntry(payload);

        if (result.success) {
          displaySuccessSnackbar("Product created successfully");
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

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        <DialogTitle>Add Product</DialogTitle>
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
                  {isSubmitting || loading ? "Creating..." : "Create"}
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </DialogActions>
      </Form>
    </FormikProvider>
  );
}

FormProductCatalogAdd.propTypes = {
  closeModal: PropTypes.func,
};

export default React.memo(FormProductCatalogAdd);
