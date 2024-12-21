import PropTypes from 'prop-types';
import { useEffect, useState } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import FormControl from '@mui/material/FormControl';
import Grid from '@mui/material/Grid';
import FormHelperText from '@mui/material/FormHelperText';
import InputLabel from '@mui/material/InputLabel';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import OutlinedInput from '@mui/material/OutlinedInput';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// third-party
import _ from 'lodash';
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';
import PhoneInput from 'react-phone-input-2';
import 'react-phone-input-2/lib/material.css';

// project imports
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import { openSnackbar } from 'api/snackbar';
import { createAccount, updateAccount } from 'api/(crm)/account';

// Constants
const ACCOUNT_TYPES = [
  { value: 'CUSTOMER', label: 'Customer' },
  { value: 'PARTNER', label: 'Partner' },
  { value: 'SUPPLIER', label: 'Supplier' },
  { value: 'OTHER', label: 'Other' }
];

const ACCOUNT_CLASSIFICATIONS = [
  { value: 'ENTERPRISE', label: 'Enterprise' },
  { value: 'MID_MARKET', label: 'Mid Market' },
  { value: 'SMB', label: 'Small Business' }
];

const getInitialValues = (account) => {
  const newAccount = {
    company_name: '',
    industry: '',
    address: '',
    city: '',
    post_code: '',
    country: '',
    website: '',
    type: '',
    phone_number: '',
    number_of_employees: '',
    potential: '',
    classification: ''
  };

  if (account) {
    return _.merge({}, newAccount, account);
  }

  return newAccount;
};

// ==============================|| ACCOUNT ADD/EDIT FORM ||============================== //

