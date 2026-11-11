// frontend/src/components/EditableTextBlock.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect, useRef } from 'react';

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
 *
 * Optional `onDirtyChange(dirty)` (« Source / Notes » 2.4): reports the
 * UNSAVED state — true while editing with a value different from the saved
 * one, false once saved, cancelled or back to the saved value. A refused Save
 * stays dirty (the edit stays open). The caller declares it to the unsaved
 * changes guard (hooks/useUnsavedChanges).
 *
 * Optional AUTOSAVE mode (« Source / Notes » notes panel, N4) — `autosave`:
 *   - always in edit (no click-to-edit, no Save / Cancel): every change goes
 *     to `onValueChange(value)` — the caller saves (useNoteAutosave);
 *   - `isLocked` → read-only: the text as typed, not editable;
 *   - syncs from `initialValue` as long as the text matches the LAST value
 *     received (nothing typed since) — instead of « while not editing »;
 *   - `indicator`: a slot on the label row (e.g. « Saved · 10:15 »).
 * Without `autosave`, the block is unchanged.
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
  onDirtyChange,
  autosave = false,
  onValueChange,
  indicator,
  ariaLabel,
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(initialValue || '');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!editing && !autosave) {
      setValue(initialValue || '');
    }
  }, [initialValue, editing, autosave]);

  // Autosave: follow the server's value while nothing was typed since the
  // last one received (the typed text is never overwritten).
  const syncedRef = useRef(initialValue || '');
  useEffect(() => {
    if (!autosave) return;
    const next = initialValue || '';
    const previous = syncedRef.current;
    syncedRef.current = next;
    setValue((current) => (current === previous ? next : current));
  }, [initialValue, autosave]);

  const handleAutosaveChange = (next) => {
    setValue(next);
    onValueChange?.(next);
  };

  const original = initialValue || '';
  const hasChanges = value !== original;

  // 2.4 — report the unsaved state to the caller (latest callback, no loop).
  const onDirtyChangeRef = useRef(onDirtyChange);
  onDirtyChangeRef.current = onDirtyChange;
  const dirty = editing && hasChanges;
  useEffect(() => {
    onDirtyChangeRef.current?.(dirty);
  }, [dirty]);

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
        {label && (
          <Typography variant="subtitle2" fontWeight={600}>
            {label}
          </Typography>
        )}
        {showCharCount && (
          <Typography variant="caption" color="text.secondary">
            {value?.length ?? 0} characters
          </Typography>
        )}
        {indicator && <Box sx={{ ml: 'auto' }}>{indicator}</Box>}
      </Stack>

      {/* Autosave (N4): always editable, or read-only when locked */}
      {autosave ? (
        isLocked ? (
          <Box sx={{ p: 2, borderRadius: 1, bgcolor: 'action.hover', minHeight: 60 }}>
            {value ? (
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {value}
              </Typography>
            ) : (
              <Typography variant="body2" color="text.secondary">
                {placeholder}
              </Typography>
            )}
          </Box>
        ) : (
          <TextField
            fullWidth
            multiline
            minRows={rows}
            value={value}
            onChange={(e) => handleAutosaveChange(e.target.value)}
            placeholder={placeholder}
            inputProps={{ 'aria-label': ariaLabel || label || field }}
          />
        )
      ) : /* Edit / Display */
      editing ? (
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
  /** Optional — (dirty: bool) => void: the unsaved state (editing with a
      changed value), for the unsaved changes guard (2.4). */
  onDirtyChange: PropTypes.func,
  /** Optional (N4) — autosave mode: always in edit, no Save / Cancel. */
  autosave: PropTypes.bool,
  /** Optional (N4) — (value: string) => void, every change (autosave). */
  onValueChange: PropTypes.func,
  /** Optional (N4) — a slot on the label row (the save indicator). */
  indicator: PropTypes.node,
  /** Optional (N4b) — the text box's accessible name (autosave; default: the label). */
  ariaLabel: PropTypes.string,
};
