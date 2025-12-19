// src/sections/accounts/workspace/components/EditableField.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useRef, useEffect } from 'react';

// material-ui
import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import InputBase from '@mui/material/InputBase';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// assets
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';

// ==============================|| EDITABLE FIELD ||============================== //

/**
 * Editable Field Component
 * 
 * Displays text with edit-on-hover capability:
 * - Hover to show edit icon
 * - Click edit to enter edit mode
 * - Confirm with check or cancel with X
 * 
 * @param {Object} props
 * @param {string} props.value - Current field value
 * @param {string} props.fieldKey - Field identifier for API update
 * @param {Function} props.onSave - Callback when value is saved (fieldKey, newValue) => Promise
 * @param {string} props.placeholder - Placeholder when empty
 * @param {string} props.variant - Typography variant (default: 'body1')
 * @param {Object} props.typographyProps - Additional Typography props
 * @param {ReactNode} props.startIcon - Icon to show before the text
 * @param {boolean} props.disabled - Disable editing
 */
export default function EditableField({
  value,
  fieldKey,
  onSave,
  placeholder = 'Add value...',
  variant = 'body1',
  typographyProps = {},
  startIcon = null,
  disabled = false
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [editValue, setEditValue] = useState(value || '');
  const [isSaving, setIsSaving] = useState(false);
  const inputRef = useRef(null);

  // ==============================|| EFFECTS ||============================== //

  // Focus input when entering edit mode
  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Sync edit value with prop value
  useEffect(() => {
    if (!isEditing) {
      setEditValue(value || '');
    }
  }, [value, isEditing]);

  // ==============================|| HANDLERS ||============================== //

  const handleEdit = (e) => {
    e.stopPropagation();
    if (!disabled) {
      setIsEditing(true);
    }
  };

  const handleCancel = (e) => {
    e?.stopPropagation();
    setEditValue(value || '');
    setIsEditing(false);
  };

  const handleSave = async (e) => {
    e?.stopPropagation();
    
    // Don't save if value hasn't changed
    if (editValue === value) {
      setIsEditing(false);
      return;
    }

    if (onSave) {
      setIsSaving(true);
      try {
        await onSave(fieldKey, editValue);
        setIsEditing(false);
      } catch (error) {
        // Keep editing mode open on error
        console.error('Failed to save:', error);
      } finally {
        setIsSaving(false);
      }
    } else {
      setIsEditing(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSave(e);
    } else if (e.key === 'Escape') {
      handleCancel(e);
    }
  };

  // ==============================|| RENDER - EDIT MODE ||============================== //

  if (isEditing) {
    return (
      <Stack direction="row" alignItems="center" spacing={0.5}>
        {startIcon && (
          <Box sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center' }}>
            {startIcon}
          </Box>
        )}
        <InputBase
          inputRef={inputRef}
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isSaving}
          placeholder={placeholder}
          sx={{
            flex: 1,
            typography: variant,
            '& .MuiInputBase-input': {
              py: 0.25,
              px: 0.5,
              borderRadius: 0.5,
              border: 1,
              borderColor: 'primary.main',
              bgcolor: 'background.paper',
              ...typographyProps.sx
            }
          }}
        />
        <Tooltip title="Save">
          <IconButton
            size="small"
            color="success"
            onClick={handleSave}
            disabled={isSaving}
            sx={{ p: 0.5 }}
          >
            <CheckOutlined style={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Cancel">
          <IconButton
            size="small"
            color="error"
            onClick={handleCancel}
            disabled={isSaving}
            sx={{ p: 0.5 }}
          >
            <CloseOutlined style={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>
      </Stack>
    );
  }

  // ==============================|| RENDER - VIEW MODE ||============================== //

  const displayValue = value || placeholder;
  const isEmpty = !value;

  return (
    <Stack
      direction="row"
      alignItems="center"
      spacing={0.5}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{
        cursor: disabled ? 'default' : 'pointer',
        borderRadius: 0.5,
        py: 0.25,
        px: 0.5,
        mx: -0.5,
        transition: 'background-color 0.2s',
        '&:hover': {
          bgcolor: disabled ? 'transparent' : 'action.hover'
        }
      }}
      onClick={!disabled ? handleEdit : undefined}
    >
      {startIcon && (
        <Box sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center' }}>
          {startIcon}
        </Box>
      )}
      <Typography
        variant={variant}
        {...typographyProps}
        sx={{
          color: isEmpty ? 'text.disabled' : typographyProps.color || 'inherit',
          fontStyle: isEmpty ? 'italic' : 'normal',
          ...typographyProps.sx
        }}
      >
        {displayValue}
      </Typography>
      {!disabled && (
        <Box
          sx={{
            opacity: isHovered ? 1 : 0,
            transition: 'opacity 0.2s',
            display: 'flex',
            alignItems: 'center'
          }}
        >
          <Tooltip title="Edit">
            <IconButton
              size="small"
              onClick={handleEdit}
              sx={{ p: 0.25 }}
            >
              <EditOutlined style={{ fontSize: 12, color: 'inherit' }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}
    </Stack>
  );
}

// ==============================|| PROP TYPES ||============================== //

EditableField.propTypes = {
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  onSave: PropTypes.func,
  placeholder: PropTypes.string,
  variant: PropTypes.string,
  typographyProps: PropTypes.object,
  startIcon: PropTypes.node,
  disabled: PropTypes.bool
};