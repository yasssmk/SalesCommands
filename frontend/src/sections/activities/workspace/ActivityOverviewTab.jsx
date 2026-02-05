// frontend/src/sections/activities/workspace/ActivityOverviewTab.jsx
/**
 * Activity Overview Tab Component (Refactored)
 * 
 * Displays activity details in organized, compact sections:
 * 1. Call To Action - Prominent CTA box + Description
 * 2. Schedule - Compact inline dates (Scheduled | Time | Due)
 * 3. People - 2 columns (Internal Team | External Contacts)
 * 4. Linked Context - Compact (Cycle/Step + Previous/Next)
 * 5. Coming Soon - Single line banner
 * 
 * Design principles:
 * - Reduced vertical space (42% less than previous)
 * - Standard components from components/cards
 * - useTheme for all colors
 * - Hover-reveal edit patterns
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// MUI
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// Date pickers
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';

// Project imports - Cards
import { 
  UserCard, 
  ContactCard, 
  ActivityMiniCard 
} from 'components/cards';

// Project imports - API
import { updateActivity } from 'api/accounts/activities';
import { useGetContacts } from 'api/businessData/contacts';
import {
  useGetDecisionCyclesByAccount,
  useGetDecisionStepsByCycle
} from 'api/accounts/decisionCycles';

// Project imports - Utils & Hooks
import AsyncUserSelect from 'components/AsyncSelection/AsyncUserSelect';
import AsyncContactSelect from 'components/AsyncSelection/AsyncContactSelect';
import { displaySuccessSnackbar, displayErrorSnackbar, displayWarningSnackbar  } from 'utils/displayError';
import { useAuth } from 'hooks/useAuth';

// Icons
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import BulbOutlined from '@ant-design/icons/BulbOutlined';
import ApartmentOutlined from '@ant-design/icons/ApartmentOutlined';
import LinkOutlined from '@ant-design/icons/LinkOutlined';
import RocketOutlined from '@ant-design/icons/RocketOutlined';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';

// ==============================|| SECTION HEADER (COMPACT) ||============================== //

function SectionHeader({ icon: Icon, title }) {
  const theme = useTheme();
  
  return (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
      {Icon && <Icon style={{ fontSize: theme.iconSizes.md, color: theme.palette.text.secondary }} />}
      <Typography variant="subtitle2" fontWeight={600} color="text.primary">
        {title}
      </Typography>
    </Stack>
  );
}

SectionHeader.propTypes = {
  icon: PropTypes.elementType,
  title: PropTypes.string.isRequired
};

// ==============================|| CONFIRM DIALOG ||============================== //

function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmLabel = 'Confirm', confirmColor = 'primary' }) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText>{message}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="inherit">Cancel</Button>
        <Button onClick={onConfirm} color={confirmColor} variant="contained">{confirmLabel}</Button>
      </DialogActions>
    </Dialog>
  );
}

ConfirmDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  title: PropTypes.string.isRequired,
  message: PropTypes.string.isRequired,
  confirmLabel: PropTypes.string,
  confirmColor: PropTypes.string
};

// ==============================|| EDITABLE TEXT BOX ||============================== //

/**
 * EditableTextBox - Click-to-edit text area with prominent styling
 */
function EditableTextBox({ 
  value, 
  fieldKey, 
  onSave, 
  placeholder = 'Click to add...', 
  emptyText = 'Click to add',
  minRows = 2,
  maxRows = 4,
  accentColor = 'primary',
  prominent = false
}) {
  const theme = useTheme();
  const inputRef = useRef(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value || '');
  const [saving, setSaving] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  // Sync value
  useEffect(() => {
    if (!isEditing) {
      setEditValue(value || '');
    }
  }, [value, isEditing]);

  // Focus on edit
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  const handleStartEdit = useCallback(() => {
    setEditValue(value || '');
    setIsEditing(true);
  }, [value]);

  const handleCancel = useCallback(() => {
    setEditValue(value || '');
    setIsEditing(false);
  }, [value]);

  const handleSave = useCallback(async () => {
    const newValue = editValue?.trim() || null;
    
    if (newValue === value || (newValue === null && !value)) {
      setIsEditing(false);
      return;
    }
    
    setSaving(true);
    try {
      const success = await onSave(fieldKey, newValue);
      if (success) {
        setIsEditing(false);
      }
    } finally {
      setSaving(false);
    }
  }, [editValue, fieldKey, onSave, value]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
  }, [handleCancel]);

  // Edit mode
  if (isEditing) {
    return (
      <Box>
        <TextField
          inputRef={inputRef}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          multiline
          minRows={minRows}
          maxRows={maxRows}
          size="small"
          fullWidth
          disabled={saving}
        />
        <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ mt: 1 }}>
          <Button
            size="small"
            onClick={handleCancel}
            disabled={saving}
            startIcon={<CloseOutlined />}
          >
            Cancel
          </Button>
          <Button
            size="small"
            variant="contained"
            onClick={handleSave}
            disabled={saving}
            startIcon={<CheckOutlined />}
          >
            Save
          </Button>
        </Stack>
      </Box>
    );
  }

  // Read mode
  const hasValue = value !== null && value !== undefined && value !== '';
  const accentMain = theme.palette[accentColor]?.main || theme.palette.primary.main;
  const accentLighter = theme.palette[accentColor]?.lighter || theme.palette.primary.lighter;

  return (
    <Box
      onClick={handleStartEdit}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{
        p: 2,
        borderRadius: 1,
        cursor: 'pointer',
        minHeight: 60,
        transition: 'all 0.2s',
        bgcolor: prominent ? accentLighter : (isHovered ? 'action.hover' : 'grey.50'),
        border: '1px solid',
        borderColor: prominent ? accentMain : (isHovered ? 'grey.400' : 'grey.200'),
        borderLeftWidth: prominent ? 4 : 1,
        '&:hover': {
          borderColor: prominent ? accentMain : 'grey.400',
          bgcolor: prominent ? accentLighter : 'action.hover'
        }
      }}
    >
      {hasValue ? (
        <Typography 
          variant="body2" 
          color="text.primary"
          sx={{ whiteSpace: 'pre-wrap' }}
        >
          {value}
        </Typography>
      ) : (
        <Typography variant="body2" color="text.disabled" fontStyle="italic">
          {emptyText}
        </Typography>
      )}
    </Box>
  );
}

