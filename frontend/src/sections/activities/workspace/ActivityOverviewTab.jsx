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
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
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

// ==============================|| INLINE SELECT FIELD (COMPACT) ||============================== //

function InlineSelectField({ label, value, fieldKey, onSave, options = [], displayValue, placeholder = 'Select...', disabled = false, allowEmpty = true }) {
  const theme = useTheme();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [pendingValue, setPendingValue] = useState(value || '');

  // Track if user changed the value (show confirm/cancel only when dirty)
  const isDirty = pendingValue !== (value || '');

  const handleOpen = () => {
    setPendingValue(value || '');
    setEditing(true);
  };

  const handleConfirm = async () => {
    const newValue = pendingValue || null;
    if (newValue === value) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(fieldKey, newValue);
    setSaving(false);
    if (success) setEditing(false);
  };

  const handleCancel = () => {
    setPendingValue(value || '');
    setEditing(false);
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
            value={pendingValue}
            onChange={(e) => setPendingValue(e.target.value)}
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
          {isDirty && (
            <IconButton
              size="small"
              color="success"
              onClick={handleConfirm}
              disabled={saving}
            >
              <CheckOutlined />
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
          onClick={() => !disabled && handleOpen()}
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
  emptyText = 'Click to add',
  disabled = false
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
    if (disabled) return;
    setEditValue(value || '');
    setIsEditing(true);
  }, [value, disabled]);

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
      <Stack 
        direction="row" 
        spacing={0.5} 
        alignItems="center"
      >
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
        cursor: disabled ? 'default' : 'pointer',
        py: 0.5,
        '&:hover .edit-icon': { opacity: disabled ? 0 : 1 }
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
  emptyText: PropTypes.string,
  disabled: PropTypes.bool
};

// ==============================|| UNIFIED DATE SECTION (COMPACT) ||============================== //

/**
 * Compact date section — fits in ~20% of row width.
 * 
 * Read mode: mode label + date + time, click to edit
 * Edit mode: [toggle + pickers] [✓] [✗] — standard inline row
 * Overdue detection on both scheduled_date and due_date
 */
function UnifiedDateSection({ activity, onSaveBatch, disabled = false }) {
  const theme = useTheme();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);

  // Derive mode from current data
  const currentMode = activity?.scheduled_date ? 'scheduled' : 'due_date';
  const currentDate = currentMode === 'scheduled' ? activity?.scheduled_date : activity?.due_date;
  const currentTime = activity?.scheduled_time;

  // Edit state (local draft until Save)
  const [draftMode, setDraftMode] = useState(currentMode);
  const [draftDate, setDraftDate] = useState(currentDate ? dayjs(currentDate) : null);
  const [draftTime, setDraftTime] = useState(currentTime ? dayjs(`1970-01-01T${currentTime}`) : null);

  // Sync drafts when activity data changes (after save)
  useEffect(() => {
    if (!editing) {
      setDraftMode(currentMode);
      setDraftDate(currentDate ? dayjs(currentDate) : null);
      setDraftTime(currentTime ? dayjs(`1970-01-01T${currentTime}`) : null);
    }
  }, [currentMode, currentDate, currentTime, editing]);

  // Overdue: any date in the past + not completed/cancelled
  const isOverdue = currentDate &&
    activity?.status !== 'COMPLETED' &&
    activity?.status !== 'CANCELLED' &&
    new Date(currentDate) < new Date();

  const handleStartEdit = () => {
    if (disabled) return;
    setDraftMode(currentMode);
    setDraftDate(currentDate ? dayjs(currentDate) : null);
    setDraftTime(currentTime ? dayjs(`1970-01-01T${currentTime}`) : null);
    setEditing(true);
  };

  const handleCancel = () => {
    setDraftMode(currentMode);
    setDraftDate(currentDate ? dayjs(currentDate) : null);
    setDraftTime(currentTime ? dayjs(`1970-01-01T${currentTime}`) : null);
    setEditing(false);
  };

  // Save — single atomic PATCH with all fields
  const handleSave = async () => {
    setSaving(true);
    try {
      const formattedDate = draftDate ? draftDate.format('YYYY-MM-DD') : null;
      const formattedTime = draftTime ? draftTime.format('HH:mm:ss') : null;

      const payload = draftMode === 'scheduled'
        ? { scheduled_date: formattedDate, scheduled_time: formattedTime, due_date: null }
        : { scheduled_date: null, scheduled_time: null, due_date: formattedDate };

      const success = await onSaveBatch(payload);
      if (success) setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  // Display values
  const displayDate = currentDate ? dayjs(currentDate).format('MMM D, YYYY') : '—';
  const displayTime = currentTime ? dayjs(`1970-01-01T${currentTime}`).format('h:mm A') : null;

  // ── EDIT MODE ──
  if (editing) {
    return (
      <Stack direction="row" spacing={0.5} alignItems="flex-start">
        <Stack spacing={0.5} sx={{ flex: 1, minWidth: 0 }}>
          <ToggleButtonGroup
            value={draftMode}
            exclusive
            onChange={(_e, val) => { if (val) setDraftMode(val); }}
            size="small"
            disabled={saving}
            sx={{
              height: 24,
              '& .MuiToggleButton-root': {
                px: 1,
                py: 0,
                fontSize: theme.typography.caption.fontSize,
                fontWeight: theme.typography.fontWeightMedium,
                textTransform: 'none',
                lineHeight: '24px',
                borderColor: theme.palette.grey[300],
                color: theme.palette.text.secondary,
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  color: 'primary.contrastText',
                  borderColor: 'primary.main',
                  '&:hover': { bgcolor: 'primary.dark' }
                }
              }
            }}
          >
            <ToggleButton value="scheduled">Scheduled</ToggleButton>
            <ToggleButton value="due_date">Due Date</ToggleButton>
          </ToggleButtonGroup>

          <LocalizationProvider dateAdapter={AdapterDayjs}>
            <DatePicker
              value={draftDate}
              onChange={(val) => setDraftDate(val)}
              disabled={saving}
              slotProps={{
                textField: { size: 'small', fullWidth: true, placeholder: 'Select date' }
              }}
            />
            {draftMode === 'scheduled' && (
              <TimePicker
                value={draftTime}
                onChange={(val) => setDraftTime(val)}
                disabled={saving}
                slotProps={{
                  textField: { size: 'small', fullWidth: true, placeholder: 'Time' }
                }}
              />
            )}
          </LocalizationProvider>
        </Stack>

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

  // ── READ MODE ──
  return (
    <Box
      onClick={handleStartEdit}
      sx={{
        cursor: disabled ? 'default' : 'pointer',
        '&:hover .edit-icon': { opacity: disabled ? 0 : 1 }
      }}
    >
      {/* Label — identical to CTA: caption + gutterBottom + display:block, no wrapper padding */}
      <Typography variant="caption" color="text.secondary" gutterBottom display="block">
        {currentMode === 'scheduled' ? 'Scheduled' : 'Due Date'}
      </Typography>

      {/* Value row — py: 0.5 matches EditableTextField read mode */}
      <Stack
        direction="row"
        spacing={0.5}
        alignItems="center"
        sx={{
          py: 0.5,
          ...(isOverdue && {
            px: 1,
            borderRadius: 1,
            bgcolor: 'error.lighter',
            border: '1px solid',
            borderColor: 'error.light'
          })
        }}
      >
        <Typography
          variant="body2"
          fontWeight={theme.typography.fontWeightMedium}
          color={isOverdue ? 'error.main' : 'text.primary'}
        >
          {displayDate}
        </Typography>
        {displayTime && (
          <Typography variant="body2" color="text.secondary">
            · {displayTime}
          </Typography>
        )}
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
    </Box>
  );
}

UnifiedDateSection.propTypes = {
  activity: PropTypes.object,
  onSaveBatch: PropTypes.func.isRequired,
  disabled: PropTypes.bool
};

// ==============================|| EDITABLE DESCRIPTION (SAVE/CANCEL) ||============================== //

/**
 * Click-to-edit multiline text with Save/Cancel icons on the right.
 * Same inline row pattern as EditableTextField and UnifiedDateSection.
 * No auto-save — changes are local until user confirms.
 */
function EditableDescription({ value, fieldKey, onSave, placeholder, emptyText, minRows = 2, maxRows = 4, disabled = false }) {
  const theme = useTheme();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(value || '');
  }, [value, editing]);

  const handleStartEdit = () => {
    if (disabled) return;
    setDraft(value || '');
    setEditing(true);
  };

  const handleCancel = () => {
    setDraft(value || '');
    setEditing(false);
  };

  const handleSave = async () => {
    const newValue = draft.trim() || null;
    if (newValue === value || (newValue === null && !value)) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      const success = await onSave(fieldKey, newValue);
      if (success) setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') handleCancel();
  };

  const hasValue = value !== null && value !== undefined && value !== '';

  if (editing) {
    return (
      <Stack direction="row" spacing={0.5} alignItems="center">
        <TextField
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          multiline
          minRows={minRows}
          maxRows={maxRows}
          size="small"
          fullWidth
          disabled={saving}
          autoFocus
          sx={{ flex: 1 }}
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

  return (
    <Stack
      direction="row"
      spacing={0.5}
      alignItems="flex-start"
      onClick={handleStartEdit}
      sx={{
        cursor: disabled ? 'default' : 'pointer',
        py: 0.5,
        '&:hover .edit-icon': { opacity: disabled ? 0 : 1 }
      }}
    >
      <Typography
        variant="body2"
        color={hasValue ? 'text.primary' : 'text.disabled'}
        fontStyle={hasValue ? 'normal' : 'italic'}
        sx={{ flex: 1, whiteSpace: 'pre-wrap' }}
      >
        {hasValue ? value : emptyText}
      </Typography>
      <EditOutlined
        className="edit-icon"
        style={{
          fontSize: theme.iconSizes.xs,
          color: theme.palette.text.secondary,
          opacity: 0,
          transition: 'opacity 0.2s',
          marginTop: 2
        }}
      />
    </Stack>
  );
}

EditableDescription.propTypes = {
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  emptyText: PropTypes.string,
  minRows: PropTypes.number,
  maxRows: PropTypes.number,
  disabled: PropTypes.bool
};

// ==============================|| SECTION 1: DETAILS (COMBINED) ||============================== //

function DetailsSection({ activity, onSave, onSaveBatch, isLocked = false  }) {
  return (
    <Box>
      <SectionHeader icon={BulbOutlined} title="Details" />

      <Box
        sx={{
          p: 2,
          borderRadius: 1,
          bgcolor: 'grey.50',
          border: '1px solid',
          borderColor: 'grey.200'
        }}
      >
        <Stack spacing={1.5}>
          {/* Row 1: Call to Action (flex) + Date (compact) */}
          <Stack direction="row" spacing={2} alignItems="stretch">
            <Box sx={{ flex: 1, minWidth: 0 }}>
              <Typography variant="caption" color="text.secondary" gutterBottom display="block">
                Call to Action
              </Typography>
              <EditableTextField
                value={activity?.call_to_action}
                fieldKey="call_to_action"
                onSave={onSave}
                placeholder="Main objective for this activity..."
                emptyText="Click to define objective..."
                disabled={isLocked}
              />
            </Box>

            <Divider orientation="vertical" flexItem />

            <Box sx={{ minWidth: 160, flexShrink: 0 }}>
              <UnifiedDateSection activity={activity} onSaveBatch={onSaveBatch} disabled={isLocked} />
            </Box>
          </Stack>

          {/* Row 2: Description (full width, save/cancel) */}
          <Box>
            <Typography variant="caption" color="text.secondary" gutterBottom display="block">
              Description
            </Typography>
            <EditableDescription
              value={activity?.description}
              fieldKey="description"
              onSave={onSave}
              placeholder="Add context or details..."
              emptyText="Click to add description..."
              minRows={2}
              maxRows={4}
              disabled={isLocked}
            />
          </Box>
        </Stack>
      </Box>
    </Box>
  );
}

DetailsSection.propTypes = {
  activity: PropTypes.object,
  onSave: PropTypes.func.isRequired,
  onSaveBatch: PropTypes.func.isRequired,
  isLocked: PropTypes.bool
};

// ==============================|| SECTION 2: PEOPLE - INTERNAL TEAM ||============================== //

function InternalTeamSubsection({ owner, invitedUsers = [], onSave, isLocked = false }) {
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
          {!addingUser && !isLocked && (
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
                onEdit={isLocked ? undefined : () => setEditingOwner(true)}
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
                  onRemove={isLocked ? undefined : () => setConfirmRemoveUser(user)}
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


function ExternalContactsSubsection({ contacts = [], accountId, activityType, onSave, isLocked = false }) {
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
          {!addingContact && !isLocked && (
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
              onRemove={isLocked ? undefined : () => setConfirmRemove(contact)}
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

function PeopleSection({ activity, onSave, clientId, isLocked = false }) {
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
              isLocked={isLocked}
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
              isLocked={isLocked}
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

function CycleStepSubsection({ activity, onSave, isLocked = false }) {
  const theme = useTheme();
  const router = useRouter();
  
  const accountId = activity?.account_detail?.id || activity?.account;
  const currentCycleId = activity?.decision_cycle_detail?.id || activity?.decision_cycle;
  const currentStepId = activity?.decision_step_detail?.id || activity?.decision_step;

  // Fetch cycles for account
  const { cycles = [], cyclesLoading } = useGetDecisionCyclesByAccount(accountId);
  
  // Fetch steps for selected cycle
  const { steps = [], stepsLoading } = useGetDecisionStepsByCycle(currentCycleId);

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
      {/* Cycle (read-only — cycle is set at activity creation, only step is editable) */}
      <Box>
        <Typography variant="caption" color="text.secondary" gutterBottom display="block">
          Decision Cycle
        </Typography>
        <Typography variant="body2" >
          {activity?.decision_cycle_detail?.name || 'No cycle'}
        </Typography>
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
              disabled={stepsLoading || isLocked}
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

function LinkedContextSection({ activity, onSave, isLocked = false }) {
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
         <CycleStepSubsection activity={activity} onSave={onSave} isLocked={isLocked} />

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

export default function ActivityOverviewTab({ activity, onUpdate, mutate, isLocked = false }) {
  const { client } = useAuth();
  const clientId = client?.id;

  /**
   * Handle single field save
   * 
   * @param {string} fieldKey - Field name to update
   * @param {any} newValue - New value for the field
   * @returns {Promise<boolean>} Success status
   */
  const handleSave = async (fieldKey, newValue) => {
    if (isLocked) return false;
    try {
      const result = await updateActivity(activity.id, { [fieldKey]: newValue });
      
      if (result.success) {
        displaySuccessSnackbar('Activity updated');
        mutate?.();
        onUpdate?.();
        return true;
      } else {
        displayErrorSnackbar(result || 'Update failed');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar(error || 'An error occurred');
      return false;
    }
  };

  /**
   * Handle batch field save (atomic PATCH with multiple fields)
   * Used by UnifiedDateSection for mode switches.
   * 
   * @param {Object} payload - Multiple fields to update atomically
   * @returns {Promise<boolean>} Success status
   */
  const handleSaveBatch = async (payload) => {
    if (isLocked) return false;
    try {
      const result = await updateActivity(activity.id, payload);

      if (result.success) {
        displaySuccessSnackbar('Activity updated');
        mutate?.();
        onUpdate?.();
        return true;
      } else {
        displayErrorSnackbar(result || 'Update failed');
        return false;
      }
    } catch (error) {
      displayErrorSnackbar(error || 'An error occurred');
      return false;
    }
  };

  return (
    <Stack spacing={3}>
      {/* Section 1: Details (CTA + Description + Schedule) */}
      <DetailsSection activity={activity} onSave={handleSave} onSaveBatch={handleSaveBatch} isLocked={isLocked} />

      {/* Section 2: People */}
      <PeopleSection activity={activity} onSave={handleSave} clientId={clientId} isLocked={isLocked} />

      {/* Section 3: Linked Context */}
      <LinkedContextSection activity={activity} onSave={handleSave} isLocked={isLocked} />

      {/* Section 4: Coming Soon */}
      <ComingSoonBanner />
    </Stack>
  );
}

ActivityOverviewTab.propTypes = {
  activity: PropTypes.object.isRequired,
  onUpdate: PropTypes.func,
  mutate: PropTypes.func,
  isLocked: PropTypes.bool
};