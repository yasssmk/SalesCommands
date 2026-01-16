// frontend/src/sections/accounts/activities/ActivityModal.jsx
/**
 * Activity Modal Component
 * 
 * Modal for creating and editing activities.
 * Follows DecisionCycleModal and ContactModal patterns.
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect, useMemo } from 'react';

// material-ui
import Autocomplete from '@mui/material/Autocomplete';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Modal from '@mui/material/Modal';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormHelperText from '@mui/material/FormHelperText';

// date pickers
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';

// third-party
import { useFormik } from 'formik';
import * as Yup from 'yup';

// project imports
import MainCard from 'components/MainCard';
import { 
  createActivity, 
  updateActivity,
  useGetActivityChoices,
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUSES,
  ACTIVITY_STATUS_LABELS
} from 'api/accounts/activities';
import { useGetContacts } from 'api/businessData/contacts';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  title: Yup.string()
    .required('Title is required')
    .max(255, 'Title must be at most 255 characters'),
  activity_type: Yup.string()
    .required('Activity type is required'),
  status: Yup.string()
    .required('Status is required'),
  description: Yup.string()
    .max(2000, 'Description must be at most 2000 characters')
    .nullable(),
  call_to_action: Yup.string()
    .max(500, 'Call to action must be at most 500 characters')
    .nullable(),
  scheduled_date: Yup.date()
    .nullable(),
  due_date: Yup.date()
    .nullable()
});

// ==============================|| ACTIVITY MODAL ||============================== //

/**
 * ActivityModal Component
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} onClose - Close modal callback
 * @param {Object} activity - Existing activity for edit mode (null for create)
 * @param {string} accountId - Parent account UUID (required for create)
 * @param {string} decisionStepId - Optional decision step UUID to link
 * @param {string} decisionCycleId - Optional decision cycle UUID to link
 * @param {Function} onSuccess - Success callback with created/updated activity
 */