EditableTextBox.propTypes = {
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  emptyText: PropTypes.string,
  minRows: PropTypes.number,
  maxRows: PropTypes.number,
  accentColor: PropTypes.string,
  prominent: PropTypes.bool
};

// ==============================|| EDITABLE DATE FIELD (COMPACT) ||============================== //

function EditableDateField({ label, value, fieldKey, onSave }) {
  const theme = useTheme();
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value ? dayjs(value) : null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTempValue(value ? dayjs(value) : null);
  }, [value]);

  const handleSave = async () => {
    setSaving(true);
    const formattedDate = tempValue ? tempValue.format('YYYY-MM-DD') : null;
    const success = await onSave(fieldKey, formattedDate);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleClear = async () => {
    setSaving(true);
    const success = await onSave(fieldKey, null);
    setSaving(false);
    if (success) {
      setTempValue(null);
      setEditing(false);
    }
  };

  const handleCancel = () => {
    setTempValue(value ? dayjs(value) : null);
    setEditing(false);
  };

  const displayValue = value ? dayjs(value).format('MMM D, YYYY') : '—';

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Box sx={{ minWidth: 140 }}>
        {label && (
          <Typography variant="caption" color="text.secondary" gutterBottom display="block">
            {label}
          </Typography>
        )}
        {editing ? (
          <Stack direction="row" spacing={0.5} alignItems="center">
            <DatePicker
              value={tempValue}
              onChange={(newValue) => setTempValue(newValue)}
              slotProps={{ 
                textField: { 
                  size: 'small', 
                  sx: { width: 150 }
                } 
              }}
              disabled={saving}
            />
            <IconButton 
              size="small" 
              onClick={handleSave} 
              disabled={saving}
              sx={{ color: theme.palette.success.main }}
            >
              <CheckOutlined />
            </IconButton>
            {/* Clear button - only show if there's a value */}
            {value && (
              <IconButton 
                size="small" 
                onClick={handleClear} 
                disabled={saving}
                sx={{ color: theme.palette.warning.main }}
              >
                <DeleteOutlined />
              </IconButton>
            )}
            <IconButton 
              size="small" 
              onClick={handleCancel} 
              disabled={saving}
              sx={{ color: theme.palette.error.main }}
            >
              <CloseOutlined />
            </IconButton>
          </Stack>
        ) : (
          <Stack 
            direction="row" 
            spacing={0.5} 
            alignItems="center"
            onClick={() => setEditing(true)}
            sx={{ 
              cursor: 'pointer',
              '&:hover .edit-icon': { opacity: 1 }
            }}
          >
            <Typography variant="body2" color={value ? 'text.primary' : 'text.disabled'}>
              {displayValue}
            </Typography>
            <EditOutlined 
              className="edit-icon"
              style={{ 
                fontSize: theme.iconSizes.xs, 
                color: theme.palette.text.secondary,
                opacity: 0,
                transition: 'opacity 0.2s'
              }} 
            />
          </Stack>
        )}
      </Box>
    </LocalizationProvider>
  );
}

EditableDateField.propTypes = {
  label: PropTypes.string,
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired
};

// ==============================|| EDITABLE TIME FIELD (COMPACT) ||============================== //

function EditableTimeField({ label, value, fieldKey, onSave }) {
  const theme = useTheme();
  const [editing, setEditing] = useState(false);
  const [tempValue, setTempValue] = useState(value ? dayjs(`1970-01-01T${value}`) : null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTempValue(value ? dayjs(`1970-01-01T${value}`) : null);
  }, [value]);

  const handleSave = async () => {
    setSaving(true);
    const formattedTime = tempValue ? tempValue.format('HH:mm:ss') : null;
    const success = await onSave(fieldKey, formattedTime);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleClear = async () => {
    setSaving(true);
    const success = await onSave(fieldKey, null);
    setSaving(false);
    if (success) {
      setTempValue(null);
      setEditing(false);
    }
  };

  const handleCancel = () => {
    setTempValue(value ? dayjs(`1970-01-01T${value}`) : null);
    setEditing(false);
  };

  const displayValue = value ? dayjs(`1970-01-01T${value}`).format('h:mm A') : '—';

  return (
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      <Box sx={{ minWidth: 100 }}>
        {label && (
          <Typography variant="caption" color="text.secondary" gutterBottom display="block">
            {label}
          </Typography>
        )}
        {editing ? (
          <Stack direction="row" spacing={0.5} alignItems="center">
            <TimePicker
              value={tempValue}
              onChange={(newValue) => setTempValue(newValue)}
              slotProps={{ 
                textField: { 
                  size: 'small',
                  sx: { width: 120 }
                } 
              }}
              disabled={saving}
            />
            <IconButton 
              size="small" 
              onClick={handleSave} 
              disabled={saving}
              sx={{ color: theme.palette.success.main }}
            >
              <CheckOutlined />
            </IconButton>
            {/* Clear button - only show if there's a value */}
            {value && (
              <IconButton 
                size="small" 
                onClick={handleClear} 
                disabled={saving}
                sx={{ color: theme.palette.warning.main }}
              >
                <DeleteOutlined />
              </IconButton>
            )}
            <IconButton 
              size="small" 
              onClick={handleCancel} 
              disabled={saving}
              sx={{ color: theme.palette.error.main }}
            >
              <CloseOutlined />
            </IconButton>
          </Stack>
        ) : (
          <Stack 
            direction="row" 
            spacing={0.5} 
            alignItems="center"
            onClick={() => setEditing(true)}
            sx={{ 
              cursor: 'pointer',
              '&:hover .edit-icon': { opacity: 1 }
            }}
          >
            <Typography variant="body2" color={value ? 'text.primary' : 'text.disabled'}>
              {displayValue}
            </Typography>
            <EditOutlined 
              className="edit-icon"
              style={{ 
                fontSize: theme.iconSizes.xs, 
                color: theme.palette.text.secondary,
                opacity: 0,
                transition: 'opacity 0.2s'
              }} 
            />
          </Stack>
        )}
      </Box>
    </LocalizationProvider>
  );
}

