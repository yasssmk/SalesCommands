// frontend/src/sections/accounts/decision-cycles/EditableField.jsx
/**
 * Editable Field Component
 * 
 * Inline editable text/number field.
 * Click to edit, Enter to save, Escape to cancel.
 * 
 * Features:
 * - Read-only display by default
 * - Click-to-edit mode
 * - Save on Enter or blur
 * - Cancel on Escape
 * - Loading state during save
 * - Support for text and number types
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useRef, useEffect, useCallback } from 'react';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// icons
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';

// ==============================|| EDITABLE FIELD ||============================== //

/**
 * EditableField Component
 * 
 * @param {string|number} value - Current value
 * @param {string} fieldKey - Field key for API update
 * @param {Function} onSave - Save callback (fieldKey, newValue) => Promise<boolean>
 * @param {string} typography - Typography variant for display
 * @param {string} placeholder - Placeholder text in edit mode
 * @param {string} emptyText - Text to show when value is empty
 * @param {string} type - Input type ('text' or 'number')
 * @param {string} suffix - Suffix to display after value
 * @param {boolean} required - Whether field is required
 */
export default function EditableField({
  value,
  fieldKey,
  onSave,
  typography = 'body1',
  placeholder = 'Enter value...',
  emptyText = 'Click to add',
  type = 'text',
  suffix = '',
  required = false
}) {
  const theme = useTheme();
  const inputRef = useRef(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(value ?? '');
  const [saving, setSaving] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  
  // Sync edit value when value prop changes
  useEffect(() => {
    if (!isEditing) {
      setEditValue(value ?? '');
    }
  }, [value, isEditing]);
  
  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);
  
  // ==============================|| HANDLERS ||============================== //
  
  const handleStartEdit = useCallback(() => {
    setEditValue(value ?? '');
    setIsEditing(true);
  }, [value]);
  
  const handleCancel = useCallback(() => {
    setEditValue(value ?? '');
    setIsEditing(false);
  }, [value]);
  
  const handleSave = useCallback(async () => {
    // Parse value based on type
    let newValue = editValue;
    if (type === 'number') {
      newValue = editValue === '' ? null : parseInt(editValue, 10);
      if (newValue !== null && isNaN(newValue)) {
        newValue = null;
      }
    } else {
      newValue = editValue?.trim() || null;
    }
    
    // Check required
    if (required && (newValue === null || newValue === '')) {
      return;
    }
    
    // Skip if unchanged
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
  }, [editValue, fieldKey, onSave, type, value, required]);
  
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSave();
    } else if (e.key === 'Escape') {
      handleCancel();
    }
  }, [handleSave, handleCancel]);
  
  const handleChange = useCallback((e) => {
    setEditValue(e.target.value);
  }, []);
  
  // ==============================|| RENDER - EDIT MODE ||============================== //
  
  if (isEditing) {
    return (
      <Stack direction="row" spacing={0.5} alignItems="center">
        <TextField
          inputRef={inputRef}
          value={editValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={() => {
            // Delay to allow button clicks
            setTimeout(() => {
              if (!saving) handleSave();
            }, 150);
          }}
          placeholder={placeholder}
          type={type}
          size="small"
          fullWidth
          disabled={saving}
          sx={{
            '& .MuiInputBase-input': {
              py: 0.75,
              fontSize: theme.typography[typography]?.fontSize || '1rem'
            }
          }}
          inputProps={{
            min: type === 'number' ? 1 : undefined
          }}
        />
        
        {saving ? (
          <CircularProgress size={20} />
        ) : (
          <>
            <IconButton size="small" onClick={handleSave} color="primary">
              <CheckOutlined />
            </IconButton>
            <IconButton size="small" onClick={handleCancel}>
              <CloseOutlined />
            </IconButton>
          </>
        )}
      </Stack>
    );
  }
  
  // ==============================|| RENDER - READ MODE ||============================== //
  
  const hasValue = value !== null && value !== undefined && value !== '';
  const displayValue = hasValue ? `${value}${suffix}` : emptyText;
  
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
        variant={typography}
        color={hasValue ? 'text.primary' : 'text.disabled'}
        sx={{
          fontStyle: hasValue ? 'normal' : 'italic'
        }}
      >
        {displayValue}
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

EditableField.propTypes = {
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  typography: PropTypes.string,
  placeholder: PropTypes.string,
  emptyText: PropTypes.string,
  type: PropTypes.oneOf(['text', 'number']),
  suffix: PropTypes.string,
  required: PropTypes.bool
};