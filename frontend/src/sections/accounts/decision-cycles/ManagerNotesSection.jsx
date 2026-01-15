// frontend/src/components/ManagerNotesSection.jsx
/**
 * Manager Notes Section Component
 * 
 * Private notes section for managers to communicate with their team members.
 * 
 * Access Rules:
 * - Editable: managers + admin only
 * - Deletable: managers + admin only
 * - Visible: resource owner + their managers + admin
 * - Hidden: if empty AND viewer is not a manager/admin
 * 
 * Note: The backend should enforce that notes are tied to a recipient_owner_id
 * so that if ownership changes, the new owner doesn't see historical notes.
 * 
 * Used in:
 * - Step Detail Overview tab
 * - Activity Overview tab (future)
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useEffect } from 'react';

// material-ui
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CircularProgress from '@mui/material/CircularProgress';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import { alpha, useTheme } from '@mui/material/styles';

// ant-design icons
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import LockOutlined from '@ant-design/icons/LockOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';

// ==============================|| DELETE CONFIRMATION DIALOG ||============================== //

function DeleteConfirmDialog({ open, onClose, onConfirm, deleting }) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
    >
      <DialogTitle>Delete Manager Notes</DialogTitle>
      <DialogContent>
        <DialogContentText>
          Are you sure you want to delete these manager notes? This action cannot be undone.
        </DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={deleting}>
          Cancel
        </Button>
        <Button
          onClick={onConfirm}
          color="error"
          variant="contained"
          disabled={deleting}
          startIcon={deleting ? <CircularProgress size={14} color="inherit" /> : <DeleteOutlined />}
        >
          {deleting ? 'Deleting...' : 'Delete'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

DeleteConfirmDialog.propTypes = {
  open: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired,
  deleting: PropTypes.bool
};

// ==============================|| EMPTY STATE ||============================== //

function EmptyState({ canEdit, onStartEdit }) {
  const theme = useTheme();

  if (!canEdit) {
    // Non-managers don't see empty state at all (component returns null in parent)
    return null;
  }

  return (
    <Box
      sx={{
        p: 2,
        borderRadius: 1,
        border: '1px dashed',
        borderColor: 'divider',
        backgroundColor: alpha(theme.palette.primary.main, 0.02),
        textAlign: 'center'
      }}
    >
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        No manager notes yet
      </Typography>
      <Button
        size="small"
        variant="outlined"
        startIcon={<EditOutlined />}
        onClick={onStartEdit}
      >
        Add Note
      </Button>
    </Box>
  );
}

EmptyState.propTypes = {
  canEdit: PropTypes.bool,
  onStartEdit: PropTypes.func
};

// ==============================|| EDIT MODE ||============================== //

function EditMode({ value, onChange, onSave, onCancel, saving }) {
  return (
    <Box>
      <TextField
        fullWidth
        multiline
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Add private notes for your team member..."
        disabled={saving}
        autoFocus
        sx={{
          '& .MuiOutlinedInput-root': {
            backgroundColor: 'background.paper'
          }
        }}
      />
      <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ mt: 1.5 }}>
        <Button
          size="small"
          color="inherit"
          onClick={onCancel}
          disabled={saving}
          startIcon={<CloseOutlined />}
        >
          Cancel
        </Button>
        <Button
          size="small"
          variant="contained"
          onClick={onSave}
          disabled={saving}
          startIcon={saving ? <CircularProgress size={14} color="inherit" /> : <CheckOutlined />}
        >
          {saving ? 'Saving...' : 'Save'}
        </Button>
      </Stack>
    </Box>
  );
}

EditMode.propTypes = {
  value: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  onSave: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  saving: PropTypes.bool
};

// ==============================|| VIEW MODE ||============================== //

function ViewMode({ notes, canEdit, onStartEdit, onStartDelete }) {
  return (
    <Box>
      <Typography
        variant="body2"
        color="text.primary"
        sx={{
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word'
        }}
      >
        {notes}
      </Typography>
      {canEdit && (
        <Stack direction="row" spacing={1} justifyContent="flex-end" sx={{ mt: 1.5 }}>
          <Button
            size="small"
            color="error"
            variant="text"
            startIcon={<DeleteOutlined />}
            onClick={onStartDelete}
          >
            Delete
          </Button>
          <Button
            size="small"
            variant="text"
            startIcon={<EditOutlined />}
            onClick={onStartEdit}
          >
            Edit
          </Button>
        </Stack>
      )}
    </Box>
  );
}

ViewMode.propTypes = {
  notes: PropTypes.string,
  canEdit: PropTypes.bool,
  onStartEdit: PropTypes.func,
  onStartDelete: PropTypes.func
};

// ==============================|| MANAGER NOTES SECTION ||============================== //

/**
 * ManagerNotesSection Component
 * 
 * @param {string} notes - Current manager notes content
 * @param {boolean} canView - Whether current user can view the notes
 * @param {boolean} canEdit - Whether current user can edit/delete the notes
 * @param {Function} onSave - Callback when saving notes: async (newNotes) => Promise
 * @param {Function} onDelete - Callback when deleting notes: async () => Promise
 * @param {string} title - Optional custom title
 * @param {boolean} loading - Whether notes are being loaded
 */
