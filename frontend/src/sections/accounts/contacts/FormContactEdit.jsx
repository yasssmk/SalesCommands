// frontend/src/sections/businessData/contacts/FormContactEdit.jsx

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
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// project imports
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import { displaySuccessSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formErrorHandler';
import AsyncAccountSelect from 'components/AsyncSelection/AsyncAccountSelect';

// api
import { updateContact, useGetContact, useGetContactChoices } from 'api/businessData/contacts';

// ==============================|| SECTION TITLE ||============================== //

const SectionTitle = ({ children }) => (
  <Grid item xs={12}>
    <Typography variant="subtitle2" color="text.secondary" sx={{ mt: 1, mb: -1 }}>
      {children}
    </Typography>
  </Grid>
);

SectionTitle.propTypes = {
  children: PropTypes.node
};

// ==============================|| VALIDATION SCHEMA ||============================== //

const EditSchema = Yup.object().shape({
  first_name: Yup.string()
    .required('First name is required')
    .min(1, 'First name must be at least 1 character')
    .max(100, 'First name must not exceed 100 characters'),
  last_name: Yup.string()
    .required('Last name is required')
    .min(1, 'Last name must be at least 1 character')
    .max(100, 'Last name must not exceed 100 characters'),
  email: Yup.string()
    .email('Must be a valid email')
    .max(254, 'Email must not exceed 254 characters'),
  phone_number: Yup.string()
    .max(50, 'Phone number must not exceed 50 characters'),
  job_title: Yup.string()
    .max(200, 'Job title must not exceed 200 characters'),
  linkedin: Yup.string()
    .url('Must be a valid URL')
    .max(500, 'LinkedIn URL must not exceed 500 characters'),
  account: Yup.object()
    .required('Account is required')
    .nullable(),
  standard_department_id: Yup.string()
    .required('Department is required'),
  notes: Yup.string()
    .max(2000, 'Notes must not exceed 2000 characters')
});

// ==============================|| BUILD INITIAL VALUES ||============================== //

const buildInitialValues = (contact) => {
  if (!contact) return {};
  
  return {
    first_name: contact.first_name || '',
    last_name: contact.last_name || '',
    email: contact.email || '',
    phone_number: contact.phone_number || '',
    job_title: contact.job_title || '',
    linkedin: contact.linkedin || '',
    account: contact.account || null,
    standard_department_id: contact.standard_department?.id || contact.standard_department_id || '',
    influence_level: contact.influence_level || '',
    has_buying_authority: contact.has_buying_authority || false,
    notes: contact.notes || ''
  };
};

// ==============================|| SANITIZE PAYLOAD ||============================== //

function sanitizePayload(values) {
  const payload = {};
  
  // Required fields
  payload.first_name = values.first_name.trim();
  payload.last_name = values.last_name.trim();
  
  // Account FK (required)
  if (values.account?.id) {
    payload.account_id = values.account.id;
  }
  
  // Optional string fields - send empty string to clear
  const optionalFields = ['email', 'phone_number', 'job_title', 'linkedin', 'notes'];
  optionalFields.forEach((field) => {
    const value = values[field];
    payload[field] = value ? value.trim() : '';
  });
  
  // Optional choice fields - send null to clear
  payload.standard_department_id = values.standard_department_id || null;
  payload.influence_level = values.influence_level || '';
  
  // Boolean field
  payload.has_buying_authority = values.has_buying_authority || false;
  
  return payload;
}

// ==============================|| FORM CONTACT EDIT ||============================== //

function FormContactEdit({ contact, contactId, closeModal }) {
  const [loading, setLoading] = useState(false);

  // Fetch fresh contact data
  const { contact: contactData, contactLoading } = useGetContact(contactId);
  const { influenceLevels, standardDepartments, choicesLoading } = useGetContactChoices();

  // Use fresh data if available, fallback to prop
  const currentContact = contactData || contact;

  const formik = useFormik({
    initialValues: buildInitialValues(currentContact),
    validationSchema: EditSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        setLoading(true);
        const payload = sanitizePayload(values);
        const result = await updateContact(contactId, payload);

        if (result.success) {
          displaySuccessSnackbar('Contact updated successfully');
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

  // Show loading state
  if (contactLoading || choicesLoading || !currentContact) {
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
        <DialogTitle>Edit Contact</DialogTitle>
        <Divider />
        
        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={2.5}>
            
            {/* ==================== ACCOUNT (Read-only) ==================== */}
            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel>Account</InputLabel>
                <TextField
                  fullWidth
                  value={currentContact?.account?.company_name || values.account?.company_name || ''}
                  disabled
                  InputProps={{
                    readOnly: true,
                    sx: { bgcolor: 'action.hover' }
                  }}
                />
              </Stack>
            </Grid>

            {/* ==================== IDENTITY ==================== */}
            <SectionTitle>Identity</SectionTitle>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="first_name">First Name *</InputLabel>
                <TextField
                  fullWidth
                  id="first_name"
                  placeholder="Enter first name"
                  {...getFieldProps('first_name')}
                  error={Boolean(touched.first_name && errors.first_name)}
                  helperText={touched.first_name && errors.first_name}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="last_name">Last Name *</InputLabel>
                <TextField
                  fullWidth
                  id="last_name"
                  placeholder="Enter last name"
                  {...getFieldProps('last_name')}
                  error={Boolean(touched.last_name && errors.last_name)}
                  helperText={touched.last_name && errors.last_name}
                />
              </Stack>
            </Grid>

            {/* ==================== CONTACT INFO ==================== */}
            <SectionTitle>Contact Information</SectionTitle>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="email">Email</InputLabel>
                <TextField
                  fullWidth
                  id="email"
                  type="email"
                  placeholder="email@company.com"
                  {...getFieldProps('email')}
                  error={Boolean(touched.email && errors.email)}
                  helperText={touched.email && errors.email}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="phone_number">Phone</InputLabel>
                <TextField
                  fullWidth
                  id="phone_number"
                  placeholder="+1 234 567 890"
                  {...getFieldProps('phone_number')}
                  error={Boolean(touched.phone_number && errors.phone_number)}
                  helperText={touched.phone_number && errors.phone_number}
                />
              </Stack>
            </Grid>

            {/* ==================== PROFESSIONAL INFO ==================== */}
            <SectionTitle>Professional Information</SectionTitle>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="job_title">Job Title</InputLabel>
                <TextField
                  fullWidth
                  id="job_title"
                  placeholder="e.g. Sales Director"
                  {...getFieldProps('job_title')}
                  error={Boolean(touched.job_title && errors.job_title)}
                  helperText={touched.job_title && errors.job_title}
                />
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="standard_department_id"required> Department</InputLabel>
                <FormControl fullWidth error={Boolean(touched.standard_department_id && errors.standard_department_id)}>
                  <Select
                    id="standard_department_id"
                    displayEmpty
                    value={values.standard_department_id}
                    onChange={(e) => setFieldValue('standard_department_id', e.target.value)}
                    onBlur={() => formik.setFieldTouched('standard_department_id', true)}
                  >
                    <MenuItem value="">
                      <em>Select department *</em>
                    </MenuItem>
                    {standardDepartments.map((dept) => (
                      <MenuItem key={dept.value} value={dept.value}>
                        {dept.label}
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.standard_department_id && errors.standard_department_id && (
                    <FormHelperText error>{errors.standard_department_id}</FormHelperText>
                  )}
                </FormControl>
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="linkedin">LinkedIn</InputLabel>
                <TextField
                  fullWidth
                  id="linkedin"
                  placeholder="https://linkedin.com/in/..."
                  {...getFieldProps('linkedin')}
                  error={Boolean(touched.linkedin && errors.linkedin)}
                  helperText={touched.linkedin && errors.linkedin}
                />
              </Stack>
            </Grid>

            {/* ==================== QUALIFICATION ==================== */}
            <SectionTitle>Qualification</SectionTitle>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="influence_level">Influence Level</InputLabel>
                <FormControl fullWidth error={Boolean(touched.influence_level && errors.influence_level)}>
                  <Select
                    id="influence_level"
                    displayEmpty
                    value={values.influence_level}
                    onChange={(e) => setFieldValue('influence_level', e.target.value)}
                  >
                    <MenuItem value="">
                      <em>Select influence level</em>
                    </MenuItem>
                    {influenceLevels.map((level) => (
                      <MenuItem key={level.value} value={level.value}>
                        {level.label}
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.influence_level && errors.influence_level && (
                    <FormHelperText>{errors.influence_level}</FormHelperText>
                  )}
                </FormControl>
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1} justifyContent="flex-end" sx={{ height: '100%', pb: 1 }}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={values.has_buying_authority}
                      onChange={(e) => setFieldValue('has_buying_authority', e.target.checked)}
                    />
                  }
                  label="Has Buying Authority"
                />
              </Stack>
            </Grid>

            {/* ==================== NOTES ==================== */}
            <SectionTitle>Notes</SectionTitle>

            <Grid item xs={12}>
              <Stack spacing={1}>
                <TextField
                  fullWidth
                  id="notes"
                  multiline
                  rows={3}
                  placeholder="Additional notes about this contact..."
                  {...getFieldProps('notes')}
                  error={Boolean(touched.notes && errors.notes)}
                  helperText={touched.notes && errors.notes}
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
                  {isSubmitting || loading ? 'Saving...' : 'Save Changes'}
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </DialogActions>
      </Form>
    </FormikProvider>
  );
}

FormContactEdit.propTypes = {
  contact: PropTypes.object,
  contactId: PropTypes.string.isRequired,
  closeModal: PropTypes.func
};

export default React.memo(FormContactEdit);