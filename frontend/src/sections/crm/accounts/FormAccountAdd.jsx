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
import Autocomplete from '@mui/material/Autocomplete';
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
import { createAccount, updateAccount, getAccountTypes } from 'api/(crm)/account';
import countries from 'data/countries';
import industries from 'data/industries';


// Constants (dynamically fetched)
let ACCOUNT_TYPES = [];
let ACCOUNT_CLASSIFICATIONS = [];

// // Fetch account types and classifications from the API
// (async () => {
//   try {
//     const { types, classifications } = await getAccountTypes();
//     ACCOUNT_TYPES = types;
//     ACCOUNT_CLASSIFICATIONS = classifications;
//   } catch (error) {
//     console.error('Error fetching account types and classifications:', error);

//   }
// })();


const getInitialValues = (accounts) => {
  if (!accounts?.length || accounts.length === 1) {
    const account = accounts?.[0];
    return {
      company_name: account?.company_name || '',
      industry: account?.industry || '',
      address: account?.address || '',
      city: account?.city || '',
      post_code: account?.post_code || '',
      country: account?.country || '',
      website: account?.website || '',
      phone_number: account?.phone_number || '',
      type: account?.type || '',
      classification: account?.classification || '',
      number_of_employees: account?.number_of_employees || '',
      potential: account?.potential || '',
    };
  }

  return {
    company_name: '',
    industry: '',
    address: '',
    city: '',
    post_code: '',
    country: '',
    website: '',
    phone_number: '',
    type: '',
    classification: '',
    number_of_employees: '',
    potential: '',
  };
};

// ==============================|| ACCOUNT ADD/EDIT FORM ||============================== //

