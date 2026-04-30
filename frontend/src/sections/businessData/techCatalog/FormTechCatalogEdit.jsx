// src/sections/businessData/techCatalog/FormTechCatalogEdit.jsx

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
import CircularWithPath from "components/@extended/progress/CircularWithPath";
import { displaySuccessSnackbar } from "utils/displayError";
import { handleFormikError } from "utils/formErrorHandler";

// api
import {
  updateTechCatalogEntry,
  useGetTechCatalogEntry,
} from "api/businessData/techCatalog";

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
  company_name: Yup.string()
    .trim()
    .required("Company name is required")
    .min(2, "Company name must be at least 2 characters")
    .max(255, "Company name must be less than 255 characters"),

  // Product name optional client-side: blank → backend keeps the
  // current product_name as-is on PATCH (we just don't send the field).
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

const buildInitialValues = (entry) => ({
  company_name: entry?.company_name || "",
  product_name: entry?.product_name || "",
  vendor_url: entry?.vendor_url || "",
  is_competitor: Boolean(entry?.is_competitor),
  is_integration_target: Boolean(entry?.is_integration_target),
});

// ==============================|| SANITIZE PAYLOAD ||============================== //

/**
 * Build a PATCH payload from form values.
 *
 * Behaviour:
 *   - All string fields are trimmed.
 *   - Empty strings for `vendor_url` are sent as `null` so the admin
 *     can explicitly clear a previously set URL.
 *   - Empty `product_name` is NOT sent — the backend would auto-fill it
 *     to company_name on update, which is the wrong semantic for an
 *     existing row. The user clears product_name only by typing the
 *     same value as company_name explicitly.
 *   - Booleans always sent (false is a meaningful value).
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

  // vendor_url: send trimmed value or explicit null to clear
  const vendorUrl = (values.vendor_url || "").trim();
  payload.vendor_url = vendorUrl ? vendorUrl : null;

  return payload;
}

// ==============================|| FORM TECH CATALOG EDIT ||============================== //

function FormTechCatalogEdit({ closeModal, entryId, entry: initialEntry }) {
  const [loading, setLoading] = useState(false);

  // Fetch entry data if not provided. When the parent passes the entry
  // directly (most cases) we skip the fetch by gating the hook on a
  // valid id but the hook already handles `null` via isValidUUID.
  const { entry: fetchedEntry, entryLoading } = useGetTechCatalogEntry(entryId);
  const entryData = initialEntry || fetchedEntry;

  const formik = useFormik({
    initialValues: buildInitialValues(entryData),
    validationSchema: EditSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        setLoading(true);
        const payload = sanitizePayload(values);
        const result = await updateTechCatalogEntry(entryData.id, payload);

        if (result.success) {
          displaySuccessSnackbar("Tech catalog entry updated successfully");
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

  // Loading state — wait for both the entry data and prevent rendering
  // an empty form against a missing record.
  if (entryLoading || !entryData) {
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
        <DialogTitle>Edit Tech Catalog Entry</DialogTitle>
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
                  placeholder="e.g. Sales Cloud"
                  {...getFieldProps("product_name")}
                  error={Boolean(touched.product_name && errors.product_name)}
                  helperText={touched.product_name && errors.product_name}
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

FormTechCatalogEdit.propTypes = {
  closeModal: PropTypes.func,
  entryId: PropTypes.string,
  entry: PropTypes.object,
};

export default React.memo(FormTechCatalogEdit);
