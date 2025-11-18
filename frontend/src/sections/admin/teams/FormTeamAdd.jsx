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

// ============================================
// 🟡 MOCK DATA - TO REPLACE WITH API HOOKS
// ============================================
const mockTeams = [
  { id: '1', name: 'Sales Team' },
  { id: '2', name: 'Marketing Team' },
  { id: '3', name: 'Engineering Team' },
  { id: '4', name: 'Product Team' },
  { id: '5', name: 'Customer Success Team' }
];

const mockUsers = [
  { id: '1', first_name: 'John', last_name: 'Doe', email: 'john@example.com' },
  { id: '2', first_name: 'Jane', last_name: 'Smith', email: 'jane@example.com' },
  { id: '3', first_name: 'Michael', last_name: 'Johnson', email: 'michael@example.com' },
  { id: '4', first_name: 'Sarah', last_name: 'Williams', email: 'sarah@example.com' }
];

// ============================================
// FORM VALUES & VALIDATION
// ============================================
const buildInitialValues = () => ({
  name: '',
  parent_team: '',    // nullable - root teams have no parent
  manager: ''         // nullable - teams can have no manager
});

const CreateSchema = Yup.object().shape({
  name: Yup.string()
    .required('Team name is required')
    .min(2, 'Team name must be at least 2 characters')
    .max(100, 'Team name must not exceed 100 characters'),
  parent_team: Yup.string().nullable(),
  manager: Yup.string().nullable()
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

  // ==============================|| FORMIK SETUP ||============================== //

  const formik = useFormik({
    initialValues: buildInitialValues(),
    validationSchema: CreateSchema,
    enableReinitialize: false,
    onSubmit: async (values) => {
      setIsSubmitting(true);
      
      // ============================================
      // 🔴 FINAL VERSION (API ready) - COMMENTED FOR NOW
      // ============================================
      // try {
      //   const payload = {
      //     name: values.name.trim(),
      //     parent_team: values.parent_team || null,
      //     manager: values.manager || null
      //   };
      //   
      //   const result = await insertTeam(payload);
      //   
      //   if (result.success) {
      //     displaySuccessSnackbar('Team created successfully');
      //     closeModal?.();
      //   } else {
      //     handleFormikError(result, formik);
      //   }
      // } catch (err) {
      //   handleFormikError(err, formik);
      // } finally {
      //   setIsSubmitting(false);
      // }

      // ============================================
      // 🟡 TEMPORARY VERSION (UX only) - TO DELETE WHEN API READY
      // ============================================
      try {
        // Simulate API delay
        await new Promise(resolve => setTimeout(resolve, 500));
        
        console.log('Team to create:', {
          name: values.name.trim(),
          parent_team: values.parent_team || null,
          manager: values.manager || null
        });
        
        displaySuccessSnackbar('Team created successfully (MOCK)');
        closeModal?.();
      } catch (err) {
        console.error('Mock error:', err);
      } finally {
        setIsSubmitting(false);
      }
    }
  });

  const { errors, touched, handleSubmit, getFieldProps, values } = formik;

  // ============================================
  // 🔴 FINAL VERSION - COMMENTED FOR NOW
  // ============================================
  // const { teams = [], teamsLoading } = useGetTeams();
  // const { users = [], usersLoading } = useGetUsers();
  // const anyLoading = teamsLoading || usersLoading;

  // ============================================
  // 🟡 TEMPORARY VERSION - MOCK DATA
  // ============================================
  const teams = mockTeams;
  const users = mockUsers;
  const anyLoading = false;

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
                    disabled={anyLoading}
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
                <InputLabel htmlFor="manager">Manager</InputLabel>
                <FormControl fullWidth error={Boolean(touched.manager && errors.manager)}>
                  <Select
                    id="manager"
                    displayEmpty
                    {...getFieldProps('manager')}
                    disabled={anyLoading}
                  >
                    <MenuItem value="">
                      <em>None</em>
                    </MenuItem>
                    {users.map((user) => (
                      <MenuItem key={user.id} value={user.id}>
                        {user.first_name} {user.last_name} ({user.email})
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.manager && errors.manager && (
                    <FormHelperText error>{errors.manager}</FormHelperText>
                  )}
                </FormControl>
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