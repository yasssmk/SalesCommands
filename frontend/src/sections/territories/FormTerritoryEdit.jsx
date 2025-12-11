// frontend/src/sections/territories/FormTerritoryEdit.jsx

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
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// project imports
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import { displaySuccessSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formErrorHandler';
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';

// api
import { updateTerritory, TERRITORY_TYPES } from 'api/territories/territories';
import { useGetAccountChoices } from 'api/admin/accounts';

// ==============================|| SECTION TITLE ||============================== //

const SectionTitle = ({ children }) => (
  <Grid item xs={12}>
    <Typography variant="subtitle2" color="text.secondary" sx={{ 
      mt: 2, 
      mb: 1, 
      textTransform: 'uppercase', 
      fontSize: '0.75rem',
      fontWeight: 600,
      letterSpacing: '0.5px'
    }}>
      {children}
    </Typography>
  </Grid>
);

SectionTitle.propTypes = { children: PropTypes.node };

// ==============================|| VALIDATION SCHEMA ||============================== //

const EditSchema = Yup.object().shape({
  name: Yup.string()
    .required('Territory name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(100, 'Name must not exceed 100 characters'),
  description: Yup.string()
    .max(500, 'Description must not exceed 500 characters'),
  type: Yup.string()
    .required('Territory type is required')
    .oneOf(Object.values(TERRITORY_TYPES), 'Invalid territory type')
});

// ==============================|| INITIAL VALUES ||============================== //

const buildInitialValues = (territory) => ({
  name: territory?.name || '',
  description: territory?.description || '',
  type: territory?.type || TERRITORY_TYPES.ACCOUNT,
  // Filter definition fields from existing territory
  filter_type: territory?.filter_definition?.type || '',
  filter_classification: territory?.filter_definition?.classification || '',
  filter_industry: territory?.filter_definition?.industry || '',
  filter_country: territory?.filter_definition?.country || '',
  // Owner scope fields
  filter_account_scope: territory?.filter_definition?.account_scope || '',
  filter_account_owner: territory?.filter_definition?.account_owner || null
});

// ==============================|| FORM TERRITORY EDIT ||============================== //

/**
 * Form for editing an existing territory
 * 
 * Features:
 * - Pre-filled values from territory
 * - Name and description editing
 * - Type selection (read-only for system territories)
 * - Filter definition editing
 * 
 * @param {Object} territory - Territory object to edit
 * @param {Function} closeModal - Function to close the modal
 */
function FormTerritoryEdit({ territory, closeModal }) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Fetch choices from accounts
  const { types, classifications, industries, countries, choicesLoading } = useGetAccountChoices();

  // ==============================|| FORMIK SETUP ||============================== //

  const formik = useFormik({
    initialValues: buildInitialValues(territory),
    validationSchema: EditSchema,
    enableReinitialize: true,
    onSubmit: async (values) => {
      setIsSubmitting(true);
      
      try {
        // Build filter_definition from filter fields
        const filter_definition = {};
        if (values.filter_type) filter_definition.type = values.filter_type;
        if (values.filter_classification) filter_definition.classification = values.filter_classification;
        if (values.filter_industry) filter_definition.industry = values.filter_industry;
        if (values.filter_country) filter_definition.country = values.filter_country;

        // Owner scope - only one of account_scope or account_owner should be set
        if (values.filter_account_scope && values.filter_account_scope !== 'other') {
          filter_definition.account_scope = values.filter_account_scope;
        }
        if (values.filter_account_owner?.id) {
          filter_definition.account_owner = values.filter_account_owner.id;
}

        const payload = {
          name: values.name.trim(),
          description: values.description?.trim() || null,
          type: values.type,
          filter_definition
        };
        
        const result = await updateTerritory(territory.id, payload);
        
        if (result.success) {
          displaySuccessSnackbar('Territory updated successfully');
          closeModal?.();
        } else {
          handleFormikError(result, formik);
        }
      } catch (err) {
        handleFormikError(err, formik);
      } finally {
        setIsSubmitting(false);
      }
    }
  });

  const { errors, touched, handleSubmit, getFieldProps, values, setFieldValue } = formik;

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

  // ==============================|| RENDER ||============================== //

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        <DialogTitle>
          Edit Territory
          {territory?.is_system && (
            <Typography variant="caption" color="warning.main" sx={{ ml: 1 }}>
              (System territory - limited editing)
            </Typography>
          )}
        </DialogTitle>
        <Divider />
        
        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={2.5}>
            
            {/* ==================== IDENTITY ==================== */}
            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="name">Territory Name *</InputLabel>
                <TextField
                  fullWidth
                  id="name"
                  placeholder="Enter territory name"
                  {...getFieldProps('name')}
                  error={Boolean(touched.name && errors.name)}
                  helperText={touched.name && errors.name}
                  disabled={territory?.is_system}
                />
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="description">Description</InputLabel>
                <TextField
                  fullWidth
                  id="description"
                  placeholder="Enter description"
                  multiline
                  rows={2}
                  {...getFieldProps('description')}
                  error={Boolean(touched.description && errors.description)}
                  helperText={touched.description && errors.description}
                />
              </Stack>
            </Grid>

            {/* ==================== TYPE ==================== */}
            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="type">Territory Type *</InputLabel>
                <FormControl fullWidth error={Boolean(touched.type && errors.type)}>
                  <Select
                    id="type"
                    displayEmpty
                    value={values.type}
                    onChange={(e) => setFieldValue('type', e.target.value)}
                    disabled={territory?.is_system}
                  >
                    <MenuItem value={TERRITORY_TYPES.ACCOUNT}>Account-based</MenuItem>
                    <MenuItem value={TERRITORY_TYPES.CONTACT} disabled>
                      Contact-based (coming soon)
                    </MenuItem>
                  </Select>
                  {touched.type && errors.type && (
                    <FormHelperText>{errors.type}</FormHelperText>
                  )}
                </FormControl>
              </Stack>
            </Grid>

            {/* ==================== ACCOUNT FILTERS ==================== */}
            <SectionTitle>Account Filters</SectionTitle>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="filter_type">Account Type</InputLabel>
                <FormControl fullWidth>
                  <Select
                    id="filter_type"
                    displayEmpty
                    value={values.filter_type}
                    onChange={(e) => setFieldValue('filter_type', e.target.value)}
                    disabled={territory?.is_system}
                  >
                    <MenuItem value="">
                      <em>All types</em>
                    </MenuItem>
                    {types.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="filter_classification">Classification</InputLabel>
                <FormControl fullWidth>
                  <Select
                    id="filter_classification"
                    displayEmpty
                    value={values.filter_classification}
                    onChange={(e) => setFieldValue('filter_classification', e.target.value)}
                    disabled={territory?.is_system}
                  >
                    <MenuItem value="">
                      <em>All classifications</em>
                    </MenuItem>
                    {classifications.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="filter_industry">Industry</InputLabel>
                <FormControl fullWidth>
                  <Select
                    id="filter_industry"
                    displayEmpty
                    value={values.filter_industry}
                    onChange={(e) => setFieldValue('filter_industry', e.target.value)}
                    disabled={territory?.is_system}
                  >
                    <MenuItem value="">
                      <em>All industries</em>
                    </MenuItem>
                    {industries.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Stack>
            </Grid>

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="filter_country">Country</InputLabel>
                <FormControl fullWidth>
                  <Select
                    id="filter_country"
                    displayEmpty
                    value={values.filter_country}
                    onChange={(e) => setFieldValue('filter_country', e.target.value)}
                    disabled={territory?.is_system}
                  >
                    <MenuItem value="">
                      <em>All countries</em>
                    </MenuItem>
                    {countries.map((option) => (
                      <MenuItem key={option.value} value={option.value}>
                        {option.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Stack>
            </Grid>

            {/* ==================== OWNER SCOPE ==================== */}
            <SectionTitle>Account Owner</SectionTitle>
            
            <Grid item xs={12}>
              <FormControl component="fieldset" fullWidth disabled={territory?.is_system}>
                <RadioGroup
                  row
                  value={values.filter_account_scope || (values.filter_account_owner?.id ? 'other' : '')}
                  onChange={(e) => {
                    const newScope = e.target.value;
                    setFieldValue('filter_account_scope', newScope);
                    // Clear account_owner when switching away from 'other'
                    if (newScope !== 'other') {
                      setFieldValue('filter_account_owner', null);
                    }
                  }}
                  sx={{ gap: 2 }}
                >
                  <FormControlLabel 
                    value="" 
                    control={<Radio size="small" />} 
                    label="All" 
                  />
                  <FormControlLabel 
                    value="mine" 
                    control={<Radio size="small" />} 
                    label="Mine" 
                  />
                  <FormControlLabel 
                    value="team" 
                    control={<Radio size="small" />} 
                    label="My Team" 
                  />
                  <FormControlLabel 
                    value="other" 
                    control={<Radio size="small" />} 
                    label="Specific user" 
                  />
                </RadioGroup>
              </FormControl>
            </Grid>
            
            {/* User Select - only enabled when 'other' is selected */}
            <Grid item xs={12} sm={6}>
              <AsyncUserSelect
                value={values.filter_account_owner}
                onChange={(event, user) => setFieldValue('filter_account_owner', user)}
                label="Select User"
                placeholder="Search user..."
                disabled={territory?.is_system || (values.filter_account_scope !== 'other' && !values.filter_account_owner?.id)}
              />
            </Grid>

            {/* ==================== OWNER SCOPE ==================== */}
            <SectionTitle>Account Owner</SectionTitle>
            
            <Grid item xs={12}>
              <FormControl component="fieldset" fullWidth disabled={territory?.is_system}>
                <RadioGroup
                  row
                  value={values.filter_account_scope || (values.filter_account_owner?.id ? 'other' : '')}
                  onChange={(e) => {
                    const newScope = e.target.value;
                    setFieldValue('filter_account_scope', newScope);
                    // Clear account_owner when switching away from 'other'
                    if (newScope !== 'other') {
                      setFieldValue('filter_account_owner', null);
                    }
                  }}
                  sx={{ gap: 2 }}
                >
                  <FormControlLabel 
                    value="" 
                    control={<Radio size="small" />} 
                    label="All" 
                  />
                  <FormControlLabel 
                    value="mine" 
                    control={<Radio size="small" />} 
                    label="Mine" 
                  />
                  <FormControlLabel 
                    value="team" 
                    control={<Radio size="small" />} 
                    label="My Team" 
                  />
                  <FormControlLabel 
                    value="other" 
                    control={<Radio size="small" />} 
                    label="Specific user" 
                  />
                </RadioGroup>
              </FormControl>
            </Grid>
            
            {/* User Select - only enabled when 'other' is selected */}
            <Grid item xs={12} sm={6}>
              <AsyncUserSelect
                value={values.filter_account_owner || null}
                onChange={(event, user) => setFieldValue('filter_account_owner', user || null)}
                label="Select User"
                placeholder="Search user..."
                disabled={territory?.is_system || (values.filter_account_scope !== 'other' && !values.filter_account_owner?.id)}
              />
            </Grid>


            {/* ==================== FUTURE FILTERS PLACEHOLDER ==================== */}
            <SectionTitle>Advanced Filters</SectionTitle>
            
            <Grid item xs={12}>
              <Box 
                sx={{ 
                  p: 2, 
                  bgcolor: 'grey.100', 
                  borderRadius: 1,
                  border: '1px dashed',
                  borderColor: 'grey.300'
                }}
              >
                <Typography variant="body2" color="text.secondary" align="center">
                  More filters coming soon: Tech Stack, Buying Process, Signals, Owner...
                </Typography>
              </Box>
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
                  {isSubmitting ? 'Saving...' : 'Save Changes'}
                </Button>
              </Stack>
            </Grid>
          </Grid>
        </DialogActions>
      </Form>
    </FormikProvider>
  );
}

FormTerritoryEdit.propTypes = {
  territory: PropTypes.object.isRequired,
  closeModal: PropTypes.func
};

export default React.memo(FormTerritoryEdit);