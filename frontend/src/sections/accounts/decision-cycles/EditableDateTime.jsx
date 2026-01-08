// frontend/src/sections/accounts/decision-cycles/EditableDateTime.jsx
/**
 * Editable DateTime Component
 * 
 * Click-to-edit date and time picker.
 * Used for scheduled_date and scheduled_time in DecisionStepDetail.
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useEffect } from 'react';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';

// date pickers
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { TimePicker } from '@mui/x-date-pickers/TimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs from 'dayjs';

// icons
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';

// ==============================|| EDITABLE DATETIME ||============================== //

/**
 * EditableDateTime Component
 * 
 * @param {string} dateValue - Current date (YYYY-MM-DD format or null)
 * @param {string} timeValue - Current time (HH:mm:ss format or null)
 * @param {Function} onSave - Async save callback (date, time) => Promise<boolean>
 * @param {string} emptyText - Text when no date is set
 * @param {boolean} showTime - Whether to show time picker (default: true)
 */
export default function EditableDateTime({
  dateValue = null,
  timeValue = null,
  onSave,
  emptyText = 'Not scheduled',
  showTime = true
}) {
  const theme = useTheme();
  
  const [isEditing, setIsEditing] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [editDate, setEditDate] = useState(null);
  const [editTime, setEditTime] = useState(null);
  const [saving, setSaving] = useState(false);
  
  // Sync edit values with props
  useEffect(() => {
    if (!isEditing) {
      setEditDate(dateValue ? dayjs(dateValue) : null);
      setEditTime(timeValue ? dayjs(`2000-01-01T${timeValue}`) : null);
    }
  }, [dateValue, timeValue, isEditing]);
  
  // ==============================|| HANDLERS ||============================== //
  
  const handleStartEdit = useCallback(() => {
    setEditDate(dateValue ? dayjs(dateValue) : null);
    setEditTime(timeValue ? dayjs(`2000-01-01T${timeValue}`) : null);
    setIsEditing(true);
  }, [dateValue, timeValue]);
  
  const handleCancel = useCallback(() => {
    setEditDate(dateValue ? dayjs(dateValue) : null);
    setEditTime(timeValue ? dayjs(`2000-01-01T${timeValue}`) : null);
    setIsEditing(false);
  }, [dateValue, timeValue]);
  
  const handleSave = useCallback(async () => {
    const newDate = editDate ? editDate.format('YYYY-MM-DD') : null;
    const newTime = editTime ? editTime.format('HH:mm:ss') : null;
    
    // Skip if unchanged
    if (newDate === dateValue && newTime === timeValue) {
      setIsEditing(false);
      return;
    }
    
    setSaving(true);
    
    try {
      const success = await onSave(newDate, newTime);
      if (success) {
        setIsEditing(false);
      }
    } finally {
      setSaving(false);
    }
  }, [editDate, editTime, dateValue, timeValue, onSave]);
  
  const handleClear = useCallback(async () => {
    setSaving(true);
    
    try {
      const success = await onSave(null, null);
      if (success) {
        setEditDate(null);
        setEditTime(null);
        setIsEditing(false);
      }
    } finally {
      setSaving(false);
    }
  }, [onSave]);
  
  // ==============================|| RENDER - EDIT MODE ||============================== //
  
  if (isEditing) {
    return (
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Stack spacing={1.5}>
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
            {/* Date Picker */}
            <DatePicker
              value={editDate}
              onChange={(newValue) => setEditDate(newValue)}
              disabled={saving}
              slotProps={{
                textField: {
                  size: 'small',
                  placeholder: 'Select date',
                  sx: { minWidth: 150 }
                }
              }}
            />
            
            {/* Time Picker (only if date is set and showTime is true) */}
            {showTime && editDate && (
              <TimePicker
                value={editTime}
                onChange={(newValue) => setEditTime(newValue)}
                disabled={saving}
                slotProps={{
                  textField: {
                    size: 'small',
                    placeholder: 'Select time',
                    sx: { minWidth: 130 }
                  }
                }}
              />
            )}
          </Stack>
          
          {/* Actions */}
          <Stack direction="row" spacing={0.5} alignItems="center">
            {saving ? (
              <CircularProgress size={20} />
            ) : (
              <>
                <Button
                  size="small"
                  variant="contained"
                  onClick={handleSave}
                  startIcon={<CheckOutlined />}
                  sx={{ minWidth: 'auto', px: 1.5 }}
                >
                  Save
                </Button>
                <Button
                  size="small"
                  color="secondary"
                  onClick={handleCancel}
                  sx={{ minWidth: 'auto', px: 1.5 }}
                >
                  Cancel
                </Button>
                {(dateValue || timeValue) && (
                  <IconButton 
                    size="small" 
                    color="error" 
                    onClick={handleClear}
                    title="Clear date & time"
                  >
                    <DeleteOutlined />
                  </IconButton>
                )}
              </>
            )}
          </Stack>
        </Stack>
      </LocalizationProvider>
    );
  }
  
  // ==============================|| RENDER - READ MODE ||============================== //
  
  const hasDate = dateValue !== null && dateValue !== undefined;
  
  // Format display
  let displayText = emptyText;
  if (hasDate) {
    const formattedDate = dayjs(dateValue).format('dddd, MMMM D, YYYY');
    if (timeValue) {
      const formattedTime = dayjs(`2000-01-01T${timeValue}`).format('h:mm A');
      displayText = `${formattedDate} at ${formattedTime}`;
    } else {
      displayText = formattedDate;
    }
  }
  
  return (
    <Box
      onClick={handleStartEdit}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 1,
        py: 0.5,
        px: 1,
        mx: -1,
        borderRadius: 1,
        cursor: 'pointer',
        transition: 'all 0.2s',
        bgcolor: isHovered ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
        '&:hover': {
          bgcolor: alpha(theme.palette.primary.main, 0.08)
        }
      }}
    >
      <Typography
        variant="body2"
        color={hasDate ? 'text.primary' : 'text.disabled'}
        sx={{
          fontStyle: hasDate ? 'normal' : 'italic'
        }}
      >
        {displayText}
      </Typography>
      
      {isHovered && (
        <EditOutlined 
          style={{ 
            fontSize: 14, 
            color: theme.palette.primary.main 
          }} 
        />
      )}
    </Box>
  );
}

EditableDateTime.propTypes = {
  dateValue: PropTypes.string,
  timeValue: PropTypes.string,
  onSave: PropTypes.func.isRequired,
  emptyText: PropTypes.string,
  showTime: PropTypes.bool
};