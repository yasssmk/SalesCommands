// frontend/src/sections/admin/roles/FormRoleAdd.jsx

import PropTypes from 'prop-types';
import React, { useState } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Collapse from '@mui/material/Collapse';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormLabel from '@mui/material/FormLabel';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import Radio from '@mui/material/Radio';
import RadioGroup from '@mui/material/RadioGroup';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// project imports
import PermissionsMatrix from './PermissionsMatrix';
import { displaySuccessSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formErrorHandler';

// api hooks
import { insertRole } from 'api/admin/roles';

// assets
import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';
import DownOutlined from '@ant-design/icons/DownOutlined';
import UpOutlined from '@ant-design/icons/UpOutlined';

// ==============================|| VALIDATION SCHEMA ||============================== //

/**
 * Yup validation schema for role creation
 */
const CreateSchema = Yup.object().shape({
  name: Yup.string()
    .required('Role name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(50, 'Name must be less than 50 characters')
    .matches(
      /^[a-zA-Z0-9\s\-_]+$/,
      'Name can only contain letters, numbers, spaces, hyphens and underscores'
    ),
  tier: Yup.string()
    .oneOf(['manager', 'individual'], 'Invalid tier selection')
    .required('Tier is required')
});

// ==============================|| HELPER FUNCTIONS ||============================== //

/**
 * Build initial form values
 */
const buildInitialValues = () => ({
  name: '',
  tier: 'individual' // Default to individual tier
});

/**
 * Sanitize and transform payload for API
 * Converts tier string to backend flags format
 */
function sanitizePayload(values) {
  const payload = {
    name: values.name.trim()
  };
  
  // Convert tier string to boolean flags
  // Backend expects exactly ONE flag to be true
  if (values.tier === 'admin') {
    payload.is_admin = true;
    payload.is_manager = false;
    payload.is_individual = false;
  } else if (values.tier === 'manager') {
    payload.is_admin = false;
    payload.is_manager = true;
    payload.is_individual = false;
  } else {
    // individual (default)
    payload.is_admin = false;
    payload.is_manager = false;
    payload.is_individual = true;
  }
  
  return payload;
}

// ==============================|| FORM COMPONENT ||============================== //

/**
 * Form for creating a new role
 * 
 * Features:
 * - Role name input with validation
 * - Tier selection via radio buttons
 * - Collapsible live permissions matrix preview
 * - Automatic permissions assignment based on tier
 * 
 * @param {Function} closeModal - Function to close the modal
 */
function FormRoleAdd({ closeModal }) {
  const theme = useTheme();
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // State for collapsible permissions preview
  const [showPermissions, setShowPermissions] = useState(true);

  // ==============================|| FORMIK SETUP ||============================== //

  const formik = useFormik({
    initialValues: buildInitialValues(),
    validationSchema: CreateSchema,
    enableReinitialize: false,
    onSubmit: async (values, { setSubmitting }) => {
      setIsSubmitting(true);
      try {
        const payload = sanitizePayload(values);
        const result = await insertRole(payload);

        if (result.success) {
          displaySuccessSnackbar('Role created successfully');
          closeModal?.();
        } else {
          handleFormikError(result, formik);
        }
      } catch (err) {
        handleFormikError(err, formik);
      } finally {
        setIsSubmitting(false);
        setSubmitting(false);
      }
    }
  });

  const { errors, touched, handleSubmit, getFieldProps, setFieldValue, values } = formik;

  // ==============================|| RENDER ||============================== //

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        <DialogTitle>Add New Role</DialogTitle>
        <Divider />
        
        <DialogContent sx={{ p: 3 }}>
          <Grid container spacing={3}>
            
            {/* ==================== SECTION 1: EDITABLE FIELDS ==================== */}
            
            {/* Role Name */}
            <Grid item xs={12}>
              <Stack spacing={1}>
                <Typography variant="subtitle1">Role Name *</Typography>
                <TextField
                  fullWidth
                  id="name"
                  placeholder="Enter role name"
                  {...getFieldProps('name')}
                  error={Boolean(touched.name && errors.name)}
                  helperText={touched.name && errors.name}
                />
              </Stack>
            </Grid>

            {/* Tier Selection */}
            <Grid item xs={12}>
              <FormControl component="fieldset" fullWidth>
                <FormLabel component="legend" sx={{ mb: 1.5 }}>
                  <Typography variant="subtitle1">Access Tier *</Typography>
                </FormLabel>
                <RadioGroup
                  aria-label="tier"
                  name="tier"
                  value={values.tier}
                  onChange={(e) => setFieldValue('tier', e.target.value)}
                >
                  {/* Admin Option */}
                  {/* <FormControlLabel
                    value="admin"
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                          Admin
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Full access to everything across the entire organization
                        </Typography>
                      </Box>
                    }
                    sx={{ 
                      mb: 1.5,
                      p: 1.5,
                      border: `1px solid ${values.tier === 'admin' ? theme.palette.error.main : theme.palette.divider}`,
                      borderRadius: 1,
                      '&:hover': {
                        bgcolor: 'action.hover'
                      }
                    }}
                  /> */}

                  {/* Manager Option */}
                  <FormControlLabel
                    value="manager"
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                          Manager
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Team management and oversight with access to team resources
                        </Typography>
                      </Box>
                    }
                    sx={{ 
                      mb: 1.5,
                      p: 1.5,
                      border: `1px solid ${values.tier === 'manager' ? theme.palette.warning.main : theme.palette.divider}`,
                      borderRadius: 1,
                      '&:hover': {
                        bgcolor: 'action.hover'
                      }
                    }}
                  />

                  {/* Individual Option */}
                  <FormControlLabel
                    value="individual"
                    control={<Radio />}
                    label={
                      <Box>
                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                          Individual
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Personal workspace access with own data only
                        </Typography>
                      </Box>
                    }
                    sx={{ 
                      mb: 0,
                      p: 1.5,
                      border: `1px solid ${values.tier === 'individual' ? theme.palette.success.main : theme.palette.divider}`,
                      borderRadius: 1,
                      '&:hover': {
                        bgcolor: 'action.hover'
                      }
                    }}
                  />
                </RadioGroup>
                {touched.tier && errors.tier && (
                  <Typography variant="caption" color="error" sx={{ mt: 1 }}>
                    {errors.tier}
                  </Typography>
                )}
              </FormControl>
            </Grid>

            {/* ==================== SECTION 2: PERMISSIONS PREVIEW (COLLAPSIBLE) ==================== */}
            
            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              
              <Stack spacing={2}>
                {/* Header with collapse button */}
                <Stack direction="row" alignItems="center" justifyContent="space-between">
                  <Typography variant="h6">
                    Permissions Preview
                  </Typography>
                  <Button
                    variant="text"
                    size="small"
                    onClick={() => setShowPermissions(!showPermissions)}
                    endIcon={showPermissions ? <UpOutlined /> : <DownOutlined />}
                    sx={{ 
                      minWidth: 'auto',
                      color: 'text.secondary',
                      '&:hover': {
                        bgcolor: 'action.hover'
                      }
                    }}
                  >
                    {showPermissions ? 'Hide' : 'Show'}
                  </Button>
                </Stack>

                {/* Collapsible content */}
               
                  <Stack spacing={2}>
                    {/* Info Alert */}
                    <Alert 
                      severity="info" 
                      icon={<InfoCircleOutlined />}
                    >
                      <Typography variant="body2">
                        Permissions are automatically calculated based on the selected tier. 
                        They are defined at the system level and cannot be customized per role.
                      </Typography>
                    </Alert>
                    </Stack>

                     <Collapse in={showPermissions} timeout="auto" unmountOnExit>
                     <Stack spacing={2}>
                    {/* Permissions Matrix */}
                    <Box sx={{ 
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 1,
                      p: 2,
                      bgcolor: theme.palette.background.paper
                    }}>
                      <PermissionsMatrix tier={values.tier} showLegend={false} />
                    </Box>
                  </Stack>
                </Collapse>
              </Stack>
            </Grid>

          </Grid>
        </DialogContent>

        {/* ==================== DIALOG ACTIONS ==================== */}
        
        <Divider />
        <DialogActions sx={{ p: 2.5 }}>
          <Grid container justifyContent="space-between" alignItems="center">
            <Grid item />
            <Grid item>
              <Stack direction="row" spacing={2} alignItems="center">
                <Button color="error" onClick={closeModal}>
                  Cancel
                </Button>
                <Button 
                  type="submit" 
                  variant="contained" 
                  disabled={!formik.isValid || isSubmitting}
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

FormRoleAdd.propTypes = { 
  closeModal: PropTypes.func 
};

export default React.memo(FormRoleAdd);