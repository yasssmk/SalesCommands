// frontend/src/sections/accounts/decision-cycles/EditableChipList.jsx
/**
 * Editable Chip List Component
 * 
 * Inline editable list of chips (tags).
 * Click to edit mode, add/remove chips.
 * 
 * Features:
 * - Display chips in read-only mode
 * - Click to enter edit mode
 * - Add new items with Enter
 * - Remove items by clicking X
 * - Save on confirm, cancel on Escape
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useRef, useEffect, useCallback } from 'react';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// icons
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';

// ==============================|| EDITABLE CHIP LIST ||============================== //

/**
 * EditableChipList Component
 * 
 * @param {Array} values - Current array of string values
 * @param {string} fieldKey - Field key for API update
 * @param {Function} onSave - Save callback (fieldKey, newValue) => Promise<boolean>
 * @param {string} placeholder - Placeholder text for input
 * @param {string} emptyText - Text to show when list is empty
 */
export default function EditableChipList({
  values = [],
  fieldKey,
  onSave,
  placeholder = 'Add item...',
  emptyText = 'Click to add'
}) {
  const theme = useTheme();
  const inputRef = useRef(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [editValues, setEditValues] = useState([...(values || [])]);
  const [inputValue, setInputValue] = useState('');
  const [saving, setSaving] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  
  // Sync edit values when values prop changes
  useEffect(() => {
    if (!isEditing) {
      setEditValues([...(values || [])]);
    }
  }, [values, isEditing]);
  
  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);
  
  // ==============================|| HANDLERS ||============================== //
  
  const handleStartEdit = useCallback(() => {
    setEditValues([...(values || [])]);
    setInputValue('');
    setIsEditing(true);
  }, [values]);
  
  const handleCancel = useCallback(() => {
    setEditValues([...(values || [])]);
    setInputValue('');
    setIsEditing(false);
  }, [values]);
  
  const handleSave = useCallback(async () => {
    // Check if changed
    const originalSorted = [...(values || [])].sort();
    const editSorted = [...editValues].sort();
    const isUnchanged = originalSorted.length === editSorted.length && 
      originalSorted.every((v, i) => v === editSorted[i]);
    
    if (isUnchanged) {
      setIsEditing(false);
      return;
    }
    
    setSaving(true);
    
    try {
      const success = await onSave(fieldKey, editValues);
      if (success) {
        setIsEditing(false);
        setInputValue('');
      }
    } finally {
      setSaving(false);
    }
  }, [editValues, fieldKey, onSave, values]);
  
  const handleAddItem = useCallback(() => {
    const trimmed = inputValue.trim();
    if (trimmed && !editValues.includes(trimmed)) {
      setEditValues([...editValues, trimmed]);
      setInputValue('');
      inputRef.current?.focus();
    }
  }, [inputValue, editValues]);
  
  const handleRemoveItem = useCallback((indexToRemove) => {
    setEditValues(editValues.filter((_, index) => index !== indexToRemove));
  }, [editValues]);
  
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddItem();
    } else if (e.key === 'Escape') {
      handleCancel();
    } else if (e.key === 'Backspace' && inputValue === '' && editValues.length > 0) {
      // Remove last item when backspace on empty input
      handleRemoveItem(editValues.length - 1);
    }
  }, [handleAddItem, handleCancel, handleRemoveItem, inputValue, editValues.length]);
  
  const handleInputChange = useCallback((e) => {
    setInputValue(e.target.value);
  }, []);
  
  // ==============================|| RENDER - EDIT MODE ||============================== //
  
  if (isEditing) {
    return (
      <Box
        sx={{
          p: 1.5,
          border: '1px solid',
          borderColor: 'primary.main',
          borderRadius: 1,
          bgcolor: alpha(theme.palette.primary.main, 0.04)
        }}
      >
        {/* Chips */}
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ mb: editValues.length > 0 ? 1.5 : 0 }}>
          {editValues.map((item, index) => (
            <Chip
              key={`${item}-${index}`}
              label={item}
              size="small"
              onDelete={() => handleRemoveItem(index)}
              disabled={saving}
              sx={{ mb: 0.5 }}
            />
          ))}
        </Stack>
        
        {/* Input */}
        <Stack direction="row" spacing={1} alignItems="center">
          <TextField
            inputRef={inputRef}
            value={inputValue}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            size="small"
            fullWidth
            disabled={saving}
            sx={{
              '& .MuiInputBase-input': {
                py: 0.75,
                fontSize: '0.875rem'
              }
            }}
            InputProps={{
              endAdornment: inputValue.trim() && (
                <IconButton size="small" onClick={handleAddItem} disabled={saving}>
                  <PlusOutlined style={{ fontSize: 14 }} />
                </IconButton>
              )
            }}
          />
        </Stack>
        
        {/* Actions */}
        <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ mt: 1.5 }}>
          {saving ? (
            <CircularProgress size={20} />
          ) : (
            <>
              <IconButton 
                size="small" 
                onClick={handleCancel} 
                sx={{ border: '1px solid', borderColor: 'divider' }}
              >
                <CloseOutlined />
              </IconButton>
              <IconButton 
                size="small" 
                onClick={handleSave} 
                color="primary" 
                sx={{ border: '1px solid', borderColor: 'primary.main' }}
              >
                <CheckOutlined />
              </IconButton>
            </>
          )}
        </Stack>
      </Box>
    );
  }
  
  // ==============================|| RENDER - READ MODE ||============================== //
  
  const hasValues = values && values.length > 0;
  
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
        minHeight: 40,
        '&:hover': {
          bgcolor: alpha(theme.palette.primary.main, 0.08),
          borderColor: alpha(theme.palette.primary.main, 0.3)
        }
      }}
    >
      {hasValues ? (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
          {values.map((item, index) => (
            <Chip
              key={`${item}-${index}`}
              label={item}
              size="small"
              variant="outlined"
              sx={{ pointerEvents: 'none' }}
            />
          ))}
        </Stack>
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

EditableChipList.propTypes = {
  values: PropTypes.arrayOf(PropTypes.string),
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  placeholder: PropTypes.string,
  emptyText: PropTypes.string
};