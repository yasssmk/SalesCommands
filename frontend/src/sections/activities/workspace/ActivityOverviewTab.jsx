'use client';

import { useState, useCallback, useEffect  } from 'react';
import PropTypes from 'prop-types';

// MUI
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import Autocomplete from '@mui/material/Autocomplete';

// Date pickers
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';

// Project imports
import {
  ACTIVITY_TYPES,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_OUTCOMES,
  ACTIVITY_OUTCOME_LABELS,
  ACTIVITY_OUTCOME_COLORS
} from 'api/accounts/activities';
import { useGetContacts } from 'api/businessData/contacts';
import {
  useGetDecisionCyclesByAccount,
  useGetDecisionStepsByCycle
} from 'api/accounts/decisionCycles';


// Icons
import { EditOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons';


// ==============================|| EDITABLE FIELD COMPONENT ||============================== //

function EditableField({ label, value, fieldKey, onSave, type = 'text', options = [], displayValue }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (tempValue === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(fieldKey, tempValue);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value || '');
    setEditing(false);
  };

  const renderEditMode = () => {
    if (type === 'select') {
      return (
        <Select
          value={tempValue}
          onChange={(e) => setTempValue(e.target.value)}
          size="small"
          fullWidth
          autoFocus
          disabled={saving}
        >
          <MenuItem value="">
            <em>None</em>
          </MenuItem>
          {options.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </Select>
      );
    }

    if (type === 'textarea') {
      return (
        <TextField
          value={tempValue}
          onChange={(e) => setTempValue(e.target.value)}
          size="small"
          fullWidth
          multiline
          rows={4}
          autoFocus
          disabled={saving}
        />
      );
    }

    return (
      <TextField
        value={tempValue}
        onChange={(e) => setTempValue(e.target.value)}
        size="small"
        fullWidth
        autoFocus
        disabled={saving}
        onKeyDown={(e) => {
          if (e.key === 'Enter') handleSave();
          if (e.key === 'Escape') handleCancel();
        }}
      />
    );
  };

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" gutterBottom display="block">
        {label}
      </Typography>
      {editing ? (
        <Stack direction="row" spacing={1} alignItems="flex-start">
          <Box flex={1}>{renderEditMode()}</Box>
          <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
            <CheckOutlined />
          </IconButton>
          <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
            <CloseOutlined />
          </IconButton>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1} alignItems="center">
          <Box component="span" sx={{ typography: 'body1' }}>
            {displayValue || value || <span style={{ color: '#999' }}>-</span>}
          </Box>
          <IconButton size="small" onClick={() => setEditing(true)}>
            <EditOutlined />
          </IconButton>
        </Stack>
      )}
    </Box>
  );
}

// ==============================|| EDITABLE DATE FIELD ||============================== //

function EditableDateField({ label, value, fieldKey, onSave }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value ? dayjs(value) : null);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    const formattedDate = tempValue ? tempValue.format('YYYY-MM-DD') : null;
    const success = await onSave(fieldKey, formattedDate);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value ? dayjs(value) : null);
    setEditing(false);
  };

  const displayValue = value ? dayjs(value).format('MMM D, YYYY') : '-';

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>

      <Box>
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          {label}
        </Typography>
        {editing ? (
          <Stack direction="row" spacing={1} alignItems="center">
            <DatePicker
              value={tempValue}
              onChange={(newValue) => setTempValue(newValue)}
              slotProps={{ textField: { size: 'small', fullWidth: true } }}
              disabled={saving}
            />
            <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
              <CheckOutlined />
            </IconButton>
            <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
              <CloseOutlined />
            </IconButton>
          </Stack>
        ) : (
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body1">{displayValue}</Typography>
            <IconButton size="small" onClick={() => setEditing(true)}>
              <EditOutlined />
            </IconButton>
          </Stack>
        )}
      </Box>
    </LocalizationProvider>
  );
}

// ==============================|| EDITABLE TIME FIELD ||============================== //

function EditableTimeField({ label, value, fieldKey, onSave }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value ? dayjs(`1970-01-01T${value}`) : null);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    const formattedTime = tempValue ? tempValue.format('HH:mm:ss') : null;
    const success = await onSave(fieldKey, formattedTime);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value ? dayjs(`1970-01-01T${value}`) : null);
    setEditing(false);
  };

  const displayValue = value ? dayjs(`1970-01-01T${value}`).format('h:mm A') : '-';

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>

      <Box>
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          {label}
        </Typography>
        {editing ? (
          <Stack direction="row" spacing={1} alignItems="center">
            <TimePicker
              value={tempValue}
              onChange={(newValue) => setTempValue(newValue)}
              slotProps={{ textField: { size: 'small', fullWidth: true } }}
              disabled={saving}
            />
            <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
              <CheckOutlined />
            </IconButton>
            <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
              <CloseOutlined />
            </IconButton>
          </Stack>
        ) : (
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body1">{displayValue}</Typography>
            <IconButton size="small" onClick={() => setEditing(true)}>
              <EditOutlined />
            </IconButton>
          </Stack>
        )}
      </Box>
    </LocalizationProvider>
  );
}

