
// frontend/src/sections/admin/roles/FormRoleEdit.jsx

import PropTypes from 'prop-types';
import React, { useMemo, useState } from 'react';

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
import { updateRole } from 'api/admin/roles';

// assets
import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';
import DownOutlined from '@ant-design/icons/DownOutlined';
import UpOutlined from '@ant-design/icons/UpOutlined';

// ==============================|| VALIDATION SCHEMA ||============================== //

const EditSchema = Yup.object().shape({
  name: Yup.string()
    .required('Role name is required')
    .min(2, 'Name must be at least 2 characters')
    .max(50, 'Name must be less than 50 characters')
    .matches(
      /^[a-zA-Z0-9\s\-_]+$/,
      'Name can only contain letters, numbers, spaces, hyphens and underscores'
    ),
  tier: Yup.string()
    .oneOf(['admin', 'manager', 'individual'], 'Invalid tier selection')
    .required('Tier is required')
});

// ==============================|| HELPER FUNCTIONS ||============================== //

const getTierFromRole = (role) => {
  if (!role) return 'individual';
  if (role.is_admin) return 'admin';
  if (role.is_manager) return 'manager';
  if (role.is_individual) return 'individual';
  return role.tier || 'individual';
};

const buildInitialValues = (role) => ({
  name: role?.name || '',
  tier: getTierFromRole(role)
});

function sanitizePayload(values) {
  const payload = {
    name: values.name.trim()
  };

  if (values.tier === 'admin') {
    payload.is_admin = true;
    payload.is_manager = false;
    payload.is_individual = false;
  } else if (values.tier === 'manager') {
    payload.is_admin = false;
    payload.is_manager = true;
    payload.is_individual = false;
  } else {
    payload.is_admin = false;
    payload.is_manager = false;
    payload.is_individual = true;
  }

  return payload;
}

// ==============================|| FORM COMPONENT ||============================== //

function FormRoleEdit({ closeModal, role: initialRole }) {
  const theme = useTheme();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPermissions, setShowPermissions] = useState(true);

  const isAdminRole = Boolean(initialRole?.is_admin || getTierFromRole(initialRole) === 'admin');

  const formik = useFormik({
    initialValues: buildInitialValues(initialRole),
    validationSchema: EditSchema,
    enableReinitialize: true,
    onSubmit: async (values, { setSubmitting }) => {
      if (isAdminRole) {
        setSubmitting(false);
        return;
      }

      setIsSubmitting(true);
      try {
        const payload = sanitizePayload(values);
        const result = await updateRole(initialRole.id, payload);

        if (result.success) {
          displaySuccessSnackbar('Role updated successfully');
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

  const radioOptions = useMemo(
    () => [
      {
        value: 'admin',
        title: 'Admin',
        description: 'Full access to everything across the entire organization',
        borderColor: theme.palette.error.main
      },
      {
        value: 'manager',
        title: 'Manager',
        description: 'Team management and oversight with access to team resources',
        borderColor: theme.palette.warning.main
      },
      {
        value: 'individual',
        title: 'Individual',
        description: 'Personal workspace access with own data only',
        borderColor: theme.palette.success.main
      }
    ],
    [theme]
  );

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        <DialogTitle>Edit Role</DialogTitle>
        <Divider />

        <DialogContent sx={{ p: 3 }}>
          <Grid container spacing={3}>
            {isAdminRole && (
              <Grid item xs={12}>
                <Alert severity="warning" icon={<InfoCircleOutlined />}>
                  <Typography variant="body2">
                    The administrator role cannot be edited.
                  </Typography>
                </Alert>
              </Grid>
            )}

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
                  disabled={isAdminRole}
                />
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <FormControl component="fieldset" fullWidth disabled={isAdminRole}>
                <FormLabel component="legend" sx={{ mb: 1.5 }}>
                  <Typography variant="subtitle1">Access Tier *</Typography>
                </FormLabel>
                <RadioGroup
                  aria-label="tier"
                  name="tier"
                  value={values.tier}
                  onChange={(e) => setFieldValue('tier', e.target.value)}
                >
                  {radioOptions.map((option) => (
                    <FormControlLabel
                      key={option.value}
                      value={option.value}
                      control={<Radio />}
                      label={
                        <Box>
                          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                            {option.title}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {option.description}
                          </Typography>
                        </Box>
                      }
                      sx={{
                        mb: option.value === 'individual' ? 0 : 1.5,
                        p: 1.5,
                        border: `1px solid ${
                          values.tier === option.value
                            ? option.borderColor
                            : theme.palette.divider
                        }`,
                        borderRadius: 1,
                        '&:hover': {
                          bgcolor: 'action.hover'
                        }
                      }}
                    />
                  ))}
                </RadioGroup>
                {touched.tier && errors.tier && (
                  <Typography variant="caption" color="error" sx={{ mt: 1 }}>
                    {errors.tier}
                  </Typography>
                )}
              </FormControl>
            </Grid>

            <Grid item xs={12}>
              <Divider sx={{ my: 2 }} />
              <Stack spacing={2}>
                <Stack direction="row" alignItems="center" justifyContent="space-between">
                  <Typography variant="h6">Permissions Preview</Typography>
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
                    disabled={isAdminRole}
                  >
                    {showPermissions ? 'Hide' : 'Show'}
                  </Button>
                </Stack>

                <Stack spacing={2}>
                  <Alert severity="info" icon={<InfoCircleOutlined />}>
                    <Typography variant="body2">
                      Permissions are automatically calculated based on the selected tier.
                      They are defined at the system level and cannot be customized per role.
                    </Typography>
                  </Alert>
                </Stack>

                <Collapse in={showPermissions} timeout="auto" unmountOnExit>
                  <Box
                    sx={{
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 1,
                      p: 2,
                      bgcolor: theme.palette.background.paper
                    }}
                  >
                    <PermissionsMatrix tier={values.tier} showLegend={false} />
                  </Box>
                </Collapse>
              </Stack>
            </Grid>
          </Grid>
        </DialogContent>

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
                  disabled={isAdminRole || !formik.isValid || isSubmitting}
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

FormRoleEdit.propTypes = {
  closeModal: PropTypes.func,
  role: PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
    name: PropTypes.string,
    is_admin: PropTypes.bool,
    is_manager: PropTypes.bool,
    is_individual: PropTypes.bool,
    tier: PropTypes.string
  })
};

export default React.memo(FormRoleEdit);
