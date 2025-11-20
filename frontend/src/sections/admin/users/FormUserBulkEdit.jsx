// frontend/src/sections/admin/users/FormUserBulkEdit.jsx
import PropTypes from 'prop-types';
import React, { useEffect, useMemo, useState } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import Grid from '@mui/material/Grid';
import ListItemText from '@mui/material/ListItemText';
import MenuItem from '@mui/material/MenuItem';
import OutlinedInput from '@mui/material/OutlinedInput';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// api
import { bulkUpdateUsers } from 'api/admin/users';
import { useGetUserRoles } from 'api/admin/roles';
import { useGetTeams } from 'api/admin/teams';

import { displaySuccessSnackbar, displayWarningSnackbar } from 'utils/displayError';
import { handleFormikError } from 'utils/formErrorHandler';

// project imports
import CircularWithPath from 'components/@extended/progress/CircularWithPath';
import BulkOperationSyncDialog from 'components/bulk/BulkOperationSyncDialog';
import { useBulkOperationSync } from 'hooks/useBulkOperationSync';

// utils
import { isValidUUID } from 'utils/validators';

// ====== FORM VALUES ======
const buildInitialValues = () => ({
  // Field enable flags
  apply_is_active: false,
  apply_is_superuser: false,
  apply_role: false,
  apply_team: false,
  
  // Actual values
  is_active: true,
  is_superuser: false,
  role: '',
  team: ''
});

const BulkEditSchema = Yup.object().shape({
  // UUID fields: validate only if apply flag is true
  role: Yup.string()
    .nullable()
    .when('apply_role', {
      is: true,
      then: (schema) => schema.test('is-valid-uuid', 'Invalid role selection', function(value) {
        if (!value || value === '') return false; // Required if applying
        return isValidUUID(value);
      })
    }),

  team: Yup.string()
    .nullable()
    .when('apply_team', {
      is: true,
      then: (schema) => schema.test('is-valid-uuid', 'Invalid team selection', function(value) {
        if (!value || value === '') return false; // Required if applying
        return isValidUUID(value);
      })
    })
});

function buildPatchPayload(values) {
  const patch = {};
  
  if (values.apply_is_active) {
    patch.is_active = values.is_active;
  }
  
  if (values.apply_is_superuser) {
    patch.is_superuser = values.is_superuser;
  }
  
  if (values.apply_role && values.role) {
    patch.role = values.role;
  }
  
  if (values.apply_team && values.team) {
    patch.team = values.team;
  }

  return patch;
}

// ==============================|| BULK EDIT USERS - FORM ||============================== //