// ==============================|| EDITABLE CONTACTS FIELD ||============================== //

function EditableContactsField({ label, value = [], fieldKey, onSave, accountId }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value || []);
  const [saving, setSaving] = useState(false);

  const { contacts = [] } = useGetContacts({ 
    filters: { account_id: accountId },
    pageSize: 100 
    });

  const handleSave = async () => {
    setSaving(true);
    const contactIds = tempValue.map((c) => c.id || c);
    const success = await onSave(fieldKey, contactIds);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value || []);
    setEditing(false);
  };

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" gutterBottom display="block">
        {label}
      </Typography>
      {editing ? (
        <Stack direction="row" spacing={1} alignItems="flex-start">
          <Autocomplete
            multiple
            fullWidth
            size="small"
            options={contacts}
            value={tempValue}
            onChange={(_, newValue) => setTempValue(newValue)}
            getOptionLabel={(option) => option.full_name || option.email || ''}
            isOptionEqualToValue={(option, val) => option.id === (val.id || val)}
            renderInput={(params) => <TextField {...params} placeholder="Select contacts" />}
            renderTags={(tagValue, getTagProps) =>
              tagValue.map((option, index) => (
                <Chip label={option.full_name || option.email} size="small" {...getTagProps({ index })} key={option.id} />
              ))
            }
            disabled={saving}
          />
          <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
            <CheckOutlined />
          </IconButton>
          <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
            <CloseOutlined />
          </IconButton>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
          {value && value.length > 0 ? (
            value.map((contact) => (
              <Chip key={contact.id} label={contact.full_name || contact.email} size="small" variant="outlined" />
            ))
          ) : (
            <Typography variant="body1" color="text.secondary">-</Typography>
          )}
          <IconButton size="small" onClick={() => setEditing(true)}>
            <EditOutlined />
          </IconButton>
        </Stack>
      )}
    </Box>
  );
}

// ==============================|| EDITABLE CYCLE FIELD ||============================== //

function EditableCycleField({ label, value, fieldKey, onSave, accountId, onCycleChange }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value || '');
  const [saving, setSaving] = useState(false);

  // Fetch cycles for the account
  const { cycles, cyclesLoading } = useGetDecisionCyclesByAccount(accountId);

  const handleSave = async () => {
    if (tempValue === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(fieldKey, tempValue || null);
    setSaving(false);
    if (success) {
      setEditing(false);
      onCycleChange?.(tempValue);
    }
  };

  const handleCancel = () => {
    setTempValue(value || '');
    setEditing(false);
  };

  const selectedCycle = cycles.find(c => c.id === value);
  const displayValue = selectedCycle?.name || '-';

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" gutterBottom display="block">
        {label}
      </Typography>
      {editing ? (
        <Stack direction="row" spacing={1} alignItems="flex-start">
          <Select
            value={tempValue}
            onChange={(e) => setTempValue(e.target.value)}
            size="small"
            fullWidth
            autoFocus
            disabled={saving || cyclesLoading}
            displayEmpty
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {cycles.map((cycle) => (
              <MenuItem key={cycle.id} value={cycle.id}>
                {cycle.name}
                {!cycle.is_active && ' (Inactive)'}
              </MenuItem>
            ))}
          </Select>
          <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
            <CheckOutlined />
          </IconButton>
          <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
            <CloseOutlined />
          </IconButton>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="body1">
            {cycles.length === 0 ? (
              <span style={{ color: '#999' }}>No cycles available</span>
            ) : (
              displayValue
            )}
          </Typography>
          {cycles.length > 0 && (
            <IconButton size="small" onClick={() => setEditing(true)}>
              <EditOutlined />
            </IconButton>
          )}
        </Stack>
      )}
    </Box>
  );
}

// ==============================|| EDITABLE STEP FIELD ||============================== //