export default function ActivityModal({ 
  open, 
  onClose, 
  activity = null,
  accountId,
  decisionStepId = null,
  decisionCycleId = null,
  defaultActivityType = null,
  onSuccess
}) {
  const [submitting, setSubmitting] = useState(false);
  
  const isEditMode = Boolean(activity?.id);
  
  // Fetch choices
  const { choicesLoading } = useGetActivityChoices();
  
  // Fetch contacts for the account
  const { contacts, contactsLoading } = useGetContacts({ 
    filters: { account_id: accountId },
    pageSize: 100 
  });

  // Contact options for autocomplete
  const contactOptions = useMemo(() => {
    if (!contacts || contacts.length === 0) return [];
    return contacts.map(contact => ({
      id: contact.id,
      label: `${contact.first_name || ''} ${contact.last_name || ''}`.trim() || contact.email,
      email: contact.email,
      job_title: contact.job_title
    }));
  }, [contacts]);

  // Build initial values
  const initialValues = useMemo(() => ({
    title: activity?.title || '',
    activity_type: activity?.activity_type || defaultActivityType || 'MEETING',
    status: activity?.status || 'PLANNED',
    description: activity?.description || '',
    call_to_action: activity?.call_to_action || '',
    scheduled_date: activity?.scheduled_date ? dayjs(activity.scheduled_date) : null,
    scheduled_time: activity?.scheduled_time ? dayjs(`2000-01-01T${activity.scheduled_time}`) : null,
    due_date: activity?.due_date ? dayjs(activity.due_date) : null,
    contact_ids: activity?.contacts?.map(c => c.id) || []
  }), [activity, defaultActivityType]);

  // Formik setup
  const formik = useFormik({
    initialValues,
    validationSchema,
    enableReinitialize: true,
    onSubmit: async (values) => {
      setSubmitting(true);
      
      try {
        // Build payload
        const payload = {
          title: values.title.trim(),
          activity_type: values.activity_type,
          status: values.status,
          description: values.description?.trim() || null,
          call_to_action: values.call_to_action?.trim() || null,
          scheduled_date: values.scheduled_date ? dayjs(values.scheduled_date).format('YYYY-MM-DD') : null,
          scheduled_time: values.scheduled_time ? dayjs(values.scheduled_time).format('HH:mm:ss') : null,
          due_date: values.due_date ? dayjs(values.due_date).format('YYYY-MM-DD') : null,
          contact_ids: values.contact_ids || []
        };
        
        // Add relations for create mode
        if (!isEditMode) {
          payload.account_id = accountId;
          if (decisionStepId) payload.decision_step_id = decisionStepId;
          if (decisionCycleId) payload.decision_cycle_id = decisionCycleId;
        }
        
        let result;
        
        if (isEditMode) {
          result = await updateActivity(activity.id, payload);
        } else {
          result = await createActivity(payload);
        }
        
        if (result.success) {
          displaySuccessSnackbar(
            isEditMode 
              ? 'Activity updated successfully' 
              : 'Activity created successfully'
          );
          onSuccess?.(result.data);
          handleClose();
        } else {
          displayErrorSnackbar(result.error || 'Failed to save activity');
        }
      } catch (error) {
        displayErrorSnackbar(error.message || 'An error occurred');
      } finally {
        setSubmitting(false);
      }
    }
  });

  const { values, errors, touched, handleChange, handleBlur, handleSubmit, resetForm, setFieldValue } = formik;
  
  // Reset form when modal opens/closes
  useEffect(() => {
    if (open) {
      resetForm({ values: initialValues });
    }
  }, [open, initialValues, resetForm]);
  
  const handleClose = () => {
    resetForm();
    onClose();
  };

  // Selected contacts for display
  const selectedContacts = useMemo(() => {
    return contactOptions.filter(c => values.contact_ids.includes(c.id));
  }, [contactOptions, values.contact_ids]);

  // ==============================|| RENDER ||============================== //

  if (choicesLoading) {
    return (
      <Modal open={open} onClose={handleClose}>
        <MainCard
          sx={{
            width: 'calc(100% - 48px)',
            maxWidth: 600,
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)'
          }}
          modal
          content={false}
        >
          <Box sx={{ p: 4, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress />
          </Box>
        </MainCard>
      </Modal>
    );
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="modal-activity-title"
      sx={{
        '& .MuiPaper-root:focus': { outline: 'none' }
      }}
    >
      <MainCard
        sx={{
          width: 'calc(100% - 48px)',
          minWidth: 340,
          maxWidth: 600,
          maxHeight: 'calc(100vh - 48px)',
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)'
        }}
        modal
        content={false}
      >
        <Box
          sx={{
            maxHeight: 'calc(100vh - 48px)',
            overflowY: 'auto'
          }}
        >
          <Box component="form" onSubmit={handleSubmit}>
            {/* Header */}
            <Box sx={{ p: 2.5, pb: 2 }}>
              <Typography variant="h5" id="modal-activity-title">
                {isEditMode ? 'Edit Activity' : 'Create Activity'}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {isEditMode 
                  ? 'Update activity details'
                  : 'Add a new activity to track your sales actions'
                }
              </Typography>
            </Box>
            
            <Divider />
            
            {/* Form Content */}
            <Box sx={{ p: 2.5 }}>
              <Grid container spacing={2.5}>
                
                {/* Title */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="title" required>Title</InputLabel>
                    <TextField
                      id="title"
                      name="title"
                      fullWidth
                      placeholder="e.g., Follow-up call with John"
                      value={values.title}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(touched.title && errors.title)}
                      helperText={touched.title && errors.title}
                    />
                  </Stack>
                </Grid>
                
                {/* Activity Type */}
                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="activity_type" required>Type</InputLabel>
                    <Select
                      id="activity_type"
                      name="activity_type"
                      fullWidth
                      value={values.activity_type}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(touched.activity_type && errors.activity_type)}
                    >
                      {Object.entries(ACTIVITY_TYPES).map(([key, value]) => (
                        <MenuItem key={key} value={value}>
                          {ACTIVITY_TYPE_LABELS[key]}
                        </MenuItem>
                      ))}
                    </Select>
                    {touched.activity_type && errors.activity_type && (
                      <FormHelperText error>{errors.activity_type}</FormHelperText>
                    )}
                  </Stack>
                </Grid>
                
                {/* Status */}
                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="status" required>Status</InputLabel>
                    <Select
                      id="status"
                      name="status"
                      fullWidth
                      value={values.status}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(touched.status && errors.status)}
                    >
                      {Object.entries(ACTIVITY_STATUSES).map(([key, value]) => (
                        <MenuItem key={key} value={value}>
                          {ACTIVITY_STATUS_LABELS[key]}
                        </MenuItem>
                      ))}
                    </Select>
                    {touched.status && errors.status && (
                      <FormHelperText error>{errors.status}</FormHelperText>
                    )}
                  </Stack>
                </Grid>
                
                {/* Scheduled Date */}
                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel>Scheduled Date</InputLabel>
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                      <DatePicker
                        value={values.scheduled_date}
                        onChange={(newValue) => setFieldValue('scheduled_date', newValue)}
                        slotProps={{
                          textField: {
                            fullWidth: true,
                            error: Boolean(touched.scheduled_date && errors.scheduled_date),
                            helperText: touched.scheduled_date && errors.scheduled_date
                          }
                        }}
                      />
                    </LocalizationProvider>
                  </Stack>
                </Grid>
                
                {/* Scheduled Time */}
                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel>Scheduled Time</InputLabel>
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                      <TimePicker
                        value={values.scheduled_time}
                        onChange={(newValue) => setFieldValue('scheduled_time', newValue)}
                        slotProps={{
                          textField: {
                            fullWidth: true
                          }
                        }}
                      />
                    </LocalizationProvider>
                  </Stack>
                </Grid>
                
                {/* Due Date */}
                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel>Due Date</InputLabel>
                    <LocalizationProvider dateAdapter={AdapterDayjs}>
                      <DatePicker
                        value={values.due_date}
                        onChange={(newValue) => setFieldValue('due_date', newValue)}
                        slotProps={{
                          textField: {
                            fullWidth: true,
                            error: Boolean(touched.due_date && errors.due_date),
                            helperText: touched.due_date && errors.due_date
                          }
                        }}
                      />
                    </LocalizationProvider>
                  </Stack>
                </Grid>
                
                {/* Contacts */}
                <Grid item xs={12} sm={6}>
                  <Stack spacing={1}>
                    <InputLabel>Contacts</InputLabel>
                    <Autocomplete
                      multiple
                      id="contact_ids"
                      options={contactOptions}
                      loading={contactsLoading}
                      value={selectedContacts}
                      onChange={(event, newValue) => {
                        setFieldValue('contact_ids', newValue.map(c => c.id));
                      }}
                      getOptionLabel={(option) => option.label || ''}
                      isOptionEqualToValue={(option, value) => option.id === value.id}
                      renderInput={(params) => (
                        <TextField
                          {...params}
                          placeholder="Select contacts..."
                          InputProps={{
                            ...params.InputProps,
                            endAdornment: (
                              <>
                                {contactsLoading ? <CircularProgress color="inherit" size={20} /> : null}
                                {params.InputProps.endAdornment}
                              </>
                            )
                          }}
                        />
                      )}
                      renderOption={(props, option) => (
                        <li {...props} key={option.id}>
                          <Stack>
                            <Typography variant="body2">{option.label}</Typography>
                            {option.job_title && (
                              <Typography variant="caption" color="text.secondary">
                                {option.job_title}
                              </Typography>
                            )}
                          </Stack>
                        </li>
                      )}
                    />
                  </Stack>
                </Grid>
                
                {/* Call to Action */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="call_to_action">Call to Action</InputLabel>
                    <TextField
                      id="call_to_action"
                      name="call_to_action"
                      fullWidth
                      placeholder="e.g., Ask about budget timeline"
                      value={values.call_to_action}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(touched.call_to_action && errors.call_to_action)}
                      helperText={touched.call_to_action && errors.call_to_action}
                    />
                  </Stack>
                </Grid>
                
                {/* Description */}
                <Grid item xs={12}>
                  <Stack spacing={1}>
                    <InputLabel htmlFor="description">Description</InputLabel>
                    <TextField
                      id="description"
                      name="description"
                      fullWidth
                      multiline
                      rows={3}
                      placeholder="Additional details about this activity..."
                      value={values.description}
                      onChange={handleChange}
                      onBlur={handleBlur}
                      error={Boolean(touched.description && errors.description)}
                      helperText={touched.description && errors.description}
                    />
                  </Stack>
                </Grid>
                
              </Grid>
            </Box>
            
            <Divider />
            
            {/* Actions */}
            <Box sx={{ p: 2.5 }}>
              <Stack direction="row" spacing={2} justifyContent="flex-end">
                <Button color="error" onClick={handleClose}>
                  Cancel
                </Button>
                <Button 
                  type="submit" 
                  variant="contained" 
                  disabled={submitting}
                  startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : null}
                >
                  {submitting 
                    ? (isEditMode ? 'Updating...' : 'Creating...') 
                    : (isEditMode ? 'Update' : 'Create')
                  }
                </Button>
              </Stack>
            </Box>
          </Box>
        </Box>
      </MainCard>
    </Modal>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  activity: PropTypes.object,
  accountId: PropTypes.string,
  decisionStepId: PropTypes.string,
  decisionCycleId: PropTypes.string,
  defaultActivityType: PropTypes.string,
  onSuccess: PropTypes.func
};