// frontend/src/sections/accounts/decision-cycles/EditableMultiSelect.jsx
/**
 * Editable Multi-Select Component
 * 
 * Click-to-edit multi-select with chips display.
 * Used for departments and contacts selection in DecisionStepDetail.
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback, useEffect, useRef } from 'react';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Autocomplete from '@mui/material/Autocomplete';
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

// ==============================|| EDITABLE MULTI SELECT ||============================== //

/**
 * EditableMultiSelect Component
 * 
 * @param {Array} value - Current selected items [{id, name, ...}, ...]
 * @param {Array} options - Available options [{id, name, ...}, ...]
 * @param {string} fieldKey - Field identifier for save callback
 * @param {Function} onSave - Async save callback (fieldKey, newIds[]) => Promise<boolean>
 * @param {Function} getOptionLabel - Function to get display label from option
 * @param {Function} isOptionEqualToValue - Function to compare options
 * @param {string} placeholder - Placeholder text when editing
 * @param {string} emptyText - Text when no items selected
 * @param {boolean} loading - Loading state for options
 * @param {string} chipColor - Color for chips (default, primary, etc.)
 */
export default function EditableMultiSelect({
  value = [],
  options = [],
  fieldKey,
  onSave,
  getOptionLabel = (opt) => opt?.name || '',
  isOptionEqualToValue = (opt, val) => opt?.id === val?.id,
  placeholder = 'Select...',
  emptyText = 'None selected',
  loading = false,
  chipColor = 'default'
}) {
  const theme = useTheme();
  const inputRef = useRef(null);
  
  const [isEditing, setIsEditing] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [editValue, setEditValue] = useState([]);
  const [saving, setSaving] = useState(false);
  
  // Sync edit value with prop value
  useEffect(() => {
    if (!isEditing) {
      setEditValue(value || []);
    }
  }, [value, isEditing]);
  
  // ==============================|| HANDLERS ||============================== //
  
  const handleStartEdit = useCallback(() => {
    setEditValue(value || []);
    setIsEditing(true);
  }, [value]);
  
  const handleCancel = useCallback(() => {
    setEditValue(value || []);
    setIsEditing(false);
  }, [value]);
  
  const handleSave = useCallback(async () => {
    // Extract IDs from selected items
    const newIds = editValue.map(item => item.id);
    const oldIds = (value || []).map(item => item.id);
    
    // Skip if unchanged
    const isEqual = newIds.length === oldIds.length && 
      newIds.every(id => oldIds.includes(id));
    
    if (isEqual) {
      setIsEditing(false);
      return;
    }
    
    setSaving(true);
    
    try {
      const success = await onSave(fieldKey, newIds);
      if (success) {
        setIsEditing(false);
      }
    } finally {
      setSaving(false);
    }
  }, [editValue, fieldKey, onSave, value]);
  
  const handleChange = useCallback((event, newValue) => {
    setEditValue(newValue);
  }, []);
  
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape') {
      handleCancel();
    }
  }, [handleCancel]);
  
  // ==============================|| RENDER - EDIT MODE ||============================== //
  
  if (isEditing) {
    return (
      <Stack direction="row" spacing={1} alignItems="flex-start">
        <Autocomplete
          multiple
          value={editValue}
          onChange={handleChange}
          options={options}
          getOptionLabel={getOptionLabel}
          isOptionEqualToValue={isOptionEqualToValue}
          loading={loading}
          disabled={saving}
          disableCloseOnSelect
          size="small"
          sx={{ minWidth: 250, flex: 1 }}
          renderInput={(params) => (
            <TextField
              {...params}
              inputRef={inputRef}
              placeholder={editValue.length === 0 ? placeholder : ''}
              onKeyDown={handleKeyDown}
              InputProps={{
                ...params.InputProps,
                endAdornment: (
                  <>
                    {loading ? <CircularProgress color="inherit" size={16} /> : null}
                    {params.InputProps.endAdornment}
                  </>
                )
              }}
            />
          )}
          renderTags={(tagValue, getTagProps) =>
            tagValue.map((option, index) => (
              <Chip
                {...getTagProps({ index })}
                key={option.id}
                label={getOptionLabel(option)}
                size="small"
                color={chipColor}
              />
            ))
          }
        />
        
        <Stack direction="row" spacing={0.5} sx={{ pt: 0.5 }}>
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
      </Stack>
    );
  }
  
  // ==============================|| RENDER - READ MODE ||============================== //
  
  const hasValue = value && value.length > 0;
  
  return (
    <Box
      onClick={handleStartEdit}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 1,
        py: 0.5,
        px: 1,
        mx: -1,
        borderRadius: 1,
        cursor: 'pointer',
        transition: 'all 0.2s',
        minHeight: 32,
        bgcolor: isHovered ? alpha(theme.palette.primary.main, 0.08) : 'transparent',
        '&:hover': {
          bgcolor: alpha(theme.palette.primary.main, 0.08)
        }
      }}
    >
      {hasValue ? (
        <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap sx={{ flex: 1 }}>
          {value.map((item) => (
            <Chip
              key={item.id}
              label={getOptionLabel(item)}
              size="small"
              color={chipColor}
              variant="outlined"
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
        <EditOutlined 
          style={{ 
            fontSize: 14, 
            color: theme.palette.primary.main,
            flexShrink: 0
          }} 
        />
      )}
    </Box>
  );
}

EditableMultiSelect.propTypes = {
  value: PropTypes.array,
  options: PropTypes.array,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func.isRequired,
  getOptionLabel: PropTypes.func,
  isOptionEqualToValue: PropTypes.func,
  placeholder: PropTypes.string,
  emptyText: PropTypes.string,
  loading: PropTypes.bool,
  chipColor: PropTypes.string
};