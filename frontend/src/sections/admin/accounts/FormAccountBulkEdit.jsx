// frontend/src/sections/admin/accounts/FormAccountBulkEdit.jsx

import PropTypes from 'prop-types';
import React, { useState } from 'react';

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
import Typography from '@mui/material/Typography';

// third-party
import * as Yup from 'yup';
import { useFormik, Form, FormikProvider } from 'formik';

// api
import { bulkUpdateAccounts, useGetAccountChoices, useGetAccounts } from 'api/admin/accounts';
import { useGetUsers } from 'api/admin/users';

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
  apply_account_owner: false,
  apply_type: false,
  apply_classification: false,
  apply_parent: false,
  
  // Actual values
  account_owner: '',
  type: '',
  classification: '',
  parent: ''
});

const BulkEditSchema = Yup.object().shape({
  // UUID fields: validate only if apply flag is true
  account_owner: Yup.string()
    .nullable()
    .when('apply_account_owner', {
      is: true,
      then: (schema) => schema.test('is-valid-uuid', 'Invalid owner selection', function(value) {
        if (!value || value === '') return true; // Allow clearing (null)
        return isValidUUID(value);
      })
    }),

  parent: Yup.string()
    .nullable()
    .when('apply_parent', {
      is: true,
      then: (schema) => schema.test('is-valid-uuid', 'Invalid parent selection', function(value) {
        if (!value || value === '') return true; // Allow clearing (null)
        return isValidUUID(value);
      })
    })
});

function buildPatchPayload(values) {
  const patch = {};
  
  if (values.apply_account_owner) {
    patch.account_owner_id = values.account_owner || null;
  }
  
  if (values.apply_type) {
    patch.type = values.type || null;
  }
  
  if (values.apply_classification) {
    patch.classification = values.classification || null;
  }
  
  if (values.apply_parent) {
    patch.parent_id = values.parent || null;
  }

  return patch;
}

// ==============================|| BULK EDIT ACCOUNTS - FORM ||============================== //

