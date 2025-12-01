// frontend/src/sections/admin/accounts/FormAccountAdd.jsx

import PropTypes from 'prop-types';
import React, { useState } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// project imports
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import { displaySuccessSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formErrorHandler';
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';
import AsyncAccountSelect from 'components/AsyncSelection/AsyncAccountSelect';

// api
import { createAccount, useGetAccountChoices } from 'api/admin/accounts';

// ==============================|| VALIDATION SCHEMA ||============================== //

const CreateSchema = Yup.object().shape({
  company_name: Yup.string()
    .trim()
    .required('Company name is required')
    .min(2, 'Company name must be at least 2 characters')
    .max(255, 'Company name must be less than 255 characters'),
  
  city: Yup.string()
    .trim()
    .required('City is required')
    .max(100, 'City must be less than 100 characters'),
  
  country: Yup.string()
    .trim()
    .required('Country is required')
    .max(100, 'Country must be less than 100 characters'),
  
  iindustry: Yup.string().nullable(),
  
  type: Yup.string().nullable(),
  
  classification: Yup.string().nullable(),

  website: Yup.string()
    .url('Must be a valid URL')
    .nullable(),
  
  email: Yup.string()
    .email('Must be a valid email')
    .nullable(),
  
  phone_number: Yup.string()
    .max(20, 'Phone number must be less than 20 characters')
    .nullable()
});

// ==============================|| INITIAL VALUES ||============================== //

const buildInitialValues = () => ({
  company_name: '',
  city: '',
  country: '',
  industry: '',
  type: '',
  classification: '',
  website: '',
  email: '',
  phone_number: '',
  address: '',
  post_code: '',
  state: '',
  account_owner: null,
  parent: null
});

// ==============================|| SANITIZE PAYLOAD ||============================== //

function sanitizePayload(values) {
  const payload = {};
  
  // Required fields
  payload.company_name = values.company_name.trim();
  payload.city = values.city.trim();
  payload.country = values.country.trim();
  payload.tier = values.tier;
  
  // Optional string fields
  const optionalFields = ['industry', 'website', 'email', 'phone_number', 'address', 'post_code', 'state'];
  optionalFields.forEach((field) => {
    const value = values[field];
    if (value && value.trim()) {
      payload[field] = value.trim();
    }
  });
  
  // Optional choice fields
  if (values.type) payload.type = values.type;
  if (values.classification) payload.classification = values.classification;
  if (values.industry) payload.industry = values.industry;
  
  return payload;
}

// ==============================|| FORM ACCOUNT ADD ||============================== //

function FormAccountAdd({ closeModal }) {
  const [loading, setLoading] = useState(false);

  const { types, classifications, industries, countries, choicesLoading } = useGetAccountChoices();

  const formik = useFormik({
    initialValues: buildInitialValues(),
    validationSchema: CreateSchema,
    enableReinitialize: false,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        setLoading(true);
        const payload = sanitizePayload(values);
        const result = await createAccount(payload);

        if (result.success) {
          displaySuccessSnackbar('Account created successfully');
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
    }
  });

  const { errors, touched, handleSubmit, isSubmitting, getFieldProps, setFieldValue, values } = formik;

  if (loading && !isSubmitting) {
    return (
      <Box sx={{ p: 5 }}>
        <Stack direction="row" justifyContent="center">
          <CircularWithPath />
        </Stack>
      </Box>
    );
  }

  // Show loading while fetching choices
  if (choicesLoading) {
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
        <DialogTitle>Add New Account</DialogTitle>
        <Divider />
        
        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={3}>
            
            {/* Company Name */}
            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="company_name">Company Name *</InputLabel>
                <TextField
                  fullWidth
                  id="company_name"
                  placeholder="Enter company name"
                  {...getFieldProps('company_name')}
                  error={Boolean(touched.company_name && errors.company_name)}
                  helperText={touched.company_name && errors.company_name}
                />
              </Stack>
            </Grid>

            {/* Type & Classification */}
            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="type">Type</InputLabel>
                <FormControl fullWidth error={Boolean(touched.type && errors.type)}>
                  <Select
                    id="type"
                    displayEmpty
                    value={values.type}
                    onChange={(e) => setFieldValue('type', e.target.value)}
                  >
                    <MenuItem value="">
                      <em>Select type</em>
                    </MenuItem>
                    {types.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.type && errors.type && (
                    <FormHelperText>{errors.type}</FormHelperText>
                  )}
                </FormControl>
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="classification">Classification</InputLabel>
                <FormControl fullWidth error={Boolean(touched.classification && errors.classification)}>
                  <Select
                    id="classification"
                    displayEmpty
                    value={values.classification}
                    onChange={(e) => setFieldValue('classification', e.target.value)}
                  >
                    <MenuItem value="">
                      <em>Select classification</em>
                    </MenuItem>
                    {classifications.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.classification && errors.classification && (
                    <FormHelperText>{errors.classification}</FormHelperText>
                  )}
                </FormControl>
              </Stack>
            </Grid>

            {/* Industry */}
            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="industry">Industry</InputLabel>
                <FormControl fullWidth error={Boolean(touched.industry && errors.industry)}>
                  <Select
                    id="industry"
                    displayEmpty
                    value={values.industry}
                    onChange={(e) => setFieldValue('industry', e.target.value)}
                  >
                    <MenuItem value="">
                      <em>Select industry</em>
                    </MenuItem>
                    {industries.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.industry && errors.industry && (
                    <FormHelperText>{errors.industry}</FormHelperText>
                  )}
                </FormControl>
              </Stack>
            </Grid>

            {/* Account Owner (Async Select) */}
            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel>Account Owner</InputLabel>
                <AsyncUserSelect
                  value={values.account_owner}
                  onChange={(event, newValue) => setFieldValue('account_owner', newValue)}
                  label=""
                  placeholder="Search by name or email..."
                />
              </Stack>
            </Grid>

            {/* Parent Company (Async Select) */}
            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel>Parent Company</InputLabel>
                <AsyncAccountSelect
                  value={values.parent}
                  onChange={(event, newValue) => setFieldValue('parent', newValue)}
                  label=""
                  placeholder="Search by company name..."
                />
              </Stack>
            </Grid>

            {/* Location: City, Country, State */}
            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="city">City *</InputLabel>
                <TextField
                  fullWidth
                  id="city"
                  placeholder="Enter city"
                  {...getFieldProps('city')}
                  error={Boolean(touched.city && errors.city)}
                  helperText={touched.city && errors.city}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="country">Country *</InputLabel>
                <FormControl fullWidth error={Boolean(touched.country && errors.country)}>
                  <Select
                    id="country"
                    displayEmpty
                    value={values.country}
                    onChange={(e) => setFieldValue('country', e.target.value)}
                  >
                    <MenuItem value="">
                      <em>Select country</em>
                    </MenuItem>
                    {countries.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.country && errors.country && (
                    <FormHelperText>{errors.country}</FormHelperText>
                  )}
                </FormControl>
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="state">State/Province</InputLabel>
                <TextField
                  fullWidth
                  id="state"
                  placeholder="Enter state or province"
                  {...getFieldProps('state')}
                  error={Boolean(touched.state && errors.state)}
                  helperText={touched.state && errors.state}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="post_code">Post Code</InputLabel>
                <TextField
                  fullWidth
                  id="post_code"
                  placeholder="Enter post code"
                  {...getFieldProps('post_code')}
                  error={Boolean(touched.post_code && errors.post_code)}
                  helperText={touched.post_code && errors.post_code}
                />
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="address">Address</InputLabel>
                <TextField
                  fullWidth
                  id="address"
                  placeholder="Enter address"
                  {...getFieldProps('address')}
                  error={Boolean(touched.address && errors.address)}
                  helperText={touched.address && errors.address}
                />
              </Stack>
            </Grid>

            {/* Contact Info */}
            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="website">Website</InputLabel>
                <TextField
                  fullWidth
                  id="website"
                  placeholder="https://company.com"
                  {...getFieldProps('website')}
                  error={Boolean(touched.website && errors.website)}
                  helperText={touched.website && errors.website}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="email">Email</InputLabel>
                <TextField
                  fullWidth
                  id="email"
                  placeholder="contact@company.com"
                  {...getFieldProps('email')}
                  error={Boolean(touched.email && errors.email)}
                  helperText={touched.email && errors.email}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="phone_number">Phone Number</InputLabel>
                <TextField
                  fullWidth
                  id="phone_number"
                  placeholder="+1 234 567 8900"
                  {...getFieldProps('phone_number')}
                  error={Boolean(touched.phone_number && errors.phone_number)}
                  helperText={touched.phone_number && errors.phone_number}
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
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Creating...' : 'Create'}
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </DialogActions>
      </Form>
    </FormikProvider>
  );
}

FormAccountAdd.propTypes = {
  closeModal: PropTypes.func
};

export default React.memo(FormAccountAdd);