export default function ManagerNotesSection({
  notes = '',
  canView = false,
  canEdit = false,
  onSave,
  onDelete,
  title = 'Manager Notes',
  loading = false
}) {
  const theme = useTheme();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(notes);
  const [saving, setSaving] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Sync edit value when notes prop changes
  useEffect(() => {
    if (!isEditing) {
      setEditValue(notes);
    }
  }, [notes, isEditing]);

  // Don't render if user can't view
  if (!canView) {
    return null;
  }

  // Don't render empty state for non-editors
  const hasNotes = notes && notes.trim().length > 0;
  if (!hasNotes && !canEdit) {
    return null;
  }

  const handleStartEdit = () => {
    setEditValue(notes);
    setIsEditing(true);
  };

  const handleCancel = () => {
    setEditValue(notes);
    setIsEditing(false);
  };

  const handleSave = async () => {
    if (!onSave) return;

    setSaving(true);
    try {
      await onSave(editValue.trim());
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save manager notes:', error);
      // Keep editing mode open on error
    } finally {
      setSaving(false);
    }
  };

  const handleStartDelete = () => {
    setDeleteDialogOpen(true);
  };

  const handleCancelDelete = () => {
    setDeleteDialogOpen(false);
  };

  const handleConfirmDelete = async () => {
    if (!onDelete) return;

    setDeleting(true);
    try {
      await onDelete();
      setDeleteDialogOpen(false);
    } catch (error) {
      console.error('Failed to delete manager notes:', error);
    } finally {
      setDeleting(false);
    }
  };

  // Loading state
  if (loading) {
    return (
      <Card
        variant="outlined"
        sx={{
          borderRadius: 2,
          backgroundColor: alpha(theme.palette.warning.main, 0.04),
          borderColor: alpha(theme.palette.warning.main, 0.2)
        }}
      >
        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
          <Stack direction="row" alignItems="center" spacing={1}>
            <CircularProgress size={16} />
            <Typography variant="body2" color="text.secondary">
              Loading notes...
            </Typography>
          </Stack>
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card
        variant="outlined"
        sx={{
          borderRadius: 2,
          backgroundColor: alpha(theme.palette.warning.main, 0.04),
          borderColor: alpha(theme.palette.warning.main, 0.2)
        }}
      >
        <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
          {/* Header */}
          <Stack
            direction="row"
            alignItems="center"
            justifyContent="space-between"
            sx={{ mb: hasNotes || isEditing ? 1.5 : 0 }}
          >
            <Stack direction="row" alignItems="center" spacing={1}>
              <TeamOutlined style={{ fontSize: 16, color: theme.palette.warning.main }} />
              <Typography variant="subtitle2" fontWeight={600}>
                {title}
              </Typography>
              <Tooltip title="Only visible to you and your managers">
                <LockOutlined style={{ fontSize: 12, color: theme.palette.text.secondary }} />
              </Tooltip>
            </Stack>
          </Stack>

          {/* Content */}
          {isEditing ? (
            <EditMode
              value={editValue}
              onChange={setEditValue}
              onSave={handleSave}
              onCancel={handleCancel}
              saving={saving}
            />
          ) : hasNotes ? (
            <ViewMode
              notes={notes}
              canEdit={canEdit}
              onStartEdit={handleStartEdit}
              onStartDelete={handleStartDelete}
            />
          ) : (
            <EmptyState
              canEdit={canEdit}
              onStartEdit={handleStartEdit}
            />
          )}
        </CardContent>
      </Card>

      {/* Delete Confirmation Dialog */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        deleting={deleting}
      />
    </>
  );
}

// ==============================|| PROP TYPES ||============================== //

ManagerNotesSection.propTypes = {
  notes: PropTypes.string,
  canView: PropTypes.bool,
  canEdit: PropTypes.bool,
  onSave: PropTypes.func,
  onDelete: PropTypes.func,
  title: PropTypes.string,
  loading: PropTypes.bool
};

// ==============================|| PERMISSION HELPER ||============================== //

/**
 * Determine manager notes visibility and edit permissions
 * 
 * @param {Object} params
 * @param {string} params.currentUserId - Current user's ID
 * @param {string} params.resourceOwnerId - Owner of the step/activity
 * @param {boolean} params.isManager - Whether current user is a manager
 * @param {boolean} params.isAdmin - Whether current user is an admin
 * @param {string[]} params.managedUserIds - IDs of users managed by current user (if manager)
 * @returns {Object} { canView: boolean, canEdit: boolean }
 */
export function getManagerNotesPermissions({
  currentUserId,
  resourceOwnerId,
  isManager = false,
  isAdmin = false,
  managedUserIds = []
}) {
  // Admins can always view and edit
  if (isAdmin) {
    return { canView: true, canEdit: true };
  }

  // Managers can view/edit for their managed users
  if (isManager) {
    const isManagingOwner = managedUserIds.includes(resourceOwnerId);
    return {
      canView: isManagingOwner || currentUserId === resourceOwnerId,
      canEdit: isManagingOwner // Managers edit for their reports, not themselves
    };
  }

  // Regular users can only view their own notes (if they exist)
  // They cannot edit - only their manager can
  if (currentUserId === resourceOwnerId) {
    return { canView: true, canEdit: false };
  }

  // No access
  return { canView: false, canEdit: false };
}
