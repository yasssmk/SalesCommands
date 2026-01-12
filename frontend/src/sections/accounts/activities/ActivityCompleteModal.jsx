// frontend/src/sections/accounts/activities/ActivityCompleteModal.jsx
/**
 * Activity Complete Modal Component
 * 
 * Modal for completing an activity with outcome selection.
 */

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
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

// third-party
import { useFormik } from 'formik';
import * as Yup from 'yup';

// project imports
import MainCard from 'components/MainCard';
import { 
  completeActivity,
  ACTIVITY_OUTCOMES,
  ACTIVITY_OUTCOME_LABELS
} from 'api/accounts/activities';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  outcome: Yup.string()
    .required('Please select an outcome'),
  outcome_notes: Yup.string()
    .max(2000, 'Notes must be at most 2000 characters')
    .nullable()
});

// ==============================|| ACTIVITY COMPLETE MODAL ||============================== //

/**
 * ActivityCompleteModal Component
 * 
 * @param {boolean} open - Modal open state
 * @param {Function} onClose - Close modal callback
 * @param {Object} activity - Activity to complete
 * @param {Function} onSuccess - Success callback
 */
export default function ActivityCompleteModal({ 
  open, 
  onClose, 
  activity,
  onSuccess
}) {
  const [submitting, setSubmitting] = useState(false);

  // Formik setup
  const formik = useFormik({
    initialValues: {
      outcome: '',
      outcome_notes: ''
    },
    validationSchema,
    onSubmit: async (values) => {
      if (!activity?.id) return;
      
      setSubmitting(true);
      
      try {
        const result = await completeActivity(activity.id, {
          outcome: values.outcome,
          outcome_notes: values.outcome_notes?.trim() || null
        });
        
        if (result.success) {
          displaySuccessSnackbar('Activity completed successfully');
          onSuccess?.(result.data);
          handleClose();
        } else {
          displayErrorSnackbar(result.error || 'Failed to complete activity');
        }
      } catch (error) {
        displayErrorSnackbar(error.message || 'An error occurred');
      } finally {
        setSubmitting(false);
      }
    }
  });

  const { values, errors, touched, handleChange, handleBlur, handleSubmit, resetForm } = formik;
  
  const handleClose = () => {
    resetForm();
    onClose();
  };

  // ==============================|| RENDER ||============================== //

  return (
    <Modal
      open={open}
      onClose={handleClose}
      aria-labelledby="modal-complete-title"
      sx={{
        '& .MuiPaper-root:focus': { outline: 'none' }
      }}
    >
      <MainCard
        sx={{
          width: 'calc(100% - 48px)',
          minWidth: 340,
          maxWidth: 480,
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)'
        }}
        modal
        content={false}
      >
        <Box component="form" onSubmit={handleSubmit}>
          {/* Header */}
          <Box sx={{ p: 2.5, pb: 2 }}>
            <Stack direction="row" alignItems="center" spacing={1.5}>
              <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
              <Typography variant="h5" id="modal-complete-title">
                Complete Activity
              </Typography>
            </Stack>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Mark &quot;{activity?.title}&quot; as completed
            </Typography>
          </Box>
          
          <Divider />
          
          {/* Form Content */}
          <Box sx={{ p: 2.5 }}>
            <Grid container spacing={2.5}>
              
              {/* Outcome */}
              <Grid item xs={12}>
                <Stack spacing={1}>
                  <InputLabel htmlFor="outcome" required>Outcome</InputLabel>
                  <Select
                    id="outcome"
                    name="outcome"
                    fullWidth
                    value={values.outcome}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    error={Boolean(touched.outcome && errors.outcome)}
                    displayEmpty
                  >
                    <MenuItem value="" disabled>
                      <em>Select an outcome...</em>
                    </MenuItem>
                    {Object.entries(ACTIVITY_OUTCOMES).map(([key, value]) => (
                      <MenuItem key={key} value={value}>
                        {ACTIVITY_OUTCOME_LABELS[key]}
                      </MenuItem>
                    ))}
                  </Select>
                  {touched.outcome && errors.outcome && (
                    <FormHelperText error>{errors.outcome}</FormHelperText>
                  )}
                </Stack>
              </Grid>
              
              {/* Notes */}
              <Grid item xs={12}>
                <Stack spacing={1}>
                  <InputLabel htmlFor="outcome_notes">Notes</InputLabel>
                  <TextField
                    id="outcome_notes"
                    name="outcome_notes"
                    fullWidth
                    multiline
                    rows={3}
                    placeholder="Add notes about the outcome..."
                    value={values.outcome_notes}
                    onChange={handleChange}
                    onBlur={handleBlur}
                    error={Boolean(touched.outcome_notes && errors.outcome_notes)}
                    helperText={touched.outcome_notes && errors.outcome_notes}
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
                color="success"
                disabled={submitting}
                startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : <CheckCircleOutlined />}
              >
                {submitting ? 'Completing...' : 'Complete'}
              </Button>
            </Stack>
          </Box>
        </Box>
      </MainCard>
    </Modal>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityCompleteModal.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  activity: PropTypes.shape({
    id: PropTypes.string,
    title: PropTypes.string
  }),
  onSuccess: PropTypes.func
};