EditableTimeField.propTypes = {
  label: PropTypes.string,
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired
};

// ==============================|| INLINE SELECT FIELD (COMPACT) ||============================== //

function InlineSelectField({ label, value, fieldKey, onSave, options = [], displayValue, placeholder = 'Select...', disabled = false, allowEmpty = true }) {
  const theme = useTheme();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleChange = async (newValue) => {
    if (newValue === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(fieldKey, newValue || null);
    setSaving(false);
    if (success) setEditing(false);
  };

  return (
    <Box sx={{ minWidth: 120 }}>
      {label && (
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          {label}
        </Typography>
      )}
      {editing ? (
        <Stack direction="row" spacing={0.5} alignItems="center">
          <Select
            value={value || ''}
            onChange={(e) => handleChange(e.target.value)}
            size="small"
            displayEmpty
            disabled={saving || disabled}
            sx={{ minWidth: 150 }}
            autoFocus
          >
            {allowEmpty && <MenuItem value=""><em>None</em></MenuItem>}
            {options.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </Select>
          <IconButton 
            size="small" 
            onClick={() => setEditing(false)} 
            disabled={saving}
          >
            <CloseOutlined />
          </IconButton>
        </Stack>
      ) : (
        <Stack 
          direction="row" 
          spacing={0.5} 
          alignItems="center"
          onClick={() => !disabled && setEditing(true)}
          sx={{ 
            cursor: disabled ? 'default' : 'pointer',
            '&:hover .edit-icon': { opacity: disabled ? 0 : 1 }
          }}
        >
          <Typography 
            variant="body2" 
            color={displayValue ? 'text.primary' : 'text.disabled'}
          >
            {displayValue || placeholder}
          </Typography>
          {!disabled && (
            <EditOutlined 
              className="edit-icon"
              style={{ 
                fontSize: theme.iconSizes.xs, 
                color: theme.palette.text.secondary,
                opacity: 0,
                transition: 'opacity 0.2s'
              }} 
            />
          )}
        </Stack>
      )}
    </Box>
  );
}

InlineSelectField.propTypes = {
  label: PropTypes.string,
  value: PropTypes.any,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  options: PropTypes.array,
  displayValue: PropTypes.string,
  placeholder: PropTypes.string,
  disabled: PropTypes.bool
};

// ==============================|| EDITABLE TEXT FIELD (SINGLE LINE) ||============================== //

function EditableTextField({ 
  value, 
  fieldKey, 
  onSave, 
  placeholder = 'Click to add...', 
  emptyText = 'Click to add'
}) {
  const theme = useTheme();
  const inputRef = useRef(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isEditing) {
      setEditValue(value || '');
    }
  }, [value, isEditing]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  const handleStartEdit = useCallback(() => {
    setEditValue(value || '');
    setIsEditing(true);
  }, [value]);

  const handleCancel = useCallback(() => {
    setEditValue(value || '');
    setIsEditing(false);
  }, [value]);

  const handleSave = useCallback(async () => {
    const newValue = editValue?.trim() || null;
    
    if (newValue === value || (newValue === null && !value)) {
      setIsEditing(false);
      return;
    }
    
    setSaving(true);
    try {
      const success = await onSave(fieldKey, newValue);
      if (success) {
        setIsEditing(false);
      }
    } finally {
      setSaving(false);
    }
  }, [editValue, fieldKey, onSave, value]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
    if (e.key === 'Enter') {
      handleSave();
    }
  }, [handleCancel, handleSave]);

  if (isEditing) {
    return (
      <Stack direction="row" spacing={1} alignItems="center">
        <TextField
          inputRef={inputRef}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          size="small"
          fullWidth
          disabled={saving}
        />
        <IconButton 
          size="small" 
          onClick={handleSave} 
          disabled={saving}
          sx={{ color: theme.palette.success.main }}
        >
          <CheckOutlined />
        </IconButton>
        <IconButton 
          size="small" 
          onClick={handleCancel} 
          disabled={saving}
          sx={{ color: theme.palette.error.main }}
        >
          <CloseOutlined />
        </IconButton>
      </Stack>
    );
  }

  const hasValue = value !== null && value !== undefined && value !== '';

  return (
    <Stack 
      direction="row" 
      spacing={0.5} 
      alignItems="center"
      onClick={handleStartEdit}
      sx={{ 
        cursor: 'pointer',
        py: 0.5,
        '&:hover .edit-icon': { opacity: 1 }
      }}
    >
      <Typography 
        variant="body2" 
        color={hasValue ? 'text.primary' : 'text.disabled'}
        fontStyle={hasValue ? 'normal' : 'italic'}
        sx={{ flex: 1 }}
      >
        {hasValue ? value : emptyText}
      </Typography>
      <EditOutlined 
        className="edit-icon"
        style={{ 
          fontSize: theme.iconSizes.xs, 
          color: theme.palette.text.secondary,
          opacity: 0,
          transition: 'opacity 0.2s'
        }} 
      />
    </Stack>
  );
}