function EditableStepField({ label, value, fieldKey, onSave, cycleId }) {
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value || '');
  const [saving, setSaving] = useState(false);

  // Fetch steps for the cycle
  const { steps, stepsLoading } = useGetDecisionStepsByCycle(cycleId);

  // Reset temp value when cycle changes
  useEffect(() => {
    setTempValue(value || '');
  }, [cycleId, value]);

  const handleSave = async () => {
    if (tempValue === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(fieldKey, tempValue || null);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setTempValue(value || '');
    setEditing(false);
  };

  const selectedStep = steps.find(s => s.id === value);
  const displayValue = selectedStep?.name || '-';

  // If no cycle selected, show message
  if (!cycleId) {
    return (
      <Box>
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          {label}
        </Typography>
        <Typography variant="body1" color="text.disabled">
          Select a cycle first
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="caption" color="text.secondary" gutterBottom display="block">
        {label}
      </Typography>
      {editing ? (
        <Stack direction="row" spacing={1} alignItems="flex-start">
          <Select
            value={tempValue}
            onChange={(e) => setTempValue(e.target.value)}
            size="small"
            fullWidth
            autoFocus
            disabled={saving || stepsLoading}
            displayEmpty
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            {steps.map((step) => (
              <MenuItem key={step.id} value={step.id}>
                {step.name}
              </MenuItem>
            ))}
          </Select>
          <IconButton size="small" onClick={handleSave} disabled={saving} color="success">
            <CheckOutlined />
          </IconButton>
          <IconButton size="small" onClick={handleCancel} disabled={saving} color="error">
            <CloseOutlined />
          </IconButton>
        </Stack>
      ) : (
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="body1">
            {steps.length === 0 ? (
              <span style={{ color: '#999' }}>No steps in cycle</span>
            ) : (
              displayValue
            )}
          </Typography>
          {steps.length > 0 && (
            <IconButton size="small" onClick={() => setEditing(true)}>
              <EditOutlined />
            </IconButton>
          )}
        </Stack>
      )}
    </Box>
  );
}

// ==============================|| ACTIVITY OVERVIEW TAB ||============================== //

export default function ActivityOverviewTab({ activity, onSave }) {
  // Track current cycle for cascading step dropdown
  const [currentCycleId, setCurrentCycleId] = useState(activity?.decision_cycle || '');

  // Update currentCycleId when activity changes
  useEffect(() => {
    setCurrentCycleId(activity?.decision_cycle || '');
  }, [activity?.decision_cycle]);

  // Handle cycle change - also clear step if cycle changes
  const handleCycleChange = async (newCycleId) => {
    setCurrentCycleId(newCycleId);
    // If cycle changed, clear the step
    if (newCycleId !== activity?.decision_cycle) {
      await onSave('decision_step_id', null);
    }
  };

  // Type options
  const typeOptions = Object.entries(ACTIVITY_TYPE_LABELS).map(([value, label]) => ({
    value,
    label
  }));

  // Outcome options
  const outcomeOptions = Object.entries(ACTIVITY_OUTCOME_LABELS).map(([value, label]) => ({
    value,
    label
  }));

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Left Column - Details */}
        <Grid item xs={12} md={6}>
          <Stack spacing={3}>
            <Typography variant="h6">Details</Typography>

            <EditableField
              label="Activity Type"
              value={activity?.activity_type}
              fieldKey="activity_type"
              onSave={onSave}
              type="select"
              options={typeOptions}
              displayValue={ACTIVITY_TYPE_LABELS[activity?.activity_type]}
            />

            <EditableDateField
              label="Scheduled Date"
              value={activity?.scheduled_date}
              fieldKey="scheduled_date"
              onSave={onSave}
            />

            <EditableTimeField
              label="Scheduled Time"
              value={activity?.scheduled_time}
              fieldKey="scheduled_time"
              onSave={onSave}
            />

            <EditableDateField
              label="Due Date"
              value={activity?.due_date}
              fieldKey="due_date"
              onSave={onSave}
            />

            <EditableContactsField
              label="Contacts"
              value={activity?.contacts_details || []}
              fieldKey="contacts"
              onSave={onSave}
              accountId={activity?.account}
            />
            
           {/* Decision Cycle Link */}
            <Box sx={{ pt: 2 }}>
              <Typography variant="h6" sx={{ mb: 2 }}>Decision Cycle</Typography>
              
              <Stack spacing={3}>
                <EditableCycleField
                  label="Cycle"
                  value={activity?.decision_cycle}
                  fieldKey="decision_cycle_id"
                  onSave={onSave}
                  accountId={activity?.account}
                  onCycleChange={handleCycleChange}
                />

                <EditableStepField
                  label="Step"
                  value={activity?.decision_step}
                  fieldKey="decision_step_id"
                  onSave={onSave}
                  cycleId={currentCycleId}
                />
              </Stack>
            </Box>
          </Stack>
        </Grid>


        {/* Right Column - Outcome & Notes */}
        <Grid item xs={12} md={6}>
          <Stack spacing={3}>
            <Typography variant="h6">Outcome & Notes</Typography>

            <EditableField
              label="Outcome"
              value={activity?.outcome}
              fieldKey="outcome"
              onSave={onSave}
              type="select"
              options={outcomeOptions}
              displayValue={
                activity?.outcome ? (
                  <Chip
                    label={ACTIVITY_OUTCOME_LABELS[activity.outcome]}
                    color={ACTIVITY_OUTCOME_COLORS[activity.outcome] || 'default'}
                    size="small"
                  />
                ) : null
              }
            />

            <EditableField
              label="Outcome Notes"
              value={activity?.outcome_notes}
              fieldKey="outcome_notes"
              onSave={onSave}
              type="textarea"
            />

            <EditableField
              label="Description"
              value={activity?.description}
              fieldKey="description"
              onSave={onSave}
              type="textarea"
            />

            <EditableField
              label="Call to Action"
              value={activity?.call_to_action}
              fieldKey="call_to_action"
              onSave={onSave}
              type="textarea"
            />
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}

ActivityOverviewTab.propTypes = {
  activity: PropTypes.object.isRequired,
  onSave: PropTypes.func.isRequired
};