export default function FormAccountAdd({ account, closeModal }) {
  const theme = useTheme();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(false);
  }, []);

  const AccountSchema = Yup.object().shape({
    company_name: Yup.string().max(255).required('Company name is required'),
    industry: Yup.string().max(100),
    address: Yup.string(),
    city: Yup.string().max(50).required('City is required'),
    post_code: Yup.string().max(20),
    country: Yup.string().max(50).required('Country is required'),
    website: Yup.string().url('Must be a valid URL'),
    type: Yup.string().max(50),
    phone_number: Yup.string(),
    number_of_employees: Yup.number().positive('Must be a positive number').integer('Must be an integer'),
    potential: Yup.number().positive('Must be a positive number'),
    classification: Yup.string().max(50)
  });

  const formik = useFormik({
    initialValues: getInitialValues(account),
    validationSchema: AccountSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        if (account) {
          await updateAccount(account.id, values);
          openSnackbar({
            open: true,
            message: 'Account updated successfully.',
            variant: 'alert',
            alert: {
              color: 'success'
            }
          });
        } else {
          await createAccount(values);
          openSnackbar({
            open: true,
            message: 'Account created successfully.',
            variant: 'alert',
            alert: {
              color: 'success'
            }
          });
        }
        setSubmitting(false);
        closeModal();
      } catch (error) {
        console.error(error);
        openSnackbar({
          open: true,
          message: 'Error occurred.',
          variant: 'alert',
          alert: {
            color: 'error'
          }
        });
        setSubmitting(false);
      }
    }
  });

  const { errors, touched, handleSubmit, isSubmitting, getFieldProps, setFieldValue } = formik;

  if (loading)
    return (
      <Box sx={{ p: 5 }}>
        <Stack direction="row" justifyContent="center">
          <CircularWithPath />
        </Stack>
      </Box>
    );

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        <DialogTitle>{account ? 'Edit Account' : 'New Account'}</DialogTitle>
        <Divider />
        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="company-name">Company Name*</InputLabel>
                <TextField
                  fullWidth
                  id="company-name"
                  placeholder="Enter Company Name"
                  {...getFieldProps('company_name')}
                  error={Boolean(touched.company_name && errors.company_name)}
                  helperText={touched.company_name && errors.company_name}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="industry">Industry</InputLabel>
                <TextField
                  fullWidth
                  id="industry"
                  placeholder="Enter Industry"
                  {...getFieldProps('industry')}
                  error={Boolean(touched.industry && errors.industry)}
                  helperText={touched.industry && errors.industry}
                />
              </Stack>
            </Grid>
            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="address">Address</InputLabel>
                <TextField
                  fullWidth
                  id="address"
                  multiline
                  rows={3}
                  placeholder="Enter Address"
                  {...getFieldProps('address')}
                  error={Boolean(touched.address && errors.address)}
                  helperText={touched.address && errors.address}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={4}>
              <Stack spacing={1}>
                <InputLabel htmlFor="city">City*</InputLabel>
                <TextField
                  fullWidth
                  id="city"
                  placeholder="Enter City"
                  {...getFieldProps('city')}
                  error={Boolean(touched.city && errors.city)}
                  helperText={touched.city && errors.city}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={4}>
              <Stack spacing={1}>
                <InputLabel htmlFor="post-code">Post Code</InputLabel>
                <TextField
                  fullWidth
                  id="post-code"
                  placeholder="Enter Post Code"
                  {...getFieldProps('post_code')}
                  error={Boolean(touched.post_code && errors.post_code)}
                  helperText={touched.post_code && errors.post_code}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={4}>
              <Stack spacing={1}>
                <InputLabel htmlFor="country">Country*</InputLabel>
                <TextField
                  fullWidth
                  id="country"
                  placeholder="Enter Country"
                  {...getFieldProps('country')}
                  error={Boolean(touched.country && errors.country)}
                  helperText={touched.country && errors.country}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="website">Website</InputLabel>
                <TextField
                  fullWidth
                  id="website"
                  placeholder="Enter Website URL"
                  {...getFieldProps('website')}
                  error={Boolean(touched.website && errors.website)}
                  helperText={touched.website && errors.website}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="phone-number">Phone Number</InputLabel>
                <PhoneInput
                  country={'us'}
                  value={formik.values.phone_number}
                  onChange={(phone) => setFieldValue('phone_number', phone)}
                  inputStyle={{ width: '100%' }}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="account-type">Account Type</InputLabel>
                <FormControl fullWidth>
                  <Select
                    id="account-type"
                    {...getFieldProps('type')}
                    error={Boolean(touched.type && errors.type)}
                  >
                    {ACCOUNT_TYPES.map((type) => (
                      <MenuItem key={type.value} value={type.value}>
                        <ListItemText primary={type.label} />
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {touched.type && errors.type && (
                  <FormHelperText error>{errors.type}</FormHelperText>
                )}
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="classification">Classification</InputLabel>
                <FormControl fullWidth>
                  <Select
                    id="classification"
                    {...getFieldProps('classification')}
                    error={Boolean(touched.classification && errors.classification)}
                  >
                    {ACCOUNT_CLASSIFICATIONS.map((classification) => (
                      <MenuItem key={classification.value} value={classification.value}>
                        <ListItemText primary={classification.label} />
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
                {touched.classification && errors.classification && (
                  <FormHelperText error>{errors.classification}</FormHelperText>
                )}
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="employees">Number of Employees</InputLabel>
                <TextField
                  fullWidth
                  type="number"
                  id="employees"
                  placeholder="Enter Number of Employees"
                  {...getFieldProps('number_of_employees')}
                  error={Boolean(touched.number_of_employees && errors.number_of_employees)}
                  helperText={touched.number_of_employees && errors.number_of_employees}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="potential">Potential Revenue</InputLabel>
                <TextField
                  fullWidth
                  type="number"
                  id="potential"
                  placeholder="Enter Potential Revenue"
                  {...getFieldProps('potential')}
                  error={Boolean(touched.potential && errors.potential)}
                  helperText={touched.potential && errors.potential}
                />
              </Stack>
            </Grid>
          </Grid>
        </DialogContent>
        <Divider />
        <DialogActions sx={{ p: 2.5 }}>
          <Grid container justifyContent="flex-end" spacing={2}>
            <Grid item>
              <Button color="error" onClick={closeModal}>
                Cancel
              </Button>
            </Grid>
            <Grid item>
              <Button type="submit" variant="contained" disabled={isSubmitting}>
                {account ? 'Save Changes' : 'Create Account'}
              </Button>
            </Grid>
          </Grid>
        </DialogActions>
      </Form>
    </FormikProvider>
  );
}

FormAccountAdd.propTypes = {
  account: PropTypes.object,
  closeModal: PropTypes.func.isRequired
};