export default function FormAccountAdd({ accounts = [], closeModal, onSuccess }) {
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initializeForm = async () => {
      try {
        const { types, classifications } = await getAccountTypes();
        ACCOUNT_TYPES = types;
        ACCOUNT_CLASSIFICATIONS = classifications;
        setLoading(false);
      } catch (error) {
        console.error('Error initializing form:', error);
        setLoading(false);
      }
    };

    initializeForm();
  }, []);

  const multipleAccounts = accounts.length > 1;

  const AccountSchema = Yup.object().shape(
    multipleAccounts ? {
      industry: Yup.string()
      .max(100)
      .test('is-valid-industry', 'You must choose a valid industry', (value) => industries.some((industry) => industry === value)),
    } : {    
    company_name: Yup.string().max(255).required('Company name is required'),
    industry: Yup.string()
      .max(100)
      .test('is-valid-industry', 'You must choose a valid industry', (value) => industries.some((industry) => industry === value)),
    address: Yup.string().max(255),
    city: Yup.string().max(50).required('City is required'),
    post_code: Yup.string().max(15),
    country: Yup.string()
      .max(50).required('Country is required')
      .test('is-valid-country', 'Invalid country', (value) => 
        countries.some((country) => country.label === value)
      ),}
    // number_of_employees: Yup.number().positive('Must be a positive number').integer('Must be an integer'),
    // potential: Yup.number().positive('Must be a positive number'),
  );

  const formik = useFormik({
    initialValues: getInitialValues(accounts),
    validationSchema: AccountSchema,
    enableReinitialize: false,
    onSubmit: async (values, { setSubmitting }) => {
      try {
        if (multipleAccounts) {
          const batchValues = {
            industry: values.industry || undefined,
            type: values.type || undefined,
            classification: values.classification || undefined
          };

          await Promise.all(accounts.map(account => 
            updateAccount(account.id, batchValues, true)
          ));
          
          openSnackbar({
            open: true,
            message: `${accounts.length} accounts updated successfully.`,
            variant: 'alert',
            alert: { color: 'success' }
          });
        } else if (accounts[0]) {
          await updateAccount(accounts[0].id, values, false);
          openSnackbar({
            open: true,
            message: 'Account updated successfully.',
            variant: 'alert',
            alert: { color: 'success' }
          });
        } else {
          await createAccount(values);
          openSnackbar({
            open: true,
            message: 'Account created successfully.',
            variant: 'alert',
            alert: { color: 'success' }
          });
        }
        
        setSubmitting(false);
        closeModal();
        onSuccess();
      } catch (error) {
        console.error(error);
        const errorMessage = error.response?.data?.message || error.response?.data?.error || 'An unexpected error occurred';
        openSnackbar({
          open: true,
          message: errorMessage,
          variant: 'alert',
          alert: { color: 'error' }
        });
        setSubmitting(false);
      }
    }
  });

  const { values, errors, touched, handleSubmit, isSubmitting, getFieldProps, setFieldValue } = formik;

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
      <Form autoComplete="off" noValidate onSubmit={formik.handleSubmit}>
        <DialogTitle>
          {multipleAccounts ? 'Batch Edit Accounts' : (accounts[0] ? 'Edit Account' : 'New Account')}
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="company-name">Company Name*</InputLabel>
                <TextField
                  fullWidth
                  disabled={multipleAccounts}
                  id="company-name"
                  placeholder="Enter Company Name"
                  {...getFieldProps('company_name')}
                  value={values.company_name.toUpperCase()} // Ensure value is uppercase
                  onChange={(e) => setFieldValue('company_name', e.target.value.toUpperCase())} // Transform input to uppercase
                  error={Boolean(touched.company_name && errors.company_name)}
                  helperText={touched.company_name && errors.company_name}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="industry">Industry</InputLabel>
                <Autocomplete
                options={industries}
                getOptionLabel={(option) => option}
                defaultValue={accounts[0]?.industry || null}
                onChange={(event, value) => setFieldValue('industry', value)}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    fullWidth
                    placeholder="Industry"
                    error={Boolean(touched.industry && errors.industry)}
                    helperText={touched.industry && errors.industry}
                  />
                )}
                inputValue={values.industry}
                onInputChange={(event, value) => setFieldValue('industry', value)}
                />
              </Stack>
            </Grid>
            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="address">Address</InputLabel>
                <TextField
                  fullWidth
                  disabled={multipleAccounts}
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
                  disabled={multipleAccounts}
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
                  disabled={multipleAccounts}
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
              <Autocomplete
                options={countries}
                disabled={multipleAccounts}
                getOptionLabel={(option) => option.label}
                defaultValue={countries.find((country) => country.label === accounts[0]?.country) || null}
                onChange={(event, value) => setFieldValue('country', value?.label || '')}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    fullWidth
                    placeholder="Country"
                    error={Boolean(touched.country && errors.country)}
                    helperText={touched.country && errors.country}
                  />
                )}
                inputValue={values.country}
                onInputChange={(event, value) => setFieldValue('country', value)}
              />
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="website">Website</InputLabel>
                <TextField
                  fullWidth
                  disabled={multipleAccounts}
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
                  disabled={multipleAccounts}
                  value={formik.values.phone_number}
                  onChange={(phone) => {
                    const formattedPhone = phone.startsWith('+') ? phone : `+${phone}`;
                    setFieldValue('phone_number',formattedPhone)}
                  }
                  inputStyle={{ width: '100%' }}
                  inputProps={{
                    required: true,
                  }}
                />
              </Stack>
            </Grid>
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="account-type">Account Type</InputLabel>
                <FormControl fullWidth>
                  <Select
                    id="account-type"
                    value={values.type || ''}
                    onChange={(event) => setFieldValue('type', event.target.value)}
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
                  value={values.classification || ''}
                  onChange={(event) => setFieldValue('classification', event.target.value)}
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
                  disabled={multipleAccounts}
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
                  disabled={multipleAccounts}
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
                {multipleAccounts ? 'Update Selected Accounts' : (accounts[0] ? 'Save Changes' : 'Create Account')}
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
  closeModal: PropTypes.func.isRequired,
  onSuccess: PropTypes.func
};


// import PropTypes from 'prop-types';
// import { useEffect, useState } from 'react';

// // material-ui
// import { useTheme } from '@mui/material/styles';
// import Box from '@mui/material/Box';
// import Button from '@mui/material/Button';
// import DialogActions from '@mui/material/DialogActions';
// import DialogContent from '@mui/material/DialogContent';
// import DialogTitle from '@mui/material/DialogTitle';
// import Divider from '@mui/material/Divider';
// import FormControl from '@mui/material/FormControl';
// import Grid from '@mui/material/Grid';
// import FormHelperText from '@mui/material/FormHelperText';
// import InputLabel from '@mui/material/InputLabel';
// import Autocomplete from '@mui/material/Autocomplete';
// import ListItemText from '@mui/material/ListItemText';
// import MenuItem from '@mui/material/MenuItem';
// import OutlinedInput from '@mui/material/OutlinedInput';
// import Select from '@mui/material/Select';
// import Stack from '@mui/material/Stack';
// import TextField from '@mui/material/TextField';
// import Typography from '@mui/material/Typography';

// // third-party
// import _ from 'lodash';
// import * as Yup from 'yup';
// import { useFormik, Form, FormikProvider } from 'formik';
// import PhoneInput from 'react-phone-input-2';
// import 'react-phone-input-2/lib/material.css';

