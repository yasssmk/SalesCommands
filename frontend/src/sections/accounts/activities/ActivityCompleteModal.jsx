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
import { useTheme } from '@mui/material/styles';
import Alert from '@mui/material/Alert';
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
  ACTIVITY_OUTCOME_LABELS,
  NO_NEXT_STEP_REASON_LABELS
} from 'api/accounts/activities';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// assets
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import TrophyOutlined from '@ant-design/icons/TrophyOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import PauseCircleOutlined from '@ant-design/icons/PauseCircleOutlined';
import StopOutlined from '@ant-design/icons/StopOutlined';
import InfoCircleOutlined from '@ant-design/icons/InfoCircleOutlined';

// ==============================|| VALIDATION SCHEMA ||============================== //

// Validation schema is built dynamically based on needsNoNextStepReason
const buildValidationSchema = (needsReason) => Yup.object({
  outcome: Yup.string()
    .required('Please select an outcome'),
  outcome_notes: Yup.string()
    .max(2000, 'Notes must be at most 2000 characters')
    .nullable(),
  no_next_step_reason: needsReason
    ? Yup.string().required('Please select a reason for no next step')
    : Yup.string().nullable(),
  other_reason_text: Yup.string()
    .when('no_next_step_reason', {
      is: 'OTHER',
      then: (schema) => needsReason ? schema.required('Please enter a reason') : schema,
      otherwise: (schema) => schema.nullable()
    })
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
  const theme = useTheme();
  const [submitting, setSubmitting] = useState(false);

  // Determine if no_next_step_reason is required
  // Same logic as OutcomeTab: activity in a cycle with no pending next step
  const effectiveHasNextStep = activity?.effective_has_next_step;
  const needsNoNextStepReason = effectiveHasNextStep !== true 
    && activity?.status !== 'COMPLETED' 
    && activity?.status !== 'CANCELLED';

  // Build reason string for API
  const buildReasonString = (reason, otherText) => {
    if (!reason) return null;
    if (reason === 'OTHER') return `OTHER: ${otherText.trim()}`;
    return reason;
  };

  // Formik setup
  const formik = useFormik({
    initialValues: {
      outcome: '',
      outcome_notes: '',
      no_next_step_reason: '',
      other_reason_text: ''
    },
    validationSchema: buildValidationSchema(needsNoNextStepReason),
    enableReinitialize: false,
    onSubmit: async (values) => {
      if (!activity?.id) return;
      
      setSubmitting(true);
      try {
        // Build payload
        const payload = {
          outcome: values.outcome,
          outcome_notes: values.outcome_notes?.trim() || null
        };

        // Include no_next_step_reason if required
        if (needsNoNextStepReason && values.no_next_step_reason) {
          payload.next_step_agreed = false;
          payload.no_next_step_reason = buildReasonString(
            values.no_next_step_reason,
            values.other_reason_text
          );
        }

        const result = await completeActivity(activity.id, payload);
        
        if (result.success) {
          displaySuccessSnackbar('Activity completed successfully');
          onSuccess?.(result.data);
          handleClose();
        } else {
          displayErrorSnackbar({
            message: result.error || 'Failed to complete activity',
            status: result.status
          });
        }
      } catch (err) {
        displayErrorSnackbar({
          message: err?.message || 'An unexpected error occurred',
          status: 500
        });
      } finally {
        setSubmitting(false);
      }
    }
  });

  const { values, errors, touched, handleChange, handleBlur, handleSubmit, resetForm, setFieldValue } = formik;
  
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

              {/* No Next Step Reason — shown when activity is in a cycle with no pending next step */}
              {needsNoNextStepReason && (
                <Grid item xs={12}>
                  <Alert 
                    severity="warning" 
                    icon={<InfoCircleOutlined />}
                    sx={{ mb: 2 }}
                  >
                    <Typography variant="caption">
                      No follow-up activity is scheduled. Please indicate why.
                    </Typography>
                  </Alert>
                  <Stack spacing={1.5}>
                    <InputLabel htmlFor="no_next_step_reason" required>
                      Reason for no next step
                    </InputLabel>
                    <Select
                      id="no_next_step_reason"
                      name="no_next_step_reason"
                      fullWidth
                      value={values.no_next_step_reason}
                      onChange={(e) => {
                        handleChange(e);
                        // Clear other text when switching away from OTHER
                        if (e.target.value !== 'OTHER') {
                          setFieldValue('other_reason_text', '');
                        }
                      }}
                      onBlur={handleBlur}
                      error={Boolean(touched.no_next_step_reason && errors.no_next_step_reason)}
                      displayEmpty
                    >
                      <MenuItem value="" disabled>
                        <em>Select a reason...</em>
                      </MenuItem>
                      <MenuItem value="CLOSE_WON">
                        <Stack direction="row" spacing={1} alignItems="center">
                          <TrophyOutlined style={{ color: theme.palette.success.main }} />
                          <span>{NO_NEXT_STEP_REASON_LABELS.CLOSE_WON}</span>
                        </Stack>
                      </MenuItem>
                      <MenuItem value="CLOSE_LOST">
                        <Stack direction="row" spacing={1} alignItems="center">
                          <CloseCircleOutlined style={{ color: theme.palette.error.main }} />
                          <span>{NO_NEXT_STEP_REASON_LABELS.CLOSE_LOST}</span>
                        </Stack>
                      </MenuItem>
                      <MenuItem value="ON_HOLD">
                        <Stack direction="row" spacing={1} alignItems="center">
                          <PauseCircleOutlined style={{ color: theme.palette.warning.main }} />
                          <span>{NO_NEXT_STEP_REASON_LABELS.ON_HOLD}</span>
                        </Stack>
                      </MenuItem>
                      <MenuItem value="NOT_QUALIFIED">
                        <Stack direction="row" spacing={1} alignItems="center">
                          <StopOutlined style={{ color: theme.palette.grey[500] }} />
                          <span>{NO_NEXT_STEP_REASON_LABELS.NOT_QUALIFIED}</span>
                        </Stack>
                      </MenuItem>
                      <MenuItem value="OTHER">
                        <Stack direction="row" spacing={1} alignItems="center">
                          <span>Other reason...</span>
                        </Stack>
                      </MenuItem>
                    </Select>
                    {touched.no_next_step_reason && errors.no_next_step_reason && (
                      <FormHelperText error>{errors.no_next_step_reason}</FormHelperText>
                    )}

                    {/* Other reason text input */}
                    {values.no_next_step_reason === 'OTHER' && (
                      <TextField
                        fullWidth
                        size="small"
                        name="other_reason_text"
                        placeholder="Enter reason..."
                        value={values.other_reason_text}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        error={Boolean(touched.other_reason_text && errors.other_reason_text)}
                        helperText={touched.other_reason_text && errors.other_reason_text}
                      />
                    )}
                  </Stack>
                </Grid>
              )}
              
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
    title: PropTypes.string,
    status: PropTypes.string,
    effective_has_next_step: PropTypes.bool,
    decision_cycle: PropTypes.string
  }),
  onSuccess: PropTypes.func
};