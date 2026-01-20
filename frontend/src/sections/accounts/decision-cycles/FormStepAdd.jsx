// frontend/src/sections/accounts/decision-cycles/FormStepAdd.jsx
/**
 * Form for creating a new Decision Step
 * 
 * Features:
 * - Stage selection (required)
 * - Name input (required)
 * - Status selection
 * - Stakeholder and department
 * - Description and goal
 * - Expected days
 */

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
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
import CircularProgress from '@mui/material/CircularProgress';

// third-party
import { useFormik } from 'formik';
import * as Yup from 'yup';

// date picker
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';

/// project imports
import { 
  createDecisionStep, 
  useGetDecisionCycleChoices,
  DECISION_STAGES,
  DECISION_STEP_STATUSES
} from 'api/accounts/decisionCycles';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| VALIDATION SCHEMA ||============================== //

const validationSchema = Yup.object({
  name: Yup.string()
    .required('Step name is required')
    .max(255, 'Name must be at most 255 characters'),
  stage: Yup.string()
    .required('Stage is required')
    .oneOf(Object.keys(DECISION_STAGES), 'Invalid stage'),
  status: Yup.string()
    .oneOf(Object.keys(DECISION_STEP_STATUSES), 'Invalid status'),
  expected_end: Yup.date()
    .required('Expected end date is required')
    .min(new Date(), 'Expected end date must be in the future'),
  stakeholder: Yup.string()
    .max(255, 'Stakeholder must be at most 255 characters'),
  description: Yup.string(),
  goal: Yup.string()
});

// ==============================|| FORM STEP ADD ||============================== //

/**
 * FormStepAdd Component
 * 
 * @param {string} cycleId - Parent cycle UUID
 * @param {string} defaultStage - Pre-selected stage
 * @param {Function} closeModal - Close modal callback
 * @param {Function} onSuccess - Success callback with created step data
 */
