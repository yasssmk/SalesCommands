// frontend/src/sections/accounts/decision-cycles/EditableTextArea.jsx
/**
 * Editable TextArea Component
 * 
 * Inline editable multiline text field.
 * Click to edit, click outside or buttons to save/cancel.
 * 
 * Features:
 * - Read-only display by default
 * - Click-to-edit mode
 * - Multiline text support
 * - Save on blur or button click
 * - Cancel on Escape
 * - Loading state during save
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

// ==============================|| EDITABLE TEXTAREA ||============================== //

/**
 * EditableTextArea Component
 * 
 * @param {string} value - Current value
 * @param {string} fieldKey - Field key for API update
 * @param {Function} onSave - Save callback (fieldKey, newValue) => Promise<boolean>
 * @param {string} placeholder - Placeholder text in edit mode
 * @param {string} emptyText - Text to show when value is empty
 * @param {number} minRows - Minimum rows for textarea
 * @param {number} maxRows - Maximum rows for textarea
 */
export default function EditableTextArea({
  value,
  fieldKey,
  onSave,
  placeholder = 'Enter text...',
  emptyText = 'Click to add',
  minRows = 2,
  maxRows = 6
}) {
  const theme = useTheme();
  const inputRef = useRef(null);
  const containerRef = useRef(null);
  
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
      // Move cursor to end
      const length = inputRef.current.value.length;
      inputRef.current.setSelectionRange(length, length);
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
    const newValue = editValue?.trim() || null;
    
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
  }, [editValue, fieldKey, onSave, value]);
  
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
    // Note: Enter creates new line in textarea, save via button or blur
  }, [handleCancel]);
  
  const handleChange = useCallback((e) => {
    setEditValue(e.target.value);
  }, []);
  
  // ==============================|| RENDER - EDIT MODE ||============================== //
  
  if (isEditing) {
    return (
      <Box ref={containerRef}>
        <TextField
          inputRef={inputRef}
          value={editValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          multiline
          minRows={minRows}
          maxRows={maxRows}
          size="small"
          fullWidth
          disabled={saving}
          sx={{
            '& .MuiInputBase-root': {
              fontSize: '0.875rem'
            }
          }}
        />
        
        <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ mt: 1 }}>
          {saving ? (
            <CircularProgress size={20} />
          ) : (
            <>
              <IconButton size="small" onClick={handleCancel} sx={{ border: '1px solid', borderColor: 'divider' }}>
                <CloseOutlined />
              </IconButton>
              <IconButton size="small" onClick={handleSave} color="primary" sx={{ border: '1px solid', borderColor: 'primary.main' }}>
                <CheckOutlined />
              </IconButton>
            </>
          )}
        </Stack>
      </Box>
    );
  }
  
  // ==============================|| RENDER - READ MODE ||============================== //
  
  const hasValue = value !== null && value !== undefined && value !== '';
  
  return (
    <Box
      onClick={handleStartEdit}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{
        position: 'relative',
        py: 1,
        px: 1.5,
        mx: -1.5,
        borderRadius: 1,
        cursor: 'pointer',
        transition: 'all 0.2s',
        bgcolor: isHovered ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
        border: '1px solid',
        borderColor: isHovered ? alpha(theme.palette.primary.main, 0.3) : 'transparent',
        minHeight: 60,
        '&:hover': {
          bgcolor: alpha(theme.palette.primary.main, 0.08),
          borderColor: alpha(theme.palette.primary.main, 0.3)
        }
      }}
    >
      {hasValue ? (
        <Typography
          variant="body2"
          color="text.primary"
          sx={{
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word'
          }}
        >
          {value}
        </Typography>
      ) : (
        <Typography
          variant="body2"
          color="text.disabled"
          sx={{ fontStyle: 'italic' }}
        >
          {emptyText}
        </Typography>
      )}
      
      {isHovered && (
        <Box
          sx={{
            position: 'absolute',
            top: 8,
            right: 8
          }}
        >
          <EditOutlined 
            style={{ 
              fontSize: 14, 
              color: theme.palette.primary.main 
            }} 
          />
        </Box>
      )}
    </Box>
  );
}

EditableTextArea.propTypes = {
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  emptyText: PropTypes.string,
  minRows: PropTypes.number,
  maxRows: PropTypes.number
};