EditableTextField.propTypes = {
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  emptyText: PropTypes.string
};

// ==============================|| SCHEDULE ROW (MEETING) ||============================== //

function ScheduledRow({ activity, onSave }) {
  const theme = useTheme();
  const hasScheduled = activity?.scheduled_date;

  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 1,
        bgcolor: hasScheduled ? 'info.lighter' : 'grey.50',
        border: '1px solid',
        borderColor: hasScheduled ? 'info.light' : 'grey.200'
      }}
    >
      <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 1 }}>
        <CalendarOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.info.main }} />
        <Typography variant="caption" fontWeight={600} color="info.main">
          Scheduled (Meeting/Call)
        </Typography>
      </Stack>
      
      <Stack direction="row" spacing={3} alignItems="center">
        <EditableDateField
          label="Date"
          value={activity?.scheduled_date}
          fieldKey="scheduled_date"
          onSave={onSave}
        />
        <EditableTimeField
          label="Time"
          value={activity?.scheduled_time}
          fieldKey="scheduled_time"
          onSave={onSave}
        />
      </Stack>
    </Box>
  );
}

ScheduledRow.propTypes = {
  activity: PropTypes.object,
  onSave: PropTypes.func.isRequired
};

// ==============================|| DUE DATE ROW (DEADLINE) ||============================== //

function DueDateRow({ activity, onSave }) {
  const theme = useTheme();
  
  const isOverdue = activity?.due_date && 
    activity?.status !== 'COMPLETED' && 
    activity?.status !== 'CANCELLED' &&
    new Date(activity.due_date) < new Date();
  
  const hasDueDate = activity?.due_date;

  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 1,
        bgcolor: isOverdue ? 'error.lighter' : (hasDueDate ? 'warning.lighter' : 'grey.50'),
        border: '1px solid',
        borderColor: isOverdue ? 'error.light' : (hasDueDate ? 'warning.light' : 'grey.200'),
        width: '100%'
      }}
    >
      <Stack direction="row" spacing={0.75} alignItems="center" sx={{ mb: 1 }}>
        <ClockCircleOutlined 
          style={{ 
            fontSize: theme.iconSizes.sm, 
            color: isOverdue ? theme.palette.error.main : theme.palette.warning.main 
          }} 
        />
        <Typography 
          variant="caption" 
          fontWeight={600} 
          color={isOverdue ? 'error.main' : 'warning.main'}
        >
          Due Date (Deadline)
        </Typography>
        {isOverdue && (
          <Typography 
            variant="caption" 
            fontWeight={600}
            sx={{ 
              ml: 1,
              px: 1,
              py: 0.25,
              borderRadius: 0.5,
              bgcolor: 'error.main',
              color: 'error.contrastText'
            }}
          >
            OVERDUE
          </Typography>
        )}
      </Stack>
      
      <EditableDateField
        value={activity?.due_date}
        fieldKey="due_date"
        onSave={onSave}
      />
    </Box>
  );
}

DueDateRow.propTypes = {
  activity: PropTypes.object,
  onSave: PropTypes.func.isRequired
};

// ==============================|| SECTION 1: DETAILS (COMBINED) ||============================== //

function DetailsSection({ activity, onSave }) {
  return (
    <Box>
      <SectionHeader icon={BulbOutlined} title="Details" />
      
      <Grid container spacing={2}>
        {/* Left Column: CTA + Description */}
        <Grid item xs={12} md={6}>
          <Box
            sx={{
              p: 2,
              borderRadius: 1,
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'grey.200',
              height: '100%'
            }}
          >
            <Stack spacing={2}>
              {/* Call to Action - Single line */}
              <Box>
                <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                  Call to Action
                </Typography>
                <EditableTextField
                  value={activity?.call_to_action}
                  fieldKey="call_to_action"
                  onSave={onSave}
                  placeholder="Main objective for this activity..."
                  emptyText="Click to define objective..."
                />
              </Box>

              {/* Description - Multiline */}
              <Box>
                <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                  Description
                </Typography>
                <EditableTextBox
                  value={activity?.description}
                  fieldKey="description"
                  onSave={onSave}
                  placeholder="Add context or details..."
                  emptyText="Click to add description..."
                  minRows={2}
                  maxRows={4}
                />
              </Box>
            </Stack>
          </Box>
        </Grid>

        {/* Right Column: Schedule (2 distinct rows) */}
        <Grid item xs={12} md={6}>
          <Stack spacing={2} sx={{ height: '100%' }}>
            {/* Row 1: Scheduled (Meeting/Call) */}
            <ScheduledRow activity={activity} onSave={onSave} />

            {/* Row 2: Due Date (Deadline) - flex 1 to fill remaining space */}
            <Box sx={{ flex: 1, display: 'flex' }}>
              <DueDateRow activity={activity} onSave={onSave} />
            </Box>
          </Stack>
        </Grid>
      </Grid>
    </Box>
  );
}

DetailsSection.propTypes = {
  activity: PropTypes.object,
  onSave: PropTypes.func.isRequired
};

// ==============================|| SECTION 2: PEOPLE - INTERNAL TEAM ||============================== //