export default function FormStepAdd({ cycleId, defaultStage, closeModal, onSuccess }) {
  
  const [submitting, setSubmitting] = useState(false);
  
  // Fetch choices
  const { stages, statuses, choicesLoading } = useGetDecisionCycleChoices();

  // Formik setup
  const formik = useFormik({
    initialValues: {
      name: '',
      stage: defaultStage || '',
      status: 'NOT_STARTED',
      expected_end: null,
      stakeholder: '',
      description: '',
      goal: ''
    },
    validationSchema,
    onSubmit: async (values) => {
      setSubmitting(true);
      
      try {
        // Prepare payload
        const payload = {
          cycle_id: cycleId,
          name: values.name.trim(),
          stage: values.stage,
          status: values.status || 'NOT_STARTED',
          expected_end: values.expected_end ? dayjs(values.expected_end).format('YYYY-MM-DD') : null,
          stakeholder: values.stakeholder?.trim() || null,
          description: values.description?.trim() || null,
          goal: values.goal?.trim() || null
        };
        
        const result = await createDecisionStep(payload);
        
        if (result.success) {
          displaySuccessSnackbar('Decision step created successfully');
          onSuccess?.(result.data);
        } else {
          displayErrorSnackbar(result.error || 'Failed to create step');
        }
      } catch (error) {
        displayErrorSnackbar(error.message || 'An error occurred');
      } finally {
        setSubmitting(false);
      }
    }
  });

  const { values, errors, touched, handleChange, handleBlur, handleSubmit, setFieldValue } = formik;

  // ==============================|| RENDER ||============================== //

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {/* Header */}
      <Box sx={{ p: 2.5, pb: 2 }}>
        <Typography variant="h5">Add Decision Step</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Create a new step in the decision cycle
        </Typography>
      </Box>
      
      <Divider />
      
      {/* Form Content */}
      <Box sx={{ p: 2.5 }}>
        <Grid container spacing={2.5}>
          
          {/* Name */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <InputLabel required>Step Name</InputLabel>
              <TextField
                fullWidth
                name="name"
                placeholder="e.g., Technical Demo, Budget Approval..."
                value={values.name}
                onChange={handleChange}
                onBlur={handleBlur}
                error={touched.name && Boolean(errors.name)}
                helperText={touched.name && errors.name}
                autoFocus
              />
            </Stack>
          </Grid>
          
          {/* Stage */}
          <Grid item xs={12} sm={6}>
            <Stack spacing={1}>
              <InputLabel required>Stage</InputLabel>
              <FormControl fullWidth error={touched.stage && Boolean(errors.stage)}>
                <Select
                  name="stage"
                  value={values.stage}
                  onChange={handleChange}
                  onBlur={handleBlur}
                  displayEmpty
                >
                  <MenuItem value="" disabled>
                    <em>Select a stage</em>
                  </MenuItem>
                  {(stages.length > 0 ? stages : Object.entries(DECISION_STAGES).map(([key]) => ({
                    value: key,
                    label: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
                  }))).map((stage) => (
                    <MenuItem key={stage.value} value={stage.value}>
                      {stage.label}
                    </MenuItem>
                  ))}
                </Select>
                {touched.stage && errors.stage && (
                  <FormHelperText>{errors.stage}</FormHelperText>
                )}
              </FormControl>
            </Stack>
          </Grid>
          
          {/* Status */}
          <Grid item xs={12} sm={6}>
            <Stack spacing={1}>
              <InputLabel>Status</InputLabel>
              <FormControl fullWidth>
                <Select
                  name="status"
                  value={values.status}
                  onChange={handleChange}
                  onBlur={handleBlur}
                >
                  {(statuses.length > 0 ? statuses : Object.entries(DECISION_STEP_STATUSES).map(([key]) => ({
                    value: key,
                    label: key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
                  }))).map((status) => (
                    <MenuItem key={status.value} value={status.value}>
                      {status.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>
          </Grid>

          {/* Expected End Date */}
          <Grid item xs={12} sm={6}>
            <Stack spacing={1}>
              <InputLabel required>Expected End Date</InputLabel>
              <LocalizationProvider dateAdapter={AdapterDayjs}>
                <DatePicker
                  value={values.expected_end}
                  onChange={(newValue) => setFieldValue('expected_end', newValue)}
                  minDate={dayjs()}
                  slotProps={{
                    textField: {
                      fullWidth: true,
                      placeholder: 'When should this step be completed?',
                      error: touched.expected_end && Boolean(errors.expected_end),
                      helperText: touched.expected_end && errors.expected_end
                    }
                  }}
                />
              </LocalizationProvider>
            </Stack>
          </Grid>
          
          {/* Stakeholder */}
          <Grid item xs={12} sm={6}>
            <Stack spacing={1}>
              <InputLabel>Stakeholder</InputLabel>
              <TextField
                fullWidth
                name="stakeholder"
                placeholder="e.g., CTO, Procurement Manager..."
                value={values.stakeholder}
                onChange={handleChange}
                onBlur={handleBlur}
                error={touched.stakeholder && Boolean(errors.stakeholder)}
                helperText={touched.stakeholder && errors.stakeholder}
              />
            </Stack>
          </Grid>
          
          {/* Expected Days */}
          <Grid item xs={12} sm={6}>
            <Stack spacing={1}>
              <InputLabel>Expected Days</InputLabel>
              <TextField
                fullWidth
                name="expected_days"
                type="number"
                placeholder="e.g., 14"
                value={values.expected_days}
                onChange={handleChange}
                onBlur={handleBlur}
                error={touched.expected_days && Boolean(errors.expected_days)}
                helperText={touched.expected_days && errors.expected_days}
                inputProps={{ min: 1 }}
              />
            </Stack>
          </Grid>
          
          {/* Description */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <InputLabel>Description</InputLabel>
              <TextField
                fullWidth
                multiline
                rows={2}
                name="description"
                placeholder="What will be done in this step..."
                value={values.description}
                onChange={handleChange}
                onBlur={handleBlur}
              />
            </Stack>
          </Grid>
          
          {/* Goal */}
          <Grid item xs={12}>
            <Stack spacing={1}>
              <InputLabel>Goal</InputLabel>
              <TextField
                fullWidth
                multiline
                rows={2}
                name="goal"
                placeholder="What this step aims to achieve..."
                value={values.goal}
                onChange={handleChange}
                onBlur={handleBlur}
              />
            </Stack>
          </Grid>
          
        </Grid>
      </Box>
      
      <Divider />
      
      {/* Actions */}
      <Box sx={{ p: 2.5 }}>
        <Stack direction="row" spacing={2} justifyContent="flex-end">
          <Button 
            color="secondary" 
            onClick={closeModal}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button 
            type="submit" 
            variant="contained"
            disabled={submitting}
            startIcon={submitting ? <CircularProgress size={16} color="inherit" /> : null}
          >
            {submitting ? 'Creating...' : 'Create Step'}
          </Button>
        </Stack>
      </Box>
    </Box>
  );
}

FormStepAdd.propTypes = {
  cycleId: PropTypes.string.isRequired,
  defaultStage: PropTypes.string,
  closeModal: PropTypes.func.isRequired,
  onSuccess: PropTypes.func
};