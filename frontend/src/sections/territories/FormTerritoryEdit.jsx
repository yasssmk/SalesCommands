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

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// project imports
import { displaySuccessSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formErrorHandler';

// api
import { updateTerritory, TERRITORY_TYPES } from 'api/territories/territories';

// utils
import { formatDateTime } from 'config/formatters';

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
  filter_definition: territory?.filter_definition || {}
});

// ==============================|| FORM TERRITORY EDIT ||============================== //

/**
 * FormTerritoryEdit - Edit existing territory modal form
 * 
 * Features:
 * - Pre-filled values from territory
 * - Name and description editing
 * - Type selection (read-only for system territories)
 * - Filter definition display
 * 
 * @param {Object} territory - Territory object to edit
 * @param {Function} closeModal - Function to close the modal
 */
function FormTerritoryEdit({ territory, closeModal }) {
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ==============================|| FORMIK SETUP ||============================== //

  const formik = useFormik({
    initialValues: buildInitialValues(territory),
    validationSchema: EditSchema,
    enableReinitialize: true,
    onSubmit: async (values) => {
      setIsSubmitting(true);
      
      try {
        const payload = {
          name: values.name.trim(),
          description: values.description?.trim() || null,
          type: values.type,
          filter_definition: values.filter_definition || {}
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

  // ==============================|| FILTER SUMMARY ||============================== //

  const getFilterSummary = () => {
    if (!values.filter_definition || Object.keys(values.filter_definition).length === 0) {
      return 'No filters applied';
    }
    
    const count = Object.values(values.filter_definition).filter(v => v).length;
    return `${count} filter${count > 1 ? 's' : ''} applied`;
  };

  // ==============================|| RENDER ||============================== //

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        
        {/* ==================== DIALOG TITLE ==================== */}
        
        <DialogTitle>
          Edit Territory
          {territory.is_system && (
            <Typography variant="caption" color="warning.main" sx={{ ml: 1 }}>
              (System territory - limited editing)
            </Typography>
          )}
        </DialogTitle>
        <Divider />
        
        {/* ==================== DIALOG CONTENT ==================== */}
        
        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={3}>
            
            {/* ==================== TERRITORY NAME ==================== */}
            
            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="territory-name">Territory Name *</InputLabel>
                <TextField
                  fullWidth
                  id="territory-name"
                  placeholder="Enter territory name"
                  {...getFieldProps('name')}
                  error={Boolean(touched.name && errors.name)}
                  helperText={touched.name && errors.name}
                  disabled={territory.is_system}
                />
              </Stack>
            </Grid>

            {/* ==================== DESCRIPTION ==================== */}

            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="territory-description">Description</InputLabel>
                <TextField
                  fullWidth
                  id="territory-description"
                  placeholder="Enter description"
                  multiline
                  rows={3}
                  {...getFieldProps('description')}
                  error={Boolean(touched.description && errors.description)}
                  helperText={touched.description && errors.description}
                />
              </Stack>
            </Grid>

            {/* ==================== TYPE ==================== */}

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="territory-type">Type *</InputLabel>
                <FormControl fullWidth error={Boolean(touched.type && errors.type)}>
                  <Select
                    id="territory-type"
                    value={values.type}
                    onChange={(e) => setFieldValue('type', e.target.value)}
                    displayEmpty
                    disabled={territory.is_system}
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

            {/* ==================== FILTERS SUMMARY ==================== */}

            <Grid item xs={12} sm={6}>
              <Stack spacing={1}>
                <InputLabel>Filters</InputLabel>
                <Box
                  sx={{
                    p: 1.5,
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 1,
                    bgcolor: 'grey.50'
                  }}
                >
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <span>{getFilterSummary()}</span>
                    {/* Future: Button to open filter builder */}
                  </Stack>
                </Box>
              </Stack>
            </Grid>

            {/* ==================== METADATA ==================== */}

            <Grid item xs={12}>
              <Divider sx={{ my: 1 }} />
              <Stack direction="row" spacing={4}>
                <Typography variant="caption" color="text.secondary">
                  Created: {formatDateTime(territory.created_at)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Updated: {formatDateTime(territory.updated_at)}
                </Typography>
              </Stack>
            </Grid>

          </Grid>
        </DialogContent>

        {/* ==================== DIALOG ACTIONS ==================== */}

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
                  disabled={!formik.isValid || isSubmitting || !formik.dirty}
                >
                  Save Changes
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