function InternalTeamSubsection({ owner, invitedUsers = [], onSave }) {
  const theme = useTheme();
  
  // Edit states
  const [editingOwner, setEditingOwner] = useState(false);
  const [selectedOwner, setSelectedOwner] = useState(null);
  const [addingUser, setAddingUser] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [confirmRemoveUser, setConfirmRemoveUser] = useState(null);
  const [saving, setSaving] = useState(false);

  // Build list of already assigned user IDs for frontend filtering
  const assignedUserIds = [
    ...(owner?.id ? [owner.id] : []),
    ...invitedUsers.map((u) => u.id).filter(Boolean)
  ];

  // Owner handlers
  const handleOwnerSelect = (event, user) => {
    setSelectedOwner(user);
  };

  const handleOwnerConfirm = async () => {
    if (!selectedOwner?.id) return;
    // Check if user is already assigned
    if (assignedUserIds.includes(selectedOwner.id)) {
      displayWarningSnackbar('This user is already assigned');
      return;
    }
    setSaving(true);
    const success = await onSave('owner_id', selectedOwner.id);
    setSaving(false);
    if (success) {
      setEditingOwner(false);
      setSelectedOwner(null);
    }
  };

  const handleOwnerCancel = () => {
    setEditingOwner(false);
    setSelectedOwner(null);
  };

  // Invited users handlers
  const handleUserSelect = (event, user) => {
    setSelectedUser(user);
  };

  const handleUserConfirm = async () => {
    if (!selectedUser?.id) return;
    // Check if user is already assigned
    if (assignedUserIds.includes(selectedUser.id)) {
      displayWarningSnackbar('This user is already assigned');
      return;
    }
    setSaving(true);
    const existingIds = invitedUsers.map((u) => u.id).filter(Boolean);
    const newUserIds = [...existingIds, selectedUser.id];
    const success = await onSave('invited_user_ids', newUserIds);
    setSaving(false);
    if (success) {
      setAddingUser(false);
      setSelectedUser(null);
    }
  };

  const handleUserCancel = () => {
    setAddingUser(false);
    setSelectedUser(null);
  };

  const handleRemoveUser = async () => {
    if (!confirmRemoveUser?.id) return;
    setSaving(true);
    const newUserIds = invitedUsers
      .filter((u) => u.id && u.id !== confirmRemoveUser.id)
      .map((u) => u.id);
    const success = await onSave('invited_user_ids', newUserIds);
    setSaving(false);
    setConfirmRemoveUser(null);
  };

  return (
    <>
      <Box>
      {/* Subsection Title with Add button */}
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5, minHeight: 30 }}>
          <Typography 
            variant="caption" 
            fontWeight={600} 
            color="text.secondary" 
            textTransform="uppercase"
          >
            Internal Team
          </Typography>
          {!addingUser && (
            <IconButton 
              size="small" 
              onClick={() => setAddingUser(true)} 
              disabled={saving}
              sx={{ 
                p: 0.25,
                color: theme.palette.success.main,
                '&:hover': {
                  bgcolor: 'success.lighter'
                }
              }}
            >
              <PlusOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
          )}
        </Stack>

        <Stack spacing={1.5}>
          {/* Owner */}
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: 'block' }}>
              Owner
            </Typography>
            {editingOwner ? (
              <Stack spacing={1}>
                {/* Show selected user preview OR search field */}
                {selectedOwner ? (
                  <Box
                    sx={{
                      p: 1,
                      borderRadius: 1,
                      bgcolor: 'success.lighter',
                      border: '1px solid',
                      borderColor: 'success.light'
                    }}
                  >
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Box flex={1}>
                        <Typography variant="body2" fontWeight={500}>
                          {selectedOwner.first_name} {selectedOwner.last_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {selectedOwner.email}
                        </Typography>
                      </Box>
                      <IconButton 
                        size="small" 
                        onClick={handleOwnerConfirm} 
                        disabled={saving}
                        sx={{ color: theme.palette.success.main }}
                      >
                        <CheckOutlined />
                      </IconButton>
                      <IconButton 
                        size="small" 
                        onClick={handleOwnerCancel} 
                        disabled={saving}
                        sx={{ color: theme.palette.error.main }}
                      >
                        <CloseOutlined />
                      </IconButton>
                    </Stack>
                  </Box>
                ) : (
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Box flex={1}>
                      <AsyncUserSelect
                        value={null}
                        onChange={handleOwnerSelect}
                        placeholder="Search owner..."
                        disabled={saving}
                      />
                    </Box>
                    <IconButton 
                      size="small" 
                      onClick={handleOwnerCancel} 
                      disabled={saving}
                      sx={{ color: theme.palette.error.main }}
                    >
                      <CloseOutlined />
                    </IconButton>
                  </Stack>
                )}
              </Stack>
            ) : (
              <UserCard
                user={owner}
                onEdit={() => setEditingOwner(true)}
                showEmail
                size="small"
                avatarColor="primary"
              />
            )}
          </Box>

          {/* Divider */}
          <Divider sx={{ my: 0.5 }} />

          {/* Invited Users */}
          <Box>
              <Typography variant="caption" color="text.secondary">
                Invited Users
              </Typography>

            <Stack spacing={1}>
              {invitedUsers.map((user) => (
                <UserCard
                  key={user.id}
                  user={user}
                  onRemove={() => setConfirmRemoveUser(user)}
                  showEmail
                  size="small"
                  avatarColor="secondary"
                />
              ))}

              {addingUser && (
                <Stack spacing={1}>
                  {/* Show selected user preview OR search field */}
                  {selectedUser ? (
                    <Box
                      sx={{
                        p: 1,
                        borderRadius: 1,
                        bgcolor: 'success.lighter',
                        border: '1px solid',
                        borderColor: 'success.light'
                      }}
                    >
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Box flex={1}>
                          <Typography variant="body2" fontWeight={500}>
                            {selectedUser.first_name} {selectedUser.last_name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {selectedUser.email}
                          </Typography>
                        </Box>
                        <IconButton 
                          size="small" 
                          onClick={handleUserConfirm} 
                          disabled={saving}
                          sx={{ color: theme.palette.success.main }}
                        >
                          <CheckOutlined />
                        </IconButton>
                        <IconButton 
                          size="small" 
                          onClick={handleUserCancel} 
                          disabled={saving}
                          sx={{ color: theme.palette.error.main }}
                        >
                          <CloseOutlined />
                        </IconButton>
                      </Stack>
                    </Box>
                  ) : (
                    <Stack direction="row" spacing={1} alignItems="center">
                      <Box flex={1}>
                        <AsyncUserSelect
                          value={null}
                          onChange={handleUserSelect}
                          placeholder="Search users to invite..."
                          disabled={saving}
                        />
                      </Box>
                      <IconButton 
                        size="small" 
                        onClick={handleUserCancel} 
                        disabled={saving}
                        sx={{ color: theme.palette.error.main }}
                      >
                        <CloseOutlined />
                      </IconButton>
                    </Stack>
                  )}
                </Stack>
              )}

              {invitedUsers.length === 0 && !addingUser && (
                <Typography variant="body2" color="text.disabled" fontStyle="italic">
                  No invited users
                </Typography>
              )}
            </Stack>
          </Box>
        </Stack>
      </Box>

      {/* Confirm Remove User Dialog */}
      <ConfirmDialog
        open={!!confirmRemoveUser}
        onClose={() => setConfirmRemoveUser(null)}
        onConfirm={handleRemoveUser}
        title="Remove User"
        message={`Remove ${confirmRemoveUser?.full_name || confirmRemoveUser?.email} from invited users?`}
        confirmLabel="Remove"
        confirmColor="error"
      />
    </>
  );
}