function FormUserBulkEdit({ closeModal, selectedUserIds = [], selectedCount = 0 }) {
  const [processing, setProcessing] = useState(false); 
  // const [loading, setLoading] = useState(false);
  const [hadTimeout, setHadTimeout] = useState(false);  

  // Hook centralisé avec snackbar de succès après sync
  const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
    onComplete: () => {
      // Si timeout, afficher le snackbar de succès maintenant
      if (hadTimeout) {
        displaySuccessSnackbar(`${selectedCount} user${selectedCount > 1 ? 's' : ''} updated successfully`);
      }
      setProcessing(false);
      closeModal?.();
      setHadTimeout(false);  // Reset le flag
    },
    closeDelay: 300
  });

  // useEffect(() => {
  //   setLoading(false);
  // }, []);

  const formik = useFormik({
  initialValues: buildInitialValues(),
  validationSchema: BulkEditSchema,
  onSubmit: async (values, { setSubmitting }) => {
    try {
      const patch = buildPatchPayload(values);
      
      // Check if at least one field is selected
      if (Object.keys(patch).length === 0) {
        displayWarningSnackbar('Please select at least one field to update');
        setSubmitting(false);
        return;
      }

      const result = await bulkUpdateUsers(
        selectedUserIds, 
        patch, 
        'partial',
        onSyncProgress,
        onSyncComplete
      );

      if (result?.data?.__is202) {
         console.log('[FormUserBulkEdit] 202 Accepted → entering processing state');
         setProcessing(true);
         return; // Le polling gère la suite
       }

      // ✅ Succès complet uniquement
      if (result.success === true) {
        displaySuccessSnackbar(`${result.summary.updated} users updated successfully`);
        
        if (!syncing && !processing) {
          closeModal?.();
        }
      } else if (result.isPending) {
        const pendingMessage =
          result.message ||
          'Operation still in progress. It will complete in the background.';

        displayWarningSnackbar(pendingMessage);

        if (!syncing && !processing) {
          closeModal?.();
        }
      }
      // ⏱️ Timeout
      else if (result.isTimeout) {
        setHadTimeout(true);
        setProcessing(true); 
      } 
      // ❌ Tout le reste (partial, false, errors)
      else {
        // ⭐ NEW: Pass closeModal as onComplete callback
        handleFormikError(result, formik, {
          // onComplete: closeModal  // 🔒 Ferme le modal après gestion
        });
      }
    } catch (err) {
      // ⭐ NEW: Pass closeModal for exceptions too
      handleFormikError(err, formik, {
        // onComplete: closeModal  // 🔒 Ferme le modal après gestion
      });
    }
  }
});

  const { errors, touched, handleSubmit, isSubmitting, setFieldValue, values } = formik;
  const isProcessing = isSubmitting || processing || syncing;

  const { roles = [], rolesLoading } = useGetUserRoles();
  const { teams = [], teamsLoading } = useGetTeams();

  const anyLoading = rolesLoading || teamsLoading;

  if (anyLoading) {
    return (
      <Box sx={{ p: 5 }}>
        <Stack direction="row" justifyContent="center">
          <CircularWithPath />
        </Stack>
      </Box>
    );
  }

  const noTeamsAvailable = (teams?.length ?? 0) === 0;

  // Count how many fields are selected
  const selectedFieldsCount = [
    values.apply_is_active,
    values.apply_is_superuser,
    values.apply_role,
    values.apply_team
  ].filter(Boolean).length;

  return (
    <>
      <FormikProvider value={formik}>
        <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
          <DialogTitle>
            Bulk Edit Users
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {selectedCount} user{selectedCount !== 1 ? 's' : ''} selected • {selectedFieldsCount} field{selectedFieldsCount !== 1 ? 's' : ''} to update
            </Typography>
          </DialogTitle>
          
          <Divider />

          {/* ⭐ NOUVEAU: Affichage conditionnel simplifié */}
          {isProcessing ? (
            // État: Sync en cours → Composant réutilisable
            <DialogContent>
              <BulkOperationSyncDialog 
                attempt={syncAttempt}
                operation="update"
              />
            </DialogContent>
          ) : (
            // État: Normal → Formulaire normal
            <DialogContent sx={{ p: 2.5 }}>
              <Grid container spacing={3}>
                {/* INFO BOX */}
                <Grid item xs={12}>
                  <Box sx={{
                    p: 2,
                    bgcolor: 'primary.lighter',
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: 'primary.light'
                  }}>
                    <Typography variant="body2" color="text.secondary">
                      <strong>How it works:</strong> Check the boxes next to the fields you want to update.
                      Only checked fields will be applied to all selected users.
                    </Typography>
                  </Box>
                </Grid>

                {/* ROLE */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={values.apply_role}
                          onChange={(e) => setFieldValue('apply_role', e.target.checked)}
                        />
                      }
                      label={
                        <Typography variant="subtitle1" fontWeight={values.apply_role ? 600 : 400}>
                          Update Role
                        </Typography>
                      }
                    />
                    
                    {values.apply_role && (
                      <FormControl fullWidth>
                        <Select
                          id="bulk-role"
                          displayEmpty
                          value={values.role}
                          onChange={(e) => setFieldValue('role', e.target.value)}
                          input={<OutlinedInput placeholder="Select role" />}
                          disabled={!values.apply_role}
                          error={Boolean(touched.role && errors.role && values.apply_role)}
                          renderValue={(selected) => {
                            if ((roles?.length ?? 0) === 0) {
                              return (
                                <Typography variant="subtitle1" color="text.secondary">
                                  No roles available
                                </Typography>
                              );
                            }
                            if (!selected) return <Typography variant="subtitle1" color="text.secondary">Select role</Typography>;
                            const r = roles?.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{r?.name || '—'}</Typography>;
                          }}
                        >
                          {(roles || []).length === 0 ? (
                            <MenuItem disabled>
                              <Typography color="text.secondary">No roles available</Typography>
                            </MenuItem>
                          ) : (
                            (roles || []).map((r) => (
                              <MenuItem key={r.id} value={String(r.id)}>
                                <ListItemText primary={r.name} />
                              </MenuItem>
                            ))
                          )}
                        </Select>
                        {touched.role && errors.role && values.apply_role && (
                          <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                            {errors.role}
                          </Typography>
                        )}
                      </FormControl>
                    )}
                  </Stack>
                </Grid>

                {/* TEAM */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={values.apply_team}
                          onChange={(e) => setFieldValue('apply_team', e.target.checked)}
                        />
                      }
                      label={
                        <Typography variant="subtitle1" fontWeight={values.apply_team ? 600 : 400}>
                          Update Team
                        </Typography>
                      }
                    />
                    
                    {values.apply_team && (
                      <FormControl fullWidth>
                        <Select
                          id="bulk-team"
                          displayEmpty
                          value={values.team}
                          onChange={(e) => setFieldValue('team', e.target.value)}
                          input={<OutlinedInput placeholder="Select team" />}
                          disabled={!values.apply_team}
                          error={Boolean(touched.team && errors.team && values.apply_team)}
                          renderValue={(selected) => {
                            if (noTeamsAvailable) {
                              return (
                                <Typography variant="subtitle1" color="text.secondary">
                                  No teams available
                                </Typography>
                              );
                            }
                            if (!selected) return <Typography variant="subtitle1" color="text.secondary">Select team</Typography>;
                            const t = teams?.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{t?.name || '—'}</Typography>;
                          }}
                        >
                          {noTeamsAvailable ? (
                            <MenuItem disabled>
                              <Typography color="text.secondary">No teams available</Typography>
                            </MenuItem>
                          ) : (
                            (teams || []).map((t) => (
                              <MenuItem key={t.id} value={String(t.id)}>
                                <ListItemText primary={t.name} />
                              </MenuItem>
                            ))
                          )}
                        </Select>
                        {touched.team && errors.team && values.apply_team && (
                          <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                            {errors.team}
                          </Typography>
                        )}
                      </FormControl>
                    )}
                  </Stack>
                </Grid>
                
                <Grid item xs={12}>
                  <Divider />
                </Grid>

                {/* IS_ACTIVE */}
                <Grid item xs={12}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={values.apply_is_active}
                          onChange={(e) => setFieldValue('apply_is_active', e.target.checked)}
                        />
                      }
                      label={
                        <Stack spacing={0.5}>
                          <Typography variant="subtitle1" fontWeight={values.apply_is_active ? 600 : 400}>
                            Update Active Status
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Controls whether users can sign in
                          </Typography>
                        </Stack>
                      }
                    />
                    {values.apply_is_active && (
                      <Switch
                        checked={values.is_active}
                        onChange={(e) => setFieldValue('is_active', e.target.checked)}
                        disabled={!values.apply_is_active}
                      />
                    )}
                  </Stack>
                </Grid>

                {/* IS_SUPERUSER */}
                <Grid item xs={12}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={values.apply_is_superuser}
                          onChange={(e) => setFieldValue('apply_is_superuser', e.target.checked)}
                        />
                      }
                      label={
                        <Stack spacing={0.5}>
                          <Typography variant="subtitle1" fontWeight={values.apply_is_superuser ? 600 : 400}>
                            Update SuperUser Status
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            Grants admin rights to users
                          </Typography>
                        </Stack>
                      }
                    />
                    {values.apply_is_superuser && (
                      <Switch
                        checked={values.is_superuser}
                        onChange={(e) => setFieldValue('is_superuser', e.target.checked)}
                        disabled={!values.apply_is_superuser}
                      />
                    )}
                  </Stack>
                </Grid>
              </Grid>
            </DialogContent>
          )}

          <Divider />

          {/* Actions */}
          <DialogActions sx={{ p: 2.5 }}>
            <Grid container justifyContent="space-between" alignItems="center">
              <Grid item>
                {isProcessing ? (
                  <Typography variant="caption" color="text.secondary">
                    Please wait, synchronization in progress...
                  </Typography>
                ) : (
                  <Typography variant="caption" color="text.secondary">
                    {selectedFieldsCount === 0 && 'Select at least one field to update'}
                  </Typography>
                )}
              </Grid>
              <Grid item>
                <Stack direction="row" spacing={2} alignItems="center">
                  <Button 
                    color="error" 
                    onClick={closeModal} 
                    disabled={isProcessing} 
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="contained"
                    disabled={isProcessing || selectedFieldsCount === 0} 
                  >
                    {isProcessing ? 'Processing...' : `Update ${selectedCount} User${selectedCount !== 1 ? 's' : ''}`}
                  </Button>
                </Stack>
              </Grid>
            </Grid>
          </DialogActions>
        </Form>
      </FormikProvider>
    </>
  );
}

FormUserBulkEdit.propTypes = {
  closeModal: PropTypes.func,
  selectedUserIds: PropTypes.array.isRequired,
  selectedCount: PropTypes.number.isRequired
};

export default React.memo(FormUserBulkEdit);