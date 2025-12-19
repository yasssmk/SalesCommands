// src/sections/accounts/workspace/components/EditableChip.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useRef, useEffect } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import ClickAwayListener from '@mui/material/ClickAwayListener';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Paper from '@mui/material/Paper';
import Popper from '@mui/material/Popper';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// assets
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';

// ==============================|| EDITABLE CHIP ||============================== //

/**
 * Editable Chip Component
 * 
 * Displays a chip with edit-on-hover capability:
 * - Hover to show edit icon
 * - Click edit to open dropdown selector
 * - Select new value or cancel
 * 
 * @param {Object} props
 * @param {string} props.value - Current field value
 * @param {string} props.fieldKey - Field identifier for API update
 * @param {Array} props.options - Array of {value, label} options
 * @param {Function} props.onSave - Callback when value is saved (fieldKey, newValue) => Promise
 * @param {string} props.placeholder - Placeholder when empty
 * @param {string} props.color - Chip color
 * @param {string} props.variant - Chip variant ('filled' | 'outlined')
 * @param {boolean} props.disabled - Disable editing
 * @param {boolean} props.allowClear - Allow clearing the value
 */
export default function EditableChip({
  value,
  fieldKey,
  options = [],
  onSave,
  placeholder = 'Select...',
  color = 'default',
  variant = 'filled',
  disabled = false,
  allowClear = true
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const anchorRef = useRef(null);

  // ==============================|| HANDLERS ||============================== //

  const handleEdit = (e) => {
    e.stopPropagation();
    if (!disabled) {
      setIsOpen(true);
    }
  };

  const handleClose = () => {
    setIsOpen(false);
  };

  const handleSelect = async (newValue) => {
    // Don't save if value hasn't changed
    if (newValue === value) {
      setIsOpen(false);
      return;
    }

    if (onSave) {
      setIsSaving(true);
      try {
        await onSave(fieldKey, newValue);
        setIsOpen(false);
      } catch (error) {
        console.error('Failed to save:', error);
      } finally {
        setIsSaving(false);
      }
    } else {
      setIsOpen(false);
    }
  };

  const handleClear = async (e) => {
    e.stopPropagation();
    await handleSelect(null);
  };

  // ==============================|| HELPERS ||============================== //

  // Find label for current value
  const currentOption = options.find(opt => opt.value === value);
  const displayLabel = currentOption?.label || value;
  const isEmpty = !value;

  // ==============================|| RENDER - EMPTY STATE ||============================== //

  if (isEmpty && !isOpen) {
    return (
      <Box
        ref={anchorRef}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          cursor: disabled ? 'default' : 'pointer',
          borderRadius: 4,
          py: 0.25,
          px: 1,
          border: 1,
          borderStyle: 'dashed',
          borderColor: 'divider',
          transition: 'all 0.2s',
          '&:hover': {
            bgcolor: disabled ? 'transparent' : 'action.hover',
            borderColor: disabled ? 'divider' : 'primary.main'
          }
        }}
        onClick={!disabled ? handleEdit : undefined}
      >
        <Typography
          variant="caption"
          sx={{
            color: 'text.disabled',
            fontStyle: 'italic'
          }}
        >
          {placeholder}
        </Typography>
        {!disabled && isHovered && (
          <Tooltip title="Add">
            <IconButton
              size="small"
              onClick={handleEdit}
              sx={{ p: 0.25, ml: 0.5 }}
            >
              <EditOutlined style={{ fontSize: 12 }} />
            </IconButton>
          </Tooltip>
        )}

        {/* Dropdown Popper */}
        <OptionsPopper
          open={isOpen}
          anchorEl={anchorRef.current}
          options={options}
          value={value}
          onSelect={handleSelect}
          onClose={handleClose}
          isSaving={isSaving}
          allowClear={allowClear}
        />
      </Box>
    );
  }

  // ==============================|| RENDER - WITH VALUE ||============================== //

  return (
    <Box
      ref={anchorRef}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      sx={{ display: 'inline-flex', alignItems: 'center', position: 'relative' }}
    >
      <Chip
        label={displayLabel}
        color={color}
        variant={variant}
        size="small"
        onClick={!disabled ? handleEdit : undefined}
        sx={{
          cursor: disabled ? 'default' : 'pointer',
          transition: 'all 0.2s',
          '&:hover': {
            opacity: disabled ? 1 : 0.85
          }
        }}
      />
      
      {/* Edit Icon on Hover */}
      {!disabled && isHovered && !isOpen && (
        <Box
          sx={{
            position: 'absolute',
            right: -20,
            display: 'flex',
            alignItems: 'center'
          }}
        >
          <Tooltip title="Change">
            <IconButton
              size="small"
              onClick={handleEdit}
              sx={{ p: 0.25 }}
            >
              <EditOutlined style={{ fontSize: 12 }} />
            </IconButton>
          </Tooltip>
        </Box>
      )}

      {/* Dropdown Popper */}
      <OptionsPopper
        open={isOpen}
        anchorEl={anchorRef.current}
        options={options}
        value={value}
        onSelect={handleSelect}
        onClose={handleClose}
        isSaving={isSaving}
        allowClear={allowClear}
      />
    </Box>
  );
}