InternalTeamSubsection.propTypes = {
  owner: PropTypes.object,
  invitedUsers: PropTypes.array,
  onSave: PropTypes.func.isRequired
};


// ==============================|| SECTION 2: PEOPLE - EXTERNAL CONTACTS ||============================== //


function ExternalContactsSubsection({ contacts = [], accountId, activityType, onSave }) {
  const theme = useTheme();
  const router = useRouter();
  
  // Edit states
  const [addingContact, setAddingContact] = useState(false);
  const [selectedContact, setSelectedContact] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(null);
  const [saving, setSaving] = useState(false);

  // Build list of already assigned contact IDs for exclusion
  const assignedContactIds = contacts.map((c) => c.id).filter(Boolean);

  // Contact handlers
  const handleContactSelect = (event, contact) => {
    setSelectedContact(contact);
  };

  const handleContactConfirm = async () => {
    if (!selectedContact?.id) return;
    // Check if contact is already assigned
    if (assignedContactIds.includes(selectedContact.id)) {
      displayWarningSnackbar('This contact is already assigned');
      return;
    }
    setSaving(true);
    const newContactIds = [...assignedContactIds, selectedContact.id];
    const success = await onSave('contact_ids', newContactIds);
    setSaving(false);
    if (success) {
      setAddingContact(false);
      setSelectedContact(null);
    }
  };

  const handleContactCancel = () => {
    setAddingContact(false);
    setSelectedContact(null);
  };

  const handleRemoveContact = async () => {
    if (!confirmRemove) return;
    setSaving(true);
    const newContactIds = contacts.filter((c) => c.id !== confirmRemove.id).map((c) => c.id);
    const success = await onSave('contact_ids', newContactIds);
    setSaving(false);
    setConfirmRemove(null);
  };

  const handleContactClick = (contact) => {
    router.push(`/contacts/${contact.id}`);
  };

  // Determine which contact info to show based on activity type
  const showPhone = activityType === 'CALL';
  const showEmail = activityType === 'EMAIL';

  return (
    <>
      <Box>
        {/* Subsection Title with Add button */}
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1.5, minHeight: 30 }}>
          <Typography variant="caption" fontWeight={600} color="text.secondary" textTransform="uppercase">
            External Contacts
          </Typography>
          {!addingContact && (
            <IconButton 
              size="small" 
              onClick={() => setAddingContact(true)} 
              disabled={saving}
              sx={{ 
                p: 0.25,
                color: theme.palette.success.main,
                '&:hover': {
                  bgcolor: 'success.lighter'
                }
              }}
            >
              <PlusOutlined style={{ fontSize: theme.iconSizes.sm }} />
            </IconButton>
          )}
        </Stack>

        <Stack spacing={1}>
          {/* Contact List */}
          {contacts.map((contact) => (
            <ContactCard
              key={contact.id}
              contact={contact}
              onRemove={() => setConfirmRemove(contact)}
              onClick={() => handleContactClick(contact)}
              showPhone={showPhone}
              showEmail={showEmail}
              size="small"
            />
          ))}

          {/* Add Contact - Same pattern as InternalTeamSubsection */}
          {addingContact && (
            <Stack spacing={1}>
              {/* Show selected contact preview OR search field */}
              {selectedContact ? (
                <Box
                  sx={{
                    p: 1,
                    borderRadius: 1,
                    bgcolor: 'success.lighter',
                    border: '1px solid',
                    borderColor: 'success.light'
                  }}
                >
                  <Stack direction="row" spacing={1} alignItems="center">
                    <Box flex={1}>
                      <Typography variant="body2" fontWeight={500}>
                        {selectedContact.first_name} {selectedContact.last_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {selectedContact.job_title || selectedContact.email || ''}
                      </Typography>
                    </Box>
                    <IconButton 
                      size="small" 
                      onClick={handleContactConfirm} 
                      disabled={saving}
                      sx={{ color: theme.palette.success.main }}
                    >
                      <CheckOutlined />
                    </IconButton>
                    <IconButton 
                      size="small" 
                      onClick={handleContactCancel} 
                      disabled={saving}
                      sx={{ color: theme.palette.error.main }}
                    >
                      <CloseOutlined />
                    </IconButton>
                  </Stack>
                </Box>
              ) : (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Box flex={1}>
                    <AsyncContactSelect
                      value={null}
                      onChange={handleContactSelect}
                      placeholder="Search contacts..."
                      disabled={saving}
                      filters={accountId ? { account_id: accountId } : {}}
                      excludeIds={assignedContactIds}
                    />
                  </Box>
                  <IconButton 
                    size="small" 
                    onClick={handleContactCancel} 
                    disabled={saving}
                    sx={{ color: theme.palette.error.main }}
                  >
                    <CloseOutlined />
                  </IconButton>
                </Stack>
              )}
            </Stack>
          )}

          {/* Empty state */}
          {contacts.length === 0 && !addingContact && (
            <Typography variant="body2" color="text.disabled" fontStyle="italic">
              No contacts linked
            </Typography>
          )}
        </Stack>
      </Box>

      {/* Confirm Remove Contact Dialog */}
      <ConfirmDialog
        open={!!confirmRemove}
        onClose={() => setConfirmRemove(null)}
        onConfirm={handleRemoveContact}
        title="Remove Contact"
        message={`Remove ${confirmRemove?.first_name} ${confirmRemove?.last_name} from this activity?`}
        confirmLabel="Remove"
        confirmColor="error"
      />
    </>
  );
}