// // project imports
// import CircularWithPath from 'components/@extended/progress/CircularWithPath';
// import { openSnackbar } from 'api/snackbar';
// import { createAccount, updateAccount, getAccountTypes } from 'api/(crm)/account';
// import countries from 'data/countries';
// import industries from 'data/industries';


// // Constants (dynamically fetched)
// let ACCOUNT_TYPES = [];
// let ACCOUNT_CLASSIFICATIONS = [];

// // Fetch account types and classifications from the API
// (async () => {
//   try {
//     const { types, classifications } = await getAccountTypes();
//     ACCOUNT_TYPES = types;
//     ACCOUNT_CLASSIFICATIONS = classifications;
//   } catch (error) {
//     console.error('Error fetching account types and classifications:', error);

//   }
// })();


// // ==============================|| ACCOUNT ADD/EDIT FORM ||============================== //

// export default function FormAccountAdd({ accounts, closeModal, onSuccess }) {
//   const theme = useTheme();
//   const [loading, setLoading] = useState(true);
//   const [accountTypes, setAccountTypes] = useState([]);
//   const [classifications, setClassifications] = useState([]);

//   useEffect(() => {
//     setLoading(false);
//     setAccountTypes(ACCOUNT_TYPES);
//     setClassifications(ACCOUNT_CLASSIFICATIONS);
//     console.log('Accounts Modal:', accounts);
//   }, []);

//   const multipleAccounts = accounts.length > 1;

//   const getInitialValues = (accounts) => {
//     if (accounts.length === 0) {
//       return {
//         company_name: '',
//         industry: '',
//         type: '',
//         classification: '',
//         address: '',
//         city: '',
//         post_code: '',
//         country: '',
//         website: '',
//         phone_number: '',
//         number_of_employees: '',
//         potential: ''
//       };
//     }
  
//     if (multipleAccounts) {
//       // For multiple accounts, only initialize batch-editable fields
//       return {
//         industry: '',
//         type: '',
//         classification: ''
//       };
//     }
  
//     // For single account, return all fields
//     return {
//       company_name: accounts[0]?.company_name || '',
//       industry: accounts[0]?.industry || '',
//       type: accounts[0]?.type || '',
//       classification: accounts[0]?.classification || '',
//       address: accounts[0]?.address || '',
//       city: accounts[0]?.city || '',
//       post_code: accounts[0]?.post_code || '',
//       country: accounts[0]?.country || '',
//       website: accounts[0]?.website || '',
//       phone_number: accounts[0]?.phone_number || '',
//       number_of_employees: accounts[0]?.number_of_employees || '',
//       potential: accounts[0]?.potential || ''
//     };
//   }

//   const AccountSchema = Yup.object().shape({
//     ...(multipleAccounts ? {
//       industry: Yup.string()
//         .test('is-valid-industry', 'You must choose a valid industry', 
//           (value) => !value || industries.some((industry) => industry === value)),
//       type: Yup.string(),
//       classification: Yup.string()
//     } : {
//       company_name: Yup.string().max(255).required('Company name is required'),
//       industry: Yup.string()
//         .max(100)
//         .test('is-valid-industry', 'You must choose a valid industry', 
//           (value) => !value || industries.some((industry) => industry === value)),
//       address: Yup.string().max(255),
//       city: Yup.string().max(50).required('City is required'),
//       post_code: Yup.string().max(15),
//       country: Yup.string()
//         .max(50)
//         .required('Country is required')
//         .test('is-valid-country', 'Invalid country', 
//           (value) => !value || countries.some((country) => country.label === value)),
//     })
//   });

//   const formik = useFormik({
//     initialValues: getInitialValues(accounts),
//     validationSchema: AccountSchema,
//     enableReinitialize: true,
//     onSubmit: async (values, { setSubmitting }) => {
//       try {
//         if (multipleAccounts) {
//           // Only update batch-editable fields
//           const batchValues = {
//             industry: values.industry || undefined,
//             type: values.type || undefined,
//             classification: values.classification || undefined
//           };

//           await Promise.all(accounts.map((account) => 
//             updateAccount(account.id, batchValues)
//           ));
          
//           openSnackbar({
//             open: true,
//             message: `${accounts.length} Accounts updated successfully.`,
//             variant: 'alert',
//             alert: { color: 'success' }
//           });
//         } else {
//           // Single account update or create
//           if (accounts.length === 1) {
//             await updateAccount(accounts[0].id, values);
//             openSnackbar({
//               open: true,
//               message: 'Account updated successfully.',
//               variant: 'alert',
//               alert: { color: 'success' }
//             });
//           } else {
//             await createAccount(values);
//             openSnackbar({
//               open: true,
//               message: 'Account created successfully.',
//               variant: 'alert',
//               alert: { color: 'success' }
//             });
//           }
//         }
//         setSubmitting(false);
//         closeModal();
//         onSuccess();
//       } catch (error) {
//         console.error(error);
//         const errorMessage = error.response?.data?.message || 
//           error.response?.data?.error || 
//           'An unexpected error occurred';
        
