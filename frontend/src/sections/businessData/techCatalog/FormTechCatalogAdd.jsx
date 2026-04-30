// src/sections/businessData/techCatalog/FormTechCatalogAdd.jsx

import PropTypes from "prop-types";
import React, { useState } from "react";

// material-ui
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Divider from "@mui/material/Divider";
import FormControlLabel from "@mui/material/FormControlLabel";
import FormHelperText from "@mui/material/FormHelperText";
import Grid from "@mui/material/Grid";
import InputLabel from "@mui/material/InputLabel";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

// third-party
import * as Yup from "yup";
import { useFormik, Form, FormikProvider } from "formik";

// project imports
import { displaySuccessSnackbar } from "utils/displayError";
import { handleFormikError } from "utils/formErrorHandler";

// api
import { createTechCatalogEntry } from "api/businessData/techCatalog";

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
  company_name: Yup.string()
    .trim()
    .required("Company name is required")
    .min(2, "Company name must be at least 2 characters")
    .max(255, "Company name must be less than 255 characters"),

  // Product name is optional client-side: when blank, the backend
  // auto-fills it with company_name (see TechCatalog.clean()).
  product_name: Yup.string()
    .trim()
    .max(255, "Product name must be less than 255 characters")
    .nullable(),

  vendor_url: Yup.string()
    .url("Must be a valid URL (e.g. https://example.com)")
    .max(500, "Vendor URL must be less than 500 characters")
    .nullable(),

  is_competitor: Yup.boolean(),
  is_integration_target: Yup.boolean(),
});

// ==============================|| INITIAL VALUES ||============================== //

const buildInitialValues = () => ({
  company_name: "",
  product_name: "",
  vendor_url: "",
  is_competitor: false,
  is_integration_target: false,
});

// ==============================|| SANITIZE PAYLOAD ||============================== //

/**
 * Build a clean payload from form values.
 *
 * Behaviour:
 *   - company_name: required, trimmed.
 *   - product_name: trimmed; if blank, omitted from the payload —
 *     the backend will auto-fill it with company_name.
 *   - vendor_url: trimmed; if blank, omitted.
 *   - booleans: always sent as booleans (default false).
 */
function sanitizePayload(values) {
  const payload = {
    company_name: values.company_name.trim(),
    is_competitor: Boolean(values.is_competitor),
    is_integration_target: Boolean(values.is_integration_target),
  };

  const productName = (values.product_name || "").trim();
  if (productName) {
    payload.product_name = productName;
  }

  const vendorUrl = (values.vendor_url || "").trim();
  if (vendorUrl) {
    payload.vendor_url = vendorUrl;
  }

  return payload;
}

// ==============================|| FORM TECH CATALOG ADD ||============================== //

function FormTechCatalogAdd({ closeModal }) {
  const [loading, setLoading] = useState(false);

  const formik = useFormik({
    initialValues: buildInitialValues(),
    validationSchema: CreateSchema,
    enableReinitialize: false,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        setLoading(true);
        const payload = sanitizePayload(values);
        const result = await createTechCatalogEntry(payload);

        if (result.success) {
          displaySuccessSnackbar("Tech catalog entry created successfully");
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
    setFieldValue,
    values,
  } = formik;

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        <DialogTitle>Add Tech Catalog Entry</DialogTitle>
        <Divider />

        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={2.5}>
            {/* ==================== IDENTITY ==================== */}
            <SectionTitle>Identity</SectionTitle>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="company_name">Company Name *</InputLabel>
                <TextField
                  fullWidth
                  id="company_name"
                  placeholder="e.g. Salesforce"
                  {...getFieldProps("company_name")}
                  error={Boolean(touched.company_name && errors.company_name)}
                  helperText={touched.company_name && errors.company_name}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="product_name">Product Name</InputLabel>
                <TextField
                  fullWidth
                  id="product_name"
                  placeholder="e.g. Sales Cloud (defaults to company name)"
                  {...getFieldProps("product_name")}
                  error={Boolean(touched.product_name && errors.product_name)}
                  helperText={
                    (touched.product_name && errors.product_name) ||
                    "Leave blank to use the company name as the product name"
                  }
                />
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="vendor_url">Vendor URL</InputLabel>
                <TextField
                  fullWidth
                  id="vendor_url"
                  placeholder="https://salesforce.com"
                  {...getFieldProps("vendor_url")}
                  error={Boolean(touched.vendor_url && errors.vendor_url)}
                  helperText={touched.vendor_url && errors.vendor_url}
                />
              </Stack>
            </Grid>

            {/* ==================== COMMERCIAL FLAGS ==================== */}
            <SectionTitle>Commercial Position</SectionTitle>

            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={values.is_competitor}
                    onChange={(e) =>
                      setFieldValue("is_competitor", e.target.checked)
                    }
                    color="error"
                  />
                }
                label="Competitor"
              />
              <FormHelperText>
                Replacing this product is a winnable angle in a deal.
              </FormHelperText>
            </Grid>

            <Grid item xs={12} sm={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={values.is_integration_target}
                    onChange={(e) =>
                      setFieldValue("is_integration_target", e.target.checked)
                    }
                    color="success"
                  />
                }
                label="Integration target"
              />
              <FormHelperText>
                Integrating with this product is a winnable angle in a deal.
              </FormHelperText>
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

FormTechCatalogAdd.propTypes = {
  closeModal: PropTypes.func,
};

export default React.memo(FormTechCatalogAdd);