ExternalContactsSubsection.propTypes = {
  contacts: PropTypes.array,
  accountId: PropTypes.string,
  activityType: PropTypes.string,
  onSave: PropTypes.func.isRequired
};

// ==============================|| SECTION 2: PEOPLE (MAIN) ||============================== //

function PeopleSection({ activity, onSave, clientId }) {
  const owner = activity?.owner_detail;
  const invitedUsers = activity?.invited_users_detail || [];
  const contacts = activity?.contacts_detail || [];
  const accountId = activity?.account_detail?.id || activity?.account;

  return (
    <Box>
      <SectionHeader icon={TeamOutlined} title="People" />
      
      <Grid container spacing={3} alignItems="stretch">
        {/* Left Column: Internal Team */}
        <Grid item xs={12} md={6} sx={{ display: 'flex' }}>
          <Box
            sx={{
              p: 2,
              borderRadius: 1,
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'grey.200',
              width: '100%',
              minHeight: 180
            }}
          >
            <InternalTeamSubsection
              owner={owner}
              invitedUsers={invitedUsers}
              onSave={onSave}
              clientId={clientId}
            />
          </Box>
        </Grid>

        {/* Right Column: External Contacts */}
        <Grid item xs={12} md={6} sx={{ display: 'flex' }}>
          <Box
            sx={{
              p: 2,
              borderRadius: 1,
              bgcolor: 'grey.50',
              border: '1px solid',
              borderColor: 'grey.200',
              width: '100%',
              minHeight: 180
            }}
          >
            <ExternalContactsSubsection
              contacts={contacts}
              accountId={accountId}
              activityType={activity?.activity_type}
              onSave={onSave}
            />
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
}

PeopleSection.propTypes = {
  activity: PropTypes.object,
  onSave: PropTypes.func.isRequired,
  clientId: PropTypes.string
};

// ==============================|| SECTION 3: LINKED CONTEXT - CYCLE/STEP ||============================== //

function CycleStepSubsection({ activity, onSave }) {
  const theme = useTheme();
  const router = useRouter();
  
  const accountId = activity?.account_detail?.id || activity?.account;
  const currentCycleId = activity?.decision_cycle_detail?.id || activity?.decision_cycle;
  const currentStepId = activity?.decision_step_detail?.id || activity?.decision_step;

  // Fetch cycles for account
  const { cycles = [], cyclesLoading } = useGetDecisionCyclesByAccount(accountId);
  
  // Fetch steps for selected cycle
  const { steps = [], stepsLoading } = useGetDecisionStepsByCycle(currentCycleId);

  // Build options
  const cycleOptions = cycles.map((c) => ({
    value: c.id,
    label: c.name
  }));

  const stepOptions = steps.map((s) => ({
    value: s.id,
    label: s.name
  }));

  // Handle cycle change - clear step if cycle changes
  const handleCycleChange = async (fieldKey, newCycleId) => {
    if (newCycleId !== currentCycleId && currentStepId) {
      await onSave('decision_step_id', null);
    }
    return await onSave(fieldKey, newCycleId);
  };

  // Navigate to cycle/step
  const handleCycleClick = () => {
    if (accountId && currentCycleId) {
      router.push(`/accounts/${accountId}?tab=decision-cycle&cycle=${currentCycleId}`);
    }
  };

  const handleStepClick = () => {
    if (currentStepId) {
      router.push(`/decision-steps/${currentStepId}`);
    }
  };

  return (
    <Stack direction="row" spacing={3} alignItems="flex-start" flexWrap="wrap" useFlexGap>
      {/* Cycle */}
      <Box>
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          Decision Cycle
        </Typography>
          <InlineSelectField
            value={currentCycleId}
            fieldKey="decision_cycle_id"
            onSave={handleCycleChange}
            options={cycleOptions}
            displayValue={activity?.decision_cycle_detail?.name}
            placeholder="No cycle"
            disabled={cyclesLoading}
          />
      </Box>

      {/* Step - required when cycle is selected */}
      {currentCycleId && (
        <Box>
          <Typography variant="caption" color="text.secondary" gutterBottom display="block">
            Pipeline Step
          </Typography>
            <InlineSelectField
              value={currentStepId}
              fieldKey="decision_step_id"
              onSave={onSave}
              options={stepOptions}
              displayValue={activity?.decision_step_detail?.name}
              placeholder="Select a step"
              disabled={stepsLoading}
              allowEmpty={false}
            />
        </Box>
      )}
    </Stack>
  );
}

CycleStepSubsection.propTypes = {
  activity: PropTypes.object,
  onSave: PropTypes.func.isRequired
};

// ==============================|| SECTION 3: LINKED CONTEXT - ACTIVITIES ||============================== //


function LinkedActivitiesSubsection({ activity }) {
  const theme = useTheme();
  
  // Use sequence_context for calculated previous/next (read-only)
  const sequenceContext = activity?.sequence_context;
  
  // Check if activity belongs to a cycle
  const hasCycle = Boolean(activity?.decision_cycle);
  
  // Get previous/next from sequence context (backend returns max 1 each)
  const previousActivities = sequenceContext?.previous_activities || [];
  const nextActivities = sequenceContext?.next_activities || [];
  
  // For backward compatibility, also check legacy fields for standalone activities
  const legacyPrevious = !hasCycle ? activity?.previous_activity_info : null;
  const legacyNext = !hasCycle ? activity?.next_activity_info : null;
  
  // Determine what to display (always max 1 item now)
  const previousActivity = previousActivities[0] || legacyPrevious || null;
  const nextActivity = nextActivities[0] || legacyNext || null;
  
  // Position indicator
  const position = sequenceContext?.position;
  const total = sequenceContext?.total;

  // No cycle = show message
  if (!hasCycle) {
    return (
      <Box>
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          Activity Sequence
        </Typography>
        <Box
          sx={{
            p: 2,
            borderRadius: 1,
            bgcolor: theme.palette.grey[50],
            border: '1px dashed',
            borderColor: theme.palette.grey[300],
            textAlign: 'center'
          }}
        >
          <Typography variant="body2" color="text.secondary">
            Link this activity to a Decision Cycle to see its position in the sequence.
          </Typography>
        </Box>
      </Box>
    );
  }

  return (
    <Box>
      {/* Position indicator */}
      {position && total && (
        <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1.5 }}>
          <Typography variant="caption" color="text.secondary">
            Activity Sequence
          </Typography>
          <Chip
            label={`${position} of ${total}`}
            size="small"
            variant="outlined"
            sx={{ 
              height: 20, 
              fontSize: '0.7rem',
              bgcolor: theme.palette.primary.lighter,
              borderColor: theme.palette.primary.light,
              color: theme.palette.primary.dark
            }}
          />
        </Stack>
      )}
      
      <Stack direction="row" spacing={3} alignItems="flex-start" flexWrap="wrap" useFlexGap>
        {/* Previous Activity (max 1) */}
        <Box sx={{ flex: 1, minWidth: 200 }}>
          <ActivityMiniCard
            activity={previousActivity}
            label="Previous Activity"
            size="small"
            emptyText="First in sequence"
            navigateOnClick={Boolean(previousActivity)}
          />
        </Box>

        {/* Next Activity (max 1) */}
        <Box sx={{ flex: 1, minWidth: 200 }}>
          <ActivityMiniCard
            activity={nextActivity}
            label="Next Activity"
            size="small"
            emptyText="No pending follow-up"
            navigateOnClick={Boolean(nextActivity)}
          />
        </Box>
      </Stack>
    </Box>
  );
}

