// frontend/src/components/EditableTextBlock.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

// ant-design icons
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';

// ==============================|| EDITABLE TEXT BLOCK ||============================== //

/**
 * EditableTextBlock — click-to-edit text area with explicit Save / Cancel.
 *
 * Display mode: clickable Box with the saved content (or placeholder).
 * Edit mode:    TextField with the configured rows + Save / Cancel buttons.
 *
 * Save is disabled while saving, or when the value matches the original.
 * On successful save (onSave returns true), exits edit mode automatically.
 * On failure, stays in edit mode so the user can retry.
 *
 * Syncs `value` from `initialValue` whenever the parent's value changes
 * AND the user is not currently editing — prevents a stale local state
 * when the activity SWR cache mutates externally.
 */
export default function EditableTextBlock({
  label,
  field,
  initialValue,
  rows = 5,
  placeholder = 'Click to add...',
  showCharCount = false,
  onSave,
  isLocked = false,
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(initialValue || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!editing) {
      setValue(initialValue || '');
    }
  }, [initialValue, editing]);

  const original = initialValue || '';
  const hasChanges = value !== original;

  const handleSave = async () => {
    if (!hasChanges) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave(field, value);
    setSaving(false);
    if (success) {
      setEditing(false);
    }
  };

  const handleCancel = () => {
    setValue(original);
    setEditing(false);
  };

  return (
    <Box>
      {/* Label row */}
      <Stack direction="row" spacing={1} alignItems="baseline" sx={{ mb: 1 }}>
        <Typography variant="subtitle2" fontWeight={600}>
          {label}
        </Typography>
        {showCharCount && (
          <Typography variant="caption" color="text.secondary">
            {value?.length ?? 0} characters
          </Typography>
        )}
      </Stack>

      {/* Edit / Display */}
      {editing ? (
        <Stack spacing={1}>
          <TextField
            fullWidth
            multiline
            minRows={rows}
            maxRows={rows * 2}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={placeholder}
            disabled={saving}
            autoFocus
          />
          <Stack direction="row" spacing={1} justifyContent="flex-end">
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
              disabled={saving || !hasChanges}
              startIcon={<CheckOutlined />}
            >
              Save
            </Button>
          </Stack>
        </Stack>
      ) : (
        <Box
          onClick={() => !isLocked && setEditing(true)}
          sx={{
            p: 2,
            borderRadius: 1,
            bgcolor: 'action.hover',
            cursor: isLocked ? 'default' : 'pointer',
            minHeight: 60,
            '&:hover': {
              bgcolor: isLocked ? 'action.hover' : 'action.selected',
            },
          }}
        >
          {original ? (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {original}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {placeholder}
            </Typography>
          )}
        </Box>
      )}
    </Box>
  );
}

// ==============================|| PROP TYPES ||============================== //

EditableTextBlock.propTypes = {
  label: PropTypes.string.isRequired,
  field: PropTypes.string.isRequired,
  initialValue: PropTypes.string,
  rows: PropTypes.number,
  placeholder: PropTypes.string,
  showCharCount: PropTypes.bool,
  onSave: PropTypes.func.isRequired,
  isLocked: PropTypes.bool,
};
