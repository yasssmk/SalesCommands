// frontend/src/sections/admin/teams/FormTeamAdd.jsx

import PropTypes from 'prop-types';
import React, { useState } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
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
import { displaySuccessSnackbar } from 'utils/displayError';
import { insertTeam } from 'api/admin/teams';
import { useGetTeams } from 'api/admin/teams';
import { handleFormikError } from 'utils/formErrorHandler';
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';


// ============================================
// FORM VALUES & VALIDATION
// ============================================
const buildInitialValues = () => ({
  name: '',
  parent_team: '',    // nullable - root teams have no parent
  manager: null         // REQUIRED per backend business rules
});

const CreateSchema = Yup.object().shape({
  name: Yup.string()
    .required('Team name is required')
    .min(2, 'Team name must be at least 2 characters')
    .max(100, 'Team name must not exceed 100 characters'),
  parent_team: Yup.string().nullable(),
  manager: Yup.object()
    .nullable()
    .required('Manager is required')
    .test('has-id', 'Manager is required', (value) => value?.id != null)
});

// ============================================
// FORM COMPONENT
// ============================================

/**
 * Form for creating a new team
 * 
 * Features:
 * - Team name input with validation
 * - Parent team selection (optional) - allows hierarchy
 * - Manager selection (optional)
 * - Root-level teams (no parent) supported
 * 
 * @param {Function} closeModal - Function to close the modal
 */
function FormTeamAdd({ closeModal }) {
  const theme = useTheme();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // ==============================|| API HOOKS ||============================== //

  const { teams = [], teamsLoading } = useGetTeams();

  // ==============================|| FORMIK SETUP ||============================== //

  const formik = useFormik({
    initialValues: buildInitialValues(),
    validationSchema: CreateSchema,
    enableReinitialize: false,
    onSubmit: async (values) => {
      setIsSubmitting(true);
      
      try {
        const payload = {
          name: values.name.trim(),
          parent_team: values.parent_team || null,
          manager: values.manager?.id // Required, no null fallback
        };
        
        const result = await insertTeam(payload);
        
        if (result.success) {
          displaySuccessSnackbar('Team created successfully');
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

  const { errors, touched, handleSubmit, getFieldProps, values } = formik;

  // ==============================|| RENDER ||============================== //

  return (
    <FormikProvider value={formik}>
      <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
        
        {/* ==================== DIALOG TITLE ==================== */}
        
        <DialogTitle>New Team</DialogTitle>
        <Divider />
        
        {/* ==================== DIALOG CONTENT ==================== */}
        
        <DialogContent sx={{ p: 2.5 }}>
          <Grid container spacing={3}>
            
            {/* ==================== TEAM NAME ==================== */}
            
            <Grid item xs={12}>
              <Stack spacing={1}>
                <InputLabel htmlFor="team-name">Team Name *</InputLabel>
                <TextField
                  fullWidth
                  id="team-name"
                  placeholder="Enter team name"
                  {...getFieldProps('name')}
                  error={Boolean(touched.name && errors.name)}
                  helperText={touched.name && errors.name}
                />
              </Stack>
            </Grid>

            {/* ==================== PARENT TEAM ==================== */}
            
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="parent-team">Parent Team</InputLabel>
                <FormControl fullWidth error={Boolean(touched.parent_team && errors.parent_team)}>
                  <Select
                    id="parent-team"
                    displayEmpty
                    {...getFieldProps('parent_team')}
                    disabled={teamsLoading}
                  >
                    <MenuItem value="">
                      <em>None (Root-level team)</em>
                    </MenuItem>
                    {teams.map((team) => (
                      <MenuItem key={team.id} value={team.id}>
                        {team.name}
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.parent_team && errors.parent_team && (
                    <FormHelperText error>{errors.parent_team}</FormHelperText>
                  )}
                  <FormHelperText>Leave empty for root-level team</FormHelperText>
                </FormControl>
              </Stack>
            </Grid>

            {/* ==================== MANAGER ==================== */}
            
            <Grid item xs={12} md={6}>
              <Stack spacing={1}>
                <InputLabel htmlFor="manager">Manager *</InputLabel>
                <AsyncUserSelect
                  value={values.manager}
                  onChange={(event, newValue) => {
                    formik.setFieldValue('manager', newValue);
                  }}
                  placeholder="Search by name or email..."
                  error={Boolean(touched.manager && errors.manager)}
                  helperText={touched.manager && errors.manager}
                />
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

FormTeamAdd.propTypes = { 
  closeModal: PropTypes.func 
};

export default React.memo(FormTeamAdd);