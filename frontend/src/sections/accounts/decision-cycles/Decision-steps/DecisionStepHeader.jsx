// frontend/src/sections/accounts/decision-cycles/DecisionStepHeader.jsx

'use client';

import { useState } from 'react';
import PropTypes from 'prop-types';

// MUI
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';

// Project imports
import MainCard from 'components/MainCard';

// Icons
import {
  EditOutlined,
  CheckOutlined,
  CloseOutlined,
} from '@ant-design/icons';

// Date formatting
import { format } from 'date-fns';

// ==============================|| CONFIGURATION ||============================== //

/**
 * Step derived status config — read-only display.
 * Status is 100% derived from activities by backend.
 */
const STATUS_CONFIG = {
  WON: { color: 'primary', label: 'Won' },
  REJECTED: { color: 'error', label: 'Rejected' },
  OVERDUE: { color: 'error', label: 'Overdue' },
  VALIDATED: { color: 'primary', label: 'Validated' },
  IN_PROGRESS: { color: 'secondary', label: 'In Progress' },
  ON_HOLD: { color: 'warning', label: 'On Hold' },
  IN_CHASING: { color: 'warning', label: 'In Chasing' },
  NOT_STARTED: { color: 'default', label: 'Not Started' }
};

/**
 * Pipeline Step Labels (7 fixed steps)
 */
const PIPELINE_STEP_LABELS = {
  QUALIFICATION: 'Qualification',
  TECHNICAL_FIT: 'Technical Fit',
  SOLUTION_VALIDATION: 'Solution Validation',
  BUSINESS_CASE: 'Business Case',
  CLOSING: 'Closing',
  IMPLEMENTATION: 'Implementation',
  GO_LIVE: 'Go Live'
};

// Legacy alias
const STAGE_LABELS = PIPELINE_STEP_LABELS;

// ==============================|| STEP HEADER ||============================== //

export default function StepHeader({ step, account, cycleId, onSave, onUpdate }) {

  // Edit name state
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState(step?.name || '');
  const [saving, setSaving] = useState(false);

  // Derived status (read-only, computed by backend from activities)
  const statusConfig = STATUS_CONFIG[step?.derived_status] || STATUS_CONFIG.NOT_STARTED;

  // ==============================|| HANDLERS ||============================== //

  // Handle name save
  const handleNameSave = async () => {
    if (nameValue === step?.name) {
      setEditingName(false);
      return;
    }
    setSaving(true);
    const success = await onSave('name', nameValue);
    setSaving(false);
    if (success) {
      setEditingName(false);
    }
  };

  // Handle name cancel
  const handleNameCancel = () => {
    setNameValue(step?.name || '');
    setEditingName(false);
  };

  return (
    <>
      <MainCard sx={{ mb: 0, borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}>
        <Stack spacing={2}>
          {/* Row 1: Title + Status/Stage chips */}
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Stack direction="row" spacing={2} alignItems="center" flex={1}>

              {/* Name - Inline Editable */}
              {editingName ? (
                <Stack direction="row" spacing={1} alignItems="center" flex={1}>
                  <TextField
                    value={nameValue}
                    onChange={(e) => setNameValue(e.target.value)}
                    size="small"
                    fullWidth
                    autoFocus
                    disabled={saving}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleNameSave();
                      if (e.key === 'Escape') handleNameCancel();
                    }}
                  />
                  <IconButton size="small" onClick={handleNameSave} disabled={saving} color="success">
                    <CheckOutlined />
                  </IconButton>
                  <IconButton size="small" onClick={handleNameCancel} disabled={saving} color="error">
                    <CloseOutlined />
                  </IconButton>
                </Stack>
              ) : (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="h4">{step?.name}</Typography>
                  <IconButton size="small" onClick={() => setEditingName(true)}>
                    <EditOutlined />
                  </IconButton>
                </Stack>
              )}
            </Stack>

            {/* Status + Stage Chips */}
            <Stack direction="row" spacing={1} alignItems="center">
              {/* Stage Chip (fixed) */}
              <Chip
                label={STAGE_LABELS[step?.stage] || step?.stage}
                size="small"
                variant="outlined"
              />
              
              {/* Derived Status Chip (read-only) */}
              <Chip
                label={step?.derived_status_display || statusConfig.label}
                color={statusConfig.color}
                size="small"
              />
            </Stack>
          </Stack>

          {/* Meta info */}
            <Stack direction="row" spacing={2} divider={<Divider orientation="vertical" flexItem />}>
              <Typography variant="body2" color="text.secondary">
                <strong>Account:</strong> {account?.company_name || '-'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Expected End:</strong> {step?.expected_end ? format(new Date(step.expected_end), 'MMM d, yyyy') : 'Not set'}
              </Typography>
            </Stack>

          </Stack>
      </MainCard>
    </>
  );
}

StepHeader.propTypes = {
  step: PropTypes.object.isRequired,
  account: PropTypes.object,
  cycleId: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};