//         openSnackbar({
//           open: true,
//           message: errorMessage,
//           variant: 'alert',
//           alert: { color: 'error' }
//         });
//         setSubmitting(false);
//       }
//     }
//   });

//   const { values, errors, touched, handleSubmit, isSubmitting, getFieldProps, setFieldValue } = formik;

//   if (loading)
//     return (
//       <Box sx={{ p: 5 }}>
//         <Stack direction="row" justifyContent="center">
//           <CircularWithPath />
//         </Stack>
//       </Box>
//     );

//     return (
//       <FormikProvider value={formik}>
//         <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
//           <DialogTitle>
//             {multipleAccounts ? 'Batch Edit Accounts' : (accounts.length === 1 ? 'Edit Account' : 'Create Account')}
//           </DialogTitle>
//           <Divider />
//           <DialogContent sx={{ p: 2.5 }}>
//             <Grid container spacing={3}>
//               {/* Fields that are always disabled in batch mode */}
//               {!multipleAccounts && (
//                 <>
//                   <Grid item xs={12} md={6}>
//                     <Stack spacing={1}>
//                       <InputLabel htmlFor="company-name">Company Name*</InputLabel>
//                       <TextField
//                         fullWidth
//                         id="company-name"
//                         placeholder="Enter Company Name"
//                         {...getFieldProps('company_name')}
//                         error={Boolean(touched.company_name && errors.company_name)}
//                         helperText={touched.company_name && errors.company_name}
//                       />
//                     </Stack>
//                   </Grid>
//                   {/* Add other single-edit only fields here */}
//                 </>
//               )}
  
//               {/* Fields that are always available */}
//               <Grid item xs={12} md={6}>
//                 <Stack spacing={1}>
//                   <InputLabel htmlFor="industry">Industry</InputLabel>
//                   <TextField
//                     fullWidth
//                     id="industry"
//                     select
//                     placeholder="Select Industry"
//                     {...getFieldProps('industry')}
//                     error={Boolean(touched.industry && errors.industry)}
//                     helperText={touched.industry && errors.industry}
//                   >
//                     {industries.map((option) => (
//                       <MenuItem key={option} value={option}>
//                         {option}
//                       </MenuItem>
//                     ))}
//                   </TextField>
//                 </Stack>
//               </Grid>
  
//               <Grid item xs={12} md={6}>
//                 <Stack spacing={1}>
//                   <InputLabel htmlFor="type">Type</InputLabel>
//                   <TextField
//                     fullWidth
//                     id="type"
//                     select
//                     placeholder="Select Type"
//                     {...getFieldProps('type')}
//                   >
//                     {accountTypes.map((option) => (
//                       <MenuItem key={option} value={option}>
//                         {option}
//                       </MenuItem>
//                     ))}
//                   </TextField>
//                 </Stack>
//               </Grid>
  
//               <Grid item xs={12} md={6}>
//                 <Stack spacing={1}>
//                   <InputLabel htmlFor="classification">Classification</InputLabel>
//                   <TextField
//                     fullWidth
//                     id="classification"
//                     select
//                     placeholder="Select Classification"
//                     {...getFieldProps('classification')}
//                   >
//                     {classifications.map((option) => (
//                       <MenuItem key={option} value={option}>
//                         {option}
//                       </MenuItem>
//                     ))}
//                   </TextField>
//                 </Stack>
//               </Grid>
//             </Grid>
//           </DialogContent>
//           <Divider />
//           <DialogActions sx={{ p: 2.5 }}>
//             <Grid container justifyContent="flex-end" spacing={2}>
//               <Grid item>
//                 <Button color="error" onClick={closeModal}>
//                   Cancel
//                 </Button>
//               </Grid>
//               <Grid item>
//                 <Button type="submit" variant="contained" disabled={isSubmitting}>
//                   {multipleAccounts ? 'Update Selected Accounts' : 'Save Changes'}
//                 </Button>
//               </Grid>
//             </Grid>
//           </DialogActions>
//         </Form>
//       </FormikProvider>
//     );
//   }

// FormAccountAdd.propTypes = {
//   accounts: PropTypes.arrayOf(PropTypes.object),
//   closeModal: PropTypes.func.isRequired,
//   onSuccess: PropTypes.func,
// };
