// frontend/src/sections/accounts/activities/components/InlineCycleForm.jsx
/**
 * Inline Cycle Form Component
 * 
 * Quick-create decision cycle form for use in modals.
 * Includes cycle name and initial pipeline step selection.
 */

'use client';

import PropTypes from 'prop-types';
import { useState } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// icons
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// project imports
import { displayErrorSnackbar } from 'utils/displayError';

// ==============================|| PIPELINE STEPS (FIXED) ||============================== //

export const PIPELINE_STEPS = [
  { value: 'QUALIFICATION', label: 'Qualification' },
  { value: 'TECHNICAL_FIT', label: 'Technical Fit' },
  { value: 'SOLUTION_VALIDATION', label: 'Solution Validation' },
  { value: 'BUSINESS_CASE', label: 'Business Case' },
  { value: 'CLOSING', label: 'Closing' },
  { value: 'IMPLEMENTATION', label: 'Implementation' },
  { value: 'GO_LIVE', label: 'Go Live' },
];

// ==============================|| INLINE CYCLE FORM ||============================== //

export default function InlineCycleForm({ onSave, onCancel }) {
  const [name, setName] = useState('');
  const [stepStage, setStepStage] = useState('QUALIFICATION');

  const handleSave = () => {
    if (!name.trim()) {
      displayErrorSnackbar('Cycle name is required');
      return;
    }
    onSave({
      name: name.trim(),
      is_active: true,
      step_stage: stepStage
    });
  };

  return (
    <Box sx={{ pt: 1, pb: 2 }}>
      <Stack spacing={2}>
        <Typography variant="body2" color="text.secondary">
          Quick create a new decision cycle
        </Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6}>
            <TextField
              fullWidth
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Cycle name *"
              autoFocus
            />
          </Grid>
          <Grid item xs={12} sm={6}>
            <Select
              fullWidth
              value={stepStage}
              onChange={(e) => setStepStage(e.target.value)}
              displayEmpty
            >
              {PIPELINE_STEPS.map((step) => (
                <MenuItem key={step.value} value={step.value}>
                  {step.label}
                </MenuItem>
              ))}
            </Select>
          </Grid>
        </Grid>
        <Stack direction="row" spacing={1} justifyContent="flex-end">
          <Button size="small" onClick={onCancel} startIcon={<CloseOutlined />}>
            Cancel
          </Button>
          <Button size="small" variant="contained" onClick={handleSave}>
            Create Cycle
          </Button>
        </Stack>
      </Stack>
    </Box>
  );
}

InlineCycleForm.propTypes = {
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired
};