function FormAccountBulkEdit({ closeModal, selectedAccountIds = [], selectedCount = 0 }) {
  const [processing, setProcessing] = useState(false);
  const [hadTimeout, setHadTimeout] = useState(false);

  // Hook centralisé avec snackbar de succès après sync
  const { syncing, syncAttempt, onSyncProgress, onSyncComplete } = useBulkOperationSync({
    onComplete: () => {
      if (hadTimeout) {
        displaySuccessSnackbar(`${selectedCount} account${selectedCount > 1 ? 's' : ''} updated successfully`);
      }
      setProcessing(false);
      closeModal?.();
      setHadTimeout(false);
    },
    closeDelay: 300
  });

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

        const result = await bulkUpdateAccounts(
          selectedAccountIds,
          patch,
          'partial',
          onSyncProgress,
          onSyncComplete
        );

        if (result?.data?.__is202) {
          console.log('[FormAccountBulkEdit] 202 Accepted → entering processing state');
          setProcessing(true);
          return;
        }

        // Succès complet uniquement
        if (result.success === true) {
          displaySuccessSnackbar(`${result.summary.updated} accounts updated successfully`);
          
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
        // Timeout
        else if (result.isTimeout) {
          setHadTimeout(true);
          setProcessing(true);
        }
        // Tout le reste (partial, false, errors)
        else {
          handleFormikError(result, formik, {});
        }
      } catch (err) {
        handleFormikError(err, formik, {});
      }
    }
  });

  const { errors, touched, handleSubmit, isSubmitting, setFieldValue, values } = formik;
  const isProcessing = isSubmitting || processing || syncing;

  // Fetch data for dropdowns
  const { types, classifications, choicesLoading } = useGetAccountChoices();
  const { users = [], usersLoading } = useGetUsers();
  const { accounts: parentAccounts = [], accountsLoading } = useGetAccounts();

  const anyLoading = choicesLoading || usersLoading || accountsLoading;

  if (anyLoading) {
    return (
      <Box sx={{ p: 5 }}>
        <Stack direction="row" justifyContent="center">
          <CircularWithPath />
        </Stack>
      </Box>
    );
  }

  // Filter out selected accounts from parent options (can't be parent of itself)
  const availableParents = (parentAccounts?.results || parentAccounts || []).filter(
    (acc) => !selectedAccountIds.includes(acc.id)
  );

  // Count how many fields are selected
  const selectedFieldsCount = [
    values.apply_account_owner,
    values.apply_type,
    values.apply_classification,
    values.apply_parent
  ].filter(Boolean).length;

  return (
    <>
      <FormikProvider value={formik}>
        <Form autoComplete="off" noValidate onSubmit={handleSubmit}>
          <DialogTitle>
            Bulk Edit Accounts
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              {selectedCount} account{selectedCount !== 1 ? 's' : ''} selected • {selectedFieldsCount} field{selectedFieldsCount !== 1 ? 's' : ''} to update
            </Typography>
          </DialogTitle>
          
          <Divider />

          {isProcessing ? (
            <DialogContent>
              <BulkOperationSyncDialog 
                attempt={syncAttempt}
                operation="update"
              />
            </DialogContent>
          ) : (
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
                      Only checked fields will be applied to all selected accounts.
                    </Typography>
                  </Box>
                </Grid>

                {/* ACCOUNT OWNER */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={values.apply_account_owner}
                          onChange={(e) => setFieldValue('apply_account_owner', e.target.checked)}
                        />
                      }
                      label={
                        <Typography variant="subtitle1" fontWeight={values.apply_account_owner ? 600 : 400}>
                          Update Account Owner
                        </Typography>
                      }
                    />
                    
                    {values.apply_account_owner && (
                      <FormControl fullWidth>
                        <Select
                          id="bulk-account-owner"
                          displayEmpty
                          value={values.account_owner}
                          onChange={(e) => setFieldValue('account_owner', e.target.value)}
                          input={<OutlinedInput placeholder="Select owner" />}
                          disabled={!values.apply_account_owner}
                          error={Boolean(touched.account_owner && errors.account_owner && values.apply_account_owner)}
                          renderValue={(selected) => {
                            if (!selected) return <Typography variant="subtitle1" color="text.secondary">Select owner (or leave empty to clear)</Typography>;
                            const u = users?.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{u ? `${u.first_name} ${u.last_name}` : '—'}</Typography>;
                          }}
                        >
                          <MenuItem value="">
                            <Typography color="text.secondary">None (clear owner)</Typography>
                          </MenuItem>
                          {(users || []).map((u) => (
                            <MenuItem key={u.id} value={String(u.id)}>
                              <ListItemText primary={`${u.first_name} ${u.last_name}`} secondary={u.email} />
                            </MenuItem>
                          ))}
                        </Select>
                        {touched.account_owner && errors.account_owner && values.apply_account_owner && (
                          <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                            {errors.account_owner}
                          </Typography>
                        )}
                      </FormControl>
                    )}
                  </Stack>
                </Grid>

                {/* TYPE */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={values.apply_type}
                          onChange={(e) => setFieldValue('apply_type', e.target.checked)}
                        />
                      }
                      label={
                        <Typography variant="subtitle1" fontWeight={values.apply_type ? 600 : 400}>
                          Update Type
                        </Typography>
                      }
                    />
                    
                    {values.apply_type && (
                      <FormControl fullWidth>
                        <Select
                          id="bulk-type"
                          displayEmpty
                          value={values.type}
                          onChange={(e) => setFieldValue('type', e.target.value)}
                          input={<OutlinedInput placeholder="Select type" />}
                          disabled={!values.apply_type}
                          renderValue={(selected) => {
                            if (!selected) return <Typography variant="subtitle1" color="text.secondary">Select type (or leave empty to clear)</Typography>;
                            const t = types?.find((x) => x.value === selected);
                            return <Typography variant="subtitle2">{t?.label || selected}</Typography>;
                          }}
                        >
                          <MenuItem value="">
                            <Typography color="text.secondary">None (clear type)</Typography>
                          </MenuItem>
                          {(types || []).map((t) => (
                            <MenuItem key={t.value} value={t.value}>
                              <ListItemText primary={t.label} />
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    )}
                  </Stack>
                </Grid>

                {/* CLASSIFICATION */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={values.apply_classification}
                          onChange={(e) => setFieldValue('apply_classification', e.target.checked)}
                        />
                      }
                      label={
                        <Typography variant="subtitle1" fontWeight={values.apply_classification ? 600 : 400}>
                          Update Classification
                        </Typography>
                      }
                    />
                    
                    {values.apply_classification && (
                      <FormControl fullWidth>
                        <Select
                          id="bulk-classification"
                          displayEmpty
                          value={values.classification}
                          onChange={(e) => setFieldValue('classification', e.target.value)}
                          input={<OutlinedInput placeholder="Select classification" />}
                          disabled={!values.apply_classification}
                          renderValue={(selected) => {
                            if (!selected) return <Typography variant="subtitle1" color="text.secondary">Select classification (or leave empty to clear)</Typography>;
                            const c = classifications?.find((x) => x.value === selected);
                            return <Typography variant="subtitle2">{c?.label || selected}</Typography>;
                          }}
                        >
                          <MenuItem value="">
                            <Typography color="text.secondary">None (clear classification)</Typography>
                          </MenuItem>
                          {(classifications || []).map((c) => (
                            <MenuItem key={c.value} value={c.value}>
                              <ListItemText primary={c.label} />
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    )}
                  </Stack>
                </Grid>

                {/* PARENT COMPANY */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={values.apply_parent}
                          onChange={(e) => setFieldValue('apply_parent', e.target.checked)}
                        />
                      }
                      label={
                        <Typography variant="subtitle1" fontWeight={values.apply_parent ? 600 : 400}>
                          Update Parent Company
                        </Typography>
                      }
                    />
                    
                    {values.apply_parent && (
                      <FormControl fullWidth>
                        <Select
                          id="bulk-parent"
                          displayEmpty
                          value={values.parent}
                          onChange={(e) => setFieldValue('parent', e.target.value)}
                          input={<OutlinedInput placeholder="Select parent company" />}
                          disabled={!values.apply_parent}
                          error={Boolean(touched.parent && errors.parent && values.apply_parent)}
                          renderValue={(selected) => {
                            if (!selected) return <Typography variant="subtitle1" color="text.secondary">Select parent (or leave empty to clear)</Typography>;
                            const p = availableParents?.find((x) => String(x.id) === String(selected));
                            return <Typography variant="subtitle2">{p?.company_name || '—'}</Typography>;
                          }}
                        >
                          <MenuItem value="">
                            <Typography color="text.secondary">None (clear parent)</Typography>
                          </MenuItem>
                          {availableParents.map((p) => (
                            <MenuItem key={p.id} value={String(p.id)}>
                              <ListItemText primary={p.company_name} />
                            </MenuItem>
                          ))}
                        </Select>
                        {touched.parent && errors.parent && values.apply_parent && (
                          <Typography variant="caption" color="error" sx={{ mt: 0.5 }}>
                            {errors.parent}
                          </Typography>
                        )}
                      </FormControl>
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
                    {isProcessing ? 'Processing...' : `Update ${selectedCount} Account${selectedCount !== 1 ? 's' : ''}`}
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

FormAccountBulkEdit.propTypes = {
  closeModal: PropTypes.func,
  selectedAccountIds: PropTypes.array.isRequired,
  selectedCount: PropTypes.number.isRequired
};

export default React.memo(FormAccountBulkEdit);