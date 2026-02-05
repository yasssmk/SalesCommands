// frontend/src/sections/accounts/activities/components/InlineContactForm.jsx
/**
 * Inline Contact Form Component
 * 
 * Quick-add contact form with Formik validation.
 */

'use client';

import PropTypes from 'prop-types';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Grid from '@mui/material/Grid';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// third-party
import { useFormik } from 'formik';
import * as Yup from 'yup';

// icons
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// project imports
import { useGetContactChoices } from 'api/businessData/contacts';

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  first_name: Yup.string()
    .required('First name is required')
    .max(100, 'First name must be at most 100 characters'),
  last_name: Yup.string()
    .required('Last name is required')
    .max(100, 'Last name must be at most 100 characters'),
  email: Yup.string()
    .email('Invalid email format')
    .max(254, 'Email must be at most 254 characters')
    .nullable(),
  phone_number: Yup.string()
    .max(30, 'Phone number must be at most 30 characters')
    .nullable(),
  job_title: Yup.string()
    .max(150, 'Job title must be at most 150 characters')
    .nullable(),
  standard_department_id: Yup.string()
    .nullable()
});

// ==============================|| INLINE CONTACT FORM ||============================== //

export default function InlineContactForm({ onSave, onCancel }) {
  // Fetch standard departments
  const { standardDepartments = [], choicesLoading } = useGetContactChoices();

  const formik = useFormik({
    initialValues: {
      first_name: '',
      last_name: '',
      email: '',
      phone_number: '',
      job_title: '',
      standard_department_id: ''
    },
    validationSchema,
    onSubmit: (values) => {
      onSave({
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        email: values.email.trim() || null,
        phone_number: values.phone_number.trim() || null,
        job_title: values.job_title.trim() || null,
        standard_department_id: values.standard_department_id || null
      });
    }
  });

  const { values, errors, touched, handleChange, handleBlur, handleSubmit } = formik;

  return (
    <Stack spacing={2} sx={{ mt: 1 }}>
      <Typography variant="body2" color="text.secondary">
        Quick add a new contact
      </Typography>
      <Grid container spacing={2.5} sx={{ ml: '-20px !important', width: 'calc(100% + 20px)' }}>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            id="first_name"
            name="first_name"
            value={values.first_name}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="First name *"
            error={Boolean(touched.first_name && errors.first_name)}
            helperText={touched.first_name && errors.first_name}
            autoFocus
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            id="last_name"
            name="last_name"
            value={values.last_name}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Last name *"
            error={Boolean(touched.last_name && errors.last_name)}
            helperText={touched.last_name && errors.last_name}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            id="email"
            name="email"
            type="email"
            value={values.email}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Email"
            error={Boolean(touched.email && errors.email)}
            helperText={touched.email && errors.email}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            id="phone_number"
            name="phone_number"
            value={values.phone_number}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Phone number"
            error={Boolean(touched.phone_number && errors.phone_number)}
            helperText={touched.phone_number && errors.phone_number}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            id="job_title"
            name="job_title"
            value={values.job_title}
            onChange={handleChange}
            onBlur={handleBlur}
            placeholder="Job title"
            error={Boolean(touched.job_title && errors.job_title)}
            helperText={touched.job_title && errors.job_title}
          />
        </Grid>
        <Grid item xs={12} sm={6}>
          <Select
            fullWidth
            id="standard_department_id"
            name="standard_department_id"
            value={values.standard_department_id}
            onChange={handleChange}
            onBlur={handleBlur}
            displayEmpty
            disabled={choicesLoading}
            endAdornment={choicesLoading ? <CircularProgress size={20} sx={{ mr: 2 }} /> : null}
          >
            <MenuItem value="">
              <em>Select department</em>
            </MenuItem>
            {standardDepartments.map((dept) => (
              <MenuItem key={dept.value} value={dept.value}>
                {dept.label}
              </MenuItem>
            ))}
          </Select>
        </Grid>
      </Grid>
      <Stack direction="row" spacing={1} justifyContent="flex-end">
        <Button type="button" size="small" onClick={onCancel} startIcon={<CloseOutlined />}>
          Cancel
        </Button>
        <Button type="button" size="small" variant="contained" onClick={handleSubmit}>
          Add Contact
        </Button>
      </Stack>
    </Stack>
  );
}

InlineContactForm.propTypes = {
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired
};