// frontend/src/sections/activities/workspace/ActivityHeader.jsx
/**
 * Activity Header Component
 * 
 * Displays activity information in the workspace header:
 * - Type avatar (circular, colored by type)
 * - Title (editable on hover)
 * - Type, Status, Outcome chips
 * - Account, Origin (Cycle > Step), Scheduled, Due/Completed info
 * - Actions menu (Complete, Cancel, Delete)
 * 
 * Aligned with AccountHeader style pattern.
 */

'use client';

import { useState } from 'react';
import PropTypes from 'prop-types';
import { useRouter } from 'next/navigation';

// MUI
import { useTheme } from '@mui/material/styles';
import Avatar from '@mui/material/Avatar';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Skeleton from '@mui/material/Skeleton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// Date formatting
import { format } from 'date-fns';

// Project imports
import MainCard from 'components/MainCard';
import EditableField from 'sections/accounts/workspace/EditableField';
import {
  cancelActivity,
  updateActivity,
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
  MoreOutlined,
  CheckCircleOutlined,
  StopOutlined,
  DeleteOutlined,
  PhoneOutlined,
  MailOutlined,
  TeamOutlined,
  CheckSquareOutlined,
  LinkedinOutlined,
  QuestionCircleOutlined,
  CalendarOutlined,
  ClockCircleOutlined,
  BankOutlined,
  ApartmentOutlined,
  RightOutlined
} from '@ant-design/icons';

// ==============================|| TYPE CONFIGURATION ||============================== //

const TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined
};

const TYPE_AVATAR_COLORS = {
  CALL: 'info.main',
  EMAIL: 'warning.main',
  MEETING: 'success.main',
  TASK: 'secondary.main',
  LINKEDIN: 'primary.main',
  OTHER: 'grey.500'
};

const TYPE_CHIP_COLORS = {
  CALL: 'info',
  EMAIL: 'warning',
  MEETING: 'success',
  TASK: 'secondary',
  LINKEDIN: 'primary',
  OTHER: 'default'
};

// ==============================|| ACTIVITY HEADER SKELETON ||============================== //

function ActivityHeaderSkeleton() {
  return (
    <MainCard sx={{ mb: 2 }}>
      <Stack spacing={2}>
        {/* Row 1: Avatar + Title */}
        <Stack direction="row" alignItems="center" spacing={2}>
          <Skeleton variant="circular" width={56} height={56} />
          <Skeleton variant="text" width={280} height={40} />
          <Box flex={1} />
          <Skeleton variant="circular" width={32} height={32} />
        </Stack>

        {/* Row 2: Chips */}
        <Stack direction="row" spacing={1}>
          <Skeleton variant="rectangular" width={70} height={24} sx={{ borderRadius: 4 }} />
          <Skeleton variant="rectangular" width={80} height={24} sx={{ borderRadius: 4 }} />
        </Stack>

        {/* Divider */}
        <Divider />

        {/* Row 3: Info items */}
        <Stack direction="row" spacing={3}>
          <Skeleton variant="text" width={150} height={20} />
          <Skeleton variant="text" width={120} height={20} />
          <Skeleton variant="text" width={100} height={20} />
        </Stack>
      </Stack>
    </MainCard>
  );
}

// ==============================|| ACTIVITY HEADER ||============================== //