// ==============================|| OPTIONS POPPER ||============================== //

function OptionsPopper({ open, anchorEl, options, value, onSelect, onClose, isSaving, allowClear }) {
  if (!open) return null;

  return (
    <Popper
      open={open}
      anchorEl={anchorEl}
      placement="bottom-start"
      style={{ zIndex: 1300 }}
    >
      <ClickAwayListener onClickAway={onClose}>
        <Paper
          elevation={8}
          sx={{
            mt: 0.5,
            py: 0.5,
            minWidth: 150,
            maxHeight: 250,
            overflow: 'auto',
            border: 1,
            borderColor: 'divider'
          }}
        >
          {/* Options List */}
          {options.map((option) => (
            <MenuItem
              key={option.value}
              selected={option.value === value}
              onClick={() => onSelect(option.value)}
              disabled={isSaving}
              sx={{
                py: 0.75,
                px: 1.5,
                fontSize: '0.875rem'
              }}
            >
              {option.label}
            </MenuItem>
          ))}
          
          {/* Clear Option */}
          {allowClear && value && (
            <>
              <Box sx={{ borderTop: 1, borderColor: 'divider', my: 0.5 }} />
              <MenuItem
                onClick={() => onSelect(null)}
                disabled={isSaving}
                sx={{
                  py: 0.75,
                  px: 1.5,
                  fontSize: '0.875rem',
                  color: 'error.main'
                }}
              >
                Clear
              </MenuItem>
            </>
          )}

          {/* Cancel Button */}
          <Box sx={{ borderTop: 1, borderColor: 'divider', mt: 0.5, pt: 0.5, px: 1 }}>
            <Stack direction="row" justifyContent="flex-end">
              <Tooltip title="Cancel">
                <IconButton
                  size="small"
                  onClick={onClose}
                  disabled={isSaving}
                >
                  <CloseOutlined style={{ fontSize: 14 }} />
                </IconButton>
              </Tooltip>
            </Stack>
          </Box>
        </Paper>
      </ClickAwayListener>
    </Popper>
  );
}

// ==============================|| PROP TYPES ||============================== //

EditableChip.propTypes = {
  value: PropTypes.string,
  fieldKey: PropTypes.string.isRequired,
  options: PropTypes.arrayOf(
    PropTypes.shape({
      value: PropTypes.string.isRequired,
      label: PropTypes.string.isRequired
    })
  ).isRequired,
  onSave: PropTypes.func,
  placeholder: PropTypes.string,
  color: PropTypes.string,
  variant: PropTypes.oneOf(['filled', 'outlined']),
  disabled: PropTypes.bool,
  allowClear: PropTypes.bool
};

OptionsPopper.propTypes = {
  open: PropTypes.bool.isRequired,
  anchorEl: PropTypes.any,
  options: PropTypes.array.isRequired,
  value: PropTypes.string,
  onSelect: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired,
  isSaving: PropTypes.bool,
  allowClear: PropTypes.bool
};