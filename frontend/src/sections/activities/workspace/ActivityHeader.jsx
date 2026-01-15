'use client';

import { useState } from 'react';
import PropTypes from 'prop-types';
import React from 'react';

// MUI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';

// Project imports
import MainCard from 'components/MainCard';
import {
  completeActivity,
  cancelActivity,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS,
  ACTIVITY_OUTCOME_LABELS,
  ACTIVITY_OUTCOME_COLORS
} from 'api/accounts/activities';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

// Modals
import ActivityCompleteModal from 'sections/accounts/activities/ActivityCompleteModal';
import AlertActivityDelete from 'sections/accounts/activities/AlertActivityDelete';

// Icons
import {
  EditOutlined,
  CheckOutlined,
  CloseOutlined,
  MoreOutlined,
  CheckCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  PhoneOutlined,
  MailOutlined,
  TeamOutlined,
  CheckSquareOutlined,
  LinkedinOutlined,
  QuestionCircleOutlined
} from '@ant-design/icons';

// Date formatting
import { format } from 'date-fns';

// Activity type icons mapping
const TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined
};

// ==============================|| ACTIVITY HEADER ||============================== //

export default function ActivityHeader({ activity, onSave, onUpdate }) {

  // Edit title state
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState(activity?.title || '');
  const [saving, setSaving] = useState(false);

  // Menu state
  const [anchorEl, setAnchorEl] = useState(null);
  const menuOpen = Boolean(anchorEl);

  // Modal states
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Get type icon component
  const TypeIcon = TYPE_ICONS[activity?.activity_type];

  // Handle title save
  const handleTitleSave = async () => {
    if (titleValue === activity?.title) {
      setEditingTitle(false);
      return;
    }
    setSaving(true);
    const success = await onSave('title', titleValue);
    setSaving(false);
    if (success) {
      setEditingTitle(false);
    }
  };

  // Handle title cancel
  const handleTitleCancel = () => {
    setTitleValue(activity?.title || '');
    setEditingTitle(false);
  };

  // Handle menu
  const handleMenuOpen = (event) => setAnchorEl(event.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  // Handle complete
  const handleCompleteClick = () => {
    handleMenuClose();
    setCompleteModalOpen(true);
  };

  const handleCompleteSuccess = () => {
    setCompleteModalOpen(false);
    onUpdate?.();
  };

  // Handle cancel activity
  const handleCancelActivity = async () => {
    handleMenuClose();
    const result = await cancelActivity(activity.id);
    if (result.success) {
      displaySuccessSnackbar('Activity cancelled');
      onUpdate?.();
    } else {
      displayErrorSnackbar(result.error || 'Failed to cancel');
    }
  };

  // Handle delete
  const handleDeleteClick = () => {
    handleMenuClose();
    setDeleteDialogOpen(true);
  };

  // Format due date
  const formatDueDate = () => {
    if (!activity?.due_date) return 'No due date';
    return format(new Date(activity.due_date), 'MMM d, yyyy');
  };

  const isCompleted = activity?.status === 'completed';
  const isCancelled = activity?.status === 'cancelled';
  const canComplete = !isCompleted && !isCancelled;

  return (
    <>
      <MainCard sx={{ mb: 0, borderBottomLeftRadius: 0, borderBottomRightRadius: 0 }}>
        <Stack spacing={2}>
          {/* Row 1: Title + Status chips */}
          <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
            <Stack direction="row" spacing={2} alignItems="center" flex={1}>
              {/* Type Icon */}
              {TypeIcon && (
                <Box sx={{ fontSize: 24, color: 'primary.main', display: 'flex', alignItems: 'center' }}>
                  <TypeIcon />
                </Box>
              )}


              {/* Title - Inline Editable */}
              {editingTitle ? (
                <Stack direction="row" spacing={1} alignItems="center" flex={1}>
                  <TextField
                    value={titleValue}
                    onChange={(e) => setTitleValue(e.target.value)}
                    size="small"
                    fullWidth
                    autoFocus
                    disabled={saving}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleTitleSave();
                      if (e.key === 'Escape') handleTitleCancel();
                    }}
                  />
                  <IconButton size="small" onClick={handleTitleSave} disabled={saving} color="success">
                    <CheckOutlined />
                  </IconButton>
                  <IconButton size="small" onClick={handleTitleCancel} disabled={saving} color="error">
                    <CloseOutlined />
                  </IconButton>
                </Stack>
              ) : (
                <Stack direction="row" spacing={1} alignItems="center">
                  <Typography variant="h4">{activity?.title}</Typography>
                  <IconButton size="small" onClick={() => setEditingTitle(true)}>
                    <EditOutlined />
                  </IconButton>
                </Stack>
              )}
            </Stack>

            {/* Status + Outcome Chips */}
            <Stack direction="row" spacing={1} alignItems="center">
              <Chip
                label={ACTIVITY_STATUS_LABELS[activity?.status] || activity?.status}
                color={ACTIVITY_STATUS_COLORS[activity?.status] || 'default'}
                size="small"
              />
              {activity?.outcome && (
                <Chip
                  label={ACTIVITY_OUTCOME_LABELS[activity.outcome] || activity.outcome}
                  color={ACTIVITY_OUTCOME_COLORS[activity.outcome] || 'default'}
                  size="small"
                  variant="outlined"
                />
              )}
            </Stack>
          </Stack>

          {/* Row 2: Meta info + Actions */}
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            {/* Meta info */}
            <Stack direction="row" spacing={2} divider={<Divider orientation="vertical" flexItem />}>
              <Typography variant="body2" color="text.secondary">
                <strong>Account:</strong> {activity?.account_detail?.company_name|| '-'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Type:</strong> {ACTIVITY_TYPE_LABELS[activity?.activity_type] || '-'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Owner:</strong> {activity?.owner_detail?.full_name|| '-'}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                <strong>Due:</strong> {formatDueDate()}
              </Typography>
            </Stack>

            {/* Actions */}
            <Stack direction="row" spacing={1}>
              {canComplete && (
                <Button
                  variant="contained"
                  color="success"
                  size="small"
                  startIcon={<CheckCircleOutlined />}
                  onClick={handleCompleteClick}
                >
                  Complete
                </Button>
              )}
              <IconButton onClick={handleMenuOpen}>
                <MoreOutlined />
              </IconButton>
              <Menu anchorEl={anchorEl} open={menuOpen} onClose={handleMenuClose}>
                {canComplete && (
                  <MenuItem onClick={handleCancelActivity}>
                    <StopOutlined style={{ marginRight: 8 }} />
                    Cancel Activity
                  </MenuItem>
                )}
                <MenuItem onClick={handleDeleteClick} sx={{ color: 'error.main' }}>
                  <DeleteOutlined style={{ marginRight: 8 }} />
                  Delete
                </MenuItem>
              </Menu>
            </Stack>
          </Stack>
        </Stack>
      </MainCard>

      {/* Complete Modal */}
      <ActivityCompleteModal
        open={completeModalOpen}
        onClose={() => setCompleteModalOpen(false)}
        activity={activity}
        onSuccess={handleCompleteSuccess}
      />

      {/* Delete Dialog */}
      <AlertActivityDelete
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
        activity={activity}
        onSuccess={() => {
          setDeleteDialogOpen(false);
          // Navigate back after delete
          window.history.back();
        }}
      />
    </>
  );
}

ActivityHeader.propTypes = {
  activity: PropTypes.object.isRequired,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};