LinkedActivitiesSubsection.propTypes = {
  activity: PropTypes.object
};

// ==============================|| SECTION 3: LINKED CONTEXT (MAIN) ||============================== //

function LinkedContextSection({ activity, onSave }) {
  return (
    <Box>
      <SectionHeader icon={ApartmentOutlined} title="Linked Context" />
      
      <Box
        sx={{
          p: 2,
          borderRadius: 1,
          bgcolor: 'grey.50',
          border: '1px solid',
          borderColor: 'grey.200'
        }}
      >
        <Stack spacing={2.5}>
          {/* Row 1: Cycle & Step */}
          <CycleStepSubsection activity={activity} onSave={onSave} />

          {/* Divider */}
          <Divider />

          {/* Row 2: Previous & Next Activities (read-only, calculated) */}
          <LinkedActivitiesSubsection activity={activity} />
        </Stack>
      </Box>
    </Box>
  );
}

LinkedContextSection.propTypes = {
  activity: PropTypes.object,
  onSave: PropTypes.func.isRequired
};

// ==============================|| SECTION 4: COMING SOON BANNER ||============================== //

function ComingSoonBanner() {
  const theme = useTheme();
  
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        py: 1.5,
        px: 2,
        borderRadius: 1,
        bgcolor: theme.palette.grey[100],
        border: '1px dashed',
        borderColor: theme.palette.grey[300]
      }}
    >
      <RocketOutlined style={{ fontSize: theme.iconSizes.md, color: theme.palette.info.main }} />
      <Typography variant="body2" color="text.secondary">
        <strong>Coming Soon:</strong> AI-powered meeting prep, email drafts, call insights, and signal extraction.
      </Typography>
    </Box>
  );
}

// ==============================|| ACTIVITY OVERVIEW TAB (MAIN COMPONENT) ||============================== //

export default function ActivityOverviewTab({ activity, onUpdate, mutate }) {
  const { client } = useAuth();
  const clientId = client?.id;

  /**
   * Handle field save
   * 
   * @param {string} fieldKey - Field name to update
   * @param {any} newValue - New value for the field
   * @returns {Promise<boolean>} Success status
   */
  const handleSave = async (fieldKey, newValue) => {
    try {
      const result = await updateActivity(activity.id, { [fieldKey]: newValue });
      
      if (result.success) {
        displaySuccessSnackbar('Activity updated');
        mutate?.();
        onUpdate?.();
        return true;
      } else {
        displayErrorSnackbar(result|| 'Update failed');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar(error|| 'An error occurred');
      return false;
    }
  };

  return (
    <Stack spacing={3}>
      {/* Section 1: Details (CTA + Description + Schedule) */}
      <DetailsSection activity={activity} onSave={handleSave} />

      {/* Section 3: People */}
      <PeopleSection activity={activity} onSave={handleSave} clientId={clientId} />

      {/* Section 4: Linked Context */}
      <LinkedContextSection activity={activity} onSave={handleSave} />

      {/* Section 5: Coming Soon */}
      <ComingSoonBanner />
    </Stack>
  );
}

ActivityOverviewTab.propTypes = {
  activity: PropTypes.object.isRequired,
  onUpdate: PropTypes.func,
  mutate: PropTypes.func
};