export default function ActivityHeader({ activity, loading, onSave, onUpdate }) {
  const theme = useTheme();
  const router = useRouter();

  // Menu state (actions)
  const [anchorEl, setAnchorEl] = useState(null);
  const menuOpen = Boolean(anchorEl);

  // Type menu state
  const [typeAnchorEl, setTypeAnchorEl] = useState(null);
  const typeMenuOpen = Boolean(typeAnchorEl);

  // Saving state for type change
  const [savingType, setSavingType] = useState(false);


  // Modal states
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // ==============================|| LOADING STATE ||============================== //

  if (loading) {
    return <ActivityHeaderSkeleton />;
  }

  // ==============================|| NO DATA STATE ||============================== //

  if (!activity) {
    return null;
  }

  // ==============================|| DERIVED VALUES ||============================== //

  const TypeIcon = TYPE_ICONS[activity.activity_type] || QuestionCircleOutlined;
  const avatarColor = TYPE_AVATAR_COLORS[activity.activity_type] || 'grey.500';
  const typeChipColor = TYPE_CHIP_COLORS[activity.activity_type] || 'default';
  
  const isCompleted = activity.status === 'COMPLETED';
  const isCancelled = activity.status === 'CANCELLED';
  const canComplete = !isCompleted && !isCancelled;

  // ==============================|| HANDLERS ||============================== //

  const handleMenuOpen = (event) => setAnchorEl(event.currentTarget);
  const handleMenuClose = () => setAnchorEl(null);

  const handleCompleteClick = () => {
    handleMenuClose();
    setCompleteModalOpen(true);
  };

  const handleCompleteSuccess = () => {
    setCompleteModalOpen(false);
    onUpdate?.();
  };

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

  const handleDeleteClick = () => {
    handleMenuClose();
    setDeleteDialogOpen(true);
  };

  const handleAccountClick = () => {
    if (activity.account_detail?.id) {
      router.push(`/accounts/${activity.account_detail.id}`);
    }
  };

  const handleCycleClick = () => {
    if (activity.account_detail?.id && activity.decision_cycle_detail?.id) {
      router.push(`/accounts/${activity.account_detail.id}?tab=decision-cycle&cycle=${activity.decision_cycle_detail.id}`);
    }
  };

  const handleStepClick = () => {
    if (activity.decision_step_detail?.id) {
      router.push(`/decision-steps/${activity.decision_step_detail.id}`);
    }
  };

  // Type menu handlers
  const handleTypeMenuOpen = (event) => {
    event.stopPropagation();
    setTypeAnchorEl(event.currentTarget);
  };

  const handleTypeMenuClose = () => {
    setTypeAnchorEl(null);
  };

  const handleTypeChange = async (newType) => {
    handleTypeMenuClose();
    if (newType === activity.activity_type) return;

    setSavingType(true);
    try {
      const result = await updateActivity(activity.id, { activity_type: newType });
      if (result.success) {
        displaySuccessSnackbar('Activity type updated');
        onUpdate?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to update type');
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
    } finally {
      setSavingType(false);
    }
  };

  // ==============================|| FORMAT HELPERS ||============================== //

  const formatScheduledDateTime = () => {
    if (!activity.scheduled_date) return null;
    const dateStr = format(new Date(activity.scheduled_date), 'MMM d, yyyy');
    if (activity.scheduled_time) {
      const timeStr = activity.scheduled_time.slice(0, 5);
      return `${dateStr} at ${timeStr}`;
    }
    return dateStr;
  };

  const renderDateInfo = () => {
    // Completed: show completed_at
    if (isCompleted && activity.completed_at) {
      return (
        <Stack direction="row" spacing={0.75} alignItems="center">
          <CheckCircleOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.success.main, display: 'flex' }} />
          <Typography variant="body2" color="success.main">
            {format(new Date(activity.completed_at), 'MMM d, yyyy HH:mm')}
          </Typography>
        </Stack>
      );
    }

    // Cancelled
    if (isCancelled) {
      return (
        <Stack direction="row" spacing={0.75} alignItems="center">
          <StopOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.error.main, display: 'flex' }} />
          <Typography variant="body2" color="error.main">
            Cancelled
          </Typography>
        </Stack>
      );
    }

    // Due date
    if (activity.due_date) {
      const dueDate = new Date(activity.due_date);
      const isOverdue = dueDate < new Date();
      
      return (
        <Stack direction="row" spacing={0.75} alignItems="center">
          <ClockCircleOutlined 
            style={{ 
              fontSize: theme.iconSizes.sm, 
              color: isOverdue ? theme.palette.error.main : theme.palette.text.secondary,
              display: 'flex'
            }} 
          />
          <Typography variant="body2" color={isOverdue ? 'error.main' : 'text.secondary'}>
            Due {format(dueDate, 'MMM d, yyyy')}
          </Typography>
        </Stack>
      );
    }

    return null;
  };

  // ==============================|| RENDER ||============================== //

  return (
    <>
      <MainCard sx={{ mb: 2 }}>
        <Stack spacing={2}>
          {/* Row 1: Avatar + Title + Actions Menu */}
          <Stack direction="row" alignItems="center" spacing={2} sx={{ flexWrap: 'wrap' }}>
            {/* Type Avatar */}
            <Avatar
              sx={{
                width: 56,
                height: 56,
                bgcolor: avatarColor,
                fontSize: '1.5rem'
              }}
            >
              <TypeIcon />
            </Avatar>

            {/* Title - Editable on hover */}
            <Box sx={{ flexGrow: 1, minWidth: 0 }}>
              <EditableField
                value={activity.title}
                fieldKey="title"
                onSave={onSave}
                placeholder="Activity title..."
                variant="h3"
                typographyProps={{ component: 'h1', noWrap: true }}
              />
            </Box>

            {/* Actions Menu */}
            <IconButton onClick={handleMenuOpen}>
              <MoreOutlined />
            </IconButton>
            <Menu anchorEl={anchorEl} open={menuOpen} onClose={handleMenuClose}>
              {canComplete && (
                <MenuItem onClick={handleCompleteClick}>
                  <ListItemIcon>
                    <CheckCircleOutlined style={{ color: theme.palette.success.main }} />
                  </ListItemIcon>
                  <Typography>Complete</Typography>
                </MenuItem>
              )}
              {canComplete && (
                <MenuItem onClick={handleCancelActivity}>
                  <ListItemIcon>
                    <StopOutlined style={{ color: theme.palette.warning.main }} />
                  </ListItemIcon>
                  <Typography>Cancel</Typography>
                </MenuItem>
              )}
              {canComplete && <Divider />}
              <MenuItem onClick={handleDeleteClick}>
                <ListItemIcon>
                  <DeleteOutlined style={{ color: theme.palette.error.main }} />
                </ListItemIcon>
                <Typography color="error.main">Delete</Typography>
              </MenuItem>
            </Menu>
          </Stack>

          {/* Row 2: Type + Status + Outcome Chips */}
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap alignItems="center">
            {/* Type Chip - Clickable to change */}
            <Tooltip title="Click to change type" arrow>
              <Chip
                label={ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type}
                color={typeChipColor}
                size="small"
                variant="filled"
                onClick={handleTypeMenuOpen}
                disabled={savingType}
                sx={{
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  '&:hover': {
                    boxShadow: 1,
                    filter: 'brightness(0.95)'
                  }
                }}
              />
            </Tooltip>

            {/* Type Selection Menu */}
            <Menu
              anchorEl={typeAnchorEl}
              open={typeMenuOpen}
              onClose={handleTypeMenuClose}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'left' }}
              transformOrigin={{ vertical: 'top', horizontal: 'left' }}
              PaperProps={{
                sx: {
                  minWidth: 180,
                  mt: 0.5,
                  boxShadow: theme.customShadows?.z1 || 2
                }
              }}
            >
              {Object.entries(ACTIVITY_TYPE_LABELS).map(([typeKey, typeLabel]) => {
                const TypeIconOption = TYPE_ICONS[typeKey];
                const isSelected = activity.activity_type === typeKey;
                return (
                  <MenuItem
                    key={typeKey}
                    onClick={() => handleTypeChange(typeKey)}
                    selected={isSelected}
                    sx={{
                      py: 1,
                      '&.Mui-selected': {
                        bgcolor: 'primary.lighter',
                        '&:hover': { bgcolor: 'primary.light' }
                      }
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 36 }}>
                      {TypeIconOption && (
                        <TypeIconOption 
                          style={{ 
                            fontSize: theme.iconSizes.lg, 
                            color: isSelected ? theme.palette.primary.main : theme.palette.text.secondary 
                          }} 
                        />
                      )}
                    </ListItemIcon>
                    <Typography 
                      variant="body2" 
                      fontWeight={isSelected ? 600 : 400}
                      color={isSelected ? 'primary.main' : 'text.primary'}
                    >
                      {typeLabel}
                    </Typography>
                  </MenuItem>
                );
              })}
            </Menu>

            {/* Status Chip - Read only (changed via actions menu) */}
            <Chip
              label={ACTIVITY_STATUS_LABELS[activity.status] || activity.status}
              color={ACTIVITY_STATUS_COLORS[activity.status] || 'default'}
              size="small"
              variant="filled"
            />

            {/* Outcome Chip - Only shown when completed */}
            {activity.outcome && (
              <Chip
                label={ACTIVITY_OUTCOME_LABELS[activity.outcome] || activity.outcome}
                color={ACTIVITY_OUTCOME_COLORS[activity.outcome] || 'default'}
                size="small"
                variant="outlined"
              />
            )}
          </Stack>

          {/* Divider */}
          <Divider />

          {/* Row 3: Info Items */}
          <Stack direction="row" spacing={3} alignItems="center" flexWrap="wrap" useFlexGap>
            {/* Account */}
            {activity.account_detail?.company_name && (
              <Stack 
                direction="row" 
                spacing={0.75} 
                alignItems="center"
                onClick={handleAccountClick}
                sx={{ 
                  cursor: 'pointer',
                  '&:hover .info-link': { textDecoration: 'underline' }
                }}
              >
                <BankOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.text.secondary, display: 'flex' }} />
                <Typography variant="body2" color="primary.main" className="info-link">
                  {activity.account_detail.company_name}
                </Typography>
              </Stack>
            )}

            {/* Origin: Decision Cycle > Step */}
            {activity.decision_cycle_detail && (
              <Stack direction="row" spacing={0.75} alignItems="center">
                <ApartmentOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.text.secondary, display: 'flex' }} />
                <Stack direction="row" spacing={0.5} alignItems="center">
                  <Typography
                    variant="body2"
                    color="primary.main"
                    onClick={handleCycleClick}
                    sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                  >
                    {activity.decision_cycle_detail.name}
                  </Typography>
                  {activity.decision_step_detail && (
                    <>
                      <RightOutlined style={{ fontSize: theme.iconSizes.xs - 2, color: theme.palette.text.disabled }} />
                      <Typography
                        variant="body2"
                        color="primary.main"
                        onClick={handleStepClick}
                        sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                      >
                        {activity.decision_step_detail.name}
                      </Typography>
                    </>
                  )}
                </Stack>
              </Stack>
            )}

            {/* TODO: Origin from Campaign (future) */}

            {/* Scheduled Date/Time */}
            {activity.scheduled_date && (
              <Stack direction="row" spacing={0.75} alignItems="center">
                <CalendarOutlined style={{ fontSize: theme.iconSizes.sm, color: theme.palette.text.secondary, display: 'flex' }} />
                <Typography variant="body2" color="text.secondary">
                  {formatScheduledDateTime()}
                </Typography>
              </Stack>
            )}

            {/* Due Date or Completed At */}
            {renderDateInfo()}
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
          window.history.back();
        }}
      />
    </>
  );
}

// ==============================|| PROP TYPES ||============================== //

ActivityHeader.propTypes = {
  activity: PropTypes.shape({
    id: PropTypes.string,
    title: PropTypes.string,
    activity_type: PropTypes.string,
    status: PropTypes.string,
    outcome: PropTypes.string,
    scheduled_date: PropTypes.string,
    scheduled_time: PropTypes.string,
    due_date: PropTypes.string,
    completed_at: PropTypes.string,
    account_detail: PropTypes.shape({
      id: PropTypes.string,
      company_name: PropTypes.string
    }),
    decision_cycle_detail: PropTypes.shape({
      id: PropTypes.string,
      name: PropTypes.string
    }),
    decision_step_detail: PropTypes.shape({
      id: PropTypes.string,
      name: PropTypes.string
    })
  }),
  loading: PropTypes.bool,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};