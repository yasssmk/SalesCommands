// frontend/src/sections/accounts/decision-cycles/DecisionCycleTimeline.jsx
/**
 * Decision Cycle Timeline Component (Pipeline View)
 * 
 * Displays a horizontal pipeline of FIXED steps with activities as cards.
 * 
 * ARCHITECTURE:
 * - Columns = Fixed Pipeline Steps (7 steps, auto-created)
 * - Cards = Activities within each step
 * 
 * Users CANNOT create/delete steps - only add activities within them.
 * Users CAN hide/show columns (persisted in localStorage per cycle).
 * 
 * Features:
 * - 7 fixed pipeline steps as columns
 * - Activities displayed as cards within each step column
 * - Color-coded status indicators
 * - Stalled detection warnings
 * - Add activity button per step
 * - Hide/show columns (saved per cycle in localStorage)
 * - Click on step header → Step Workspace
 * - Click on activity card → Activity Workspace
 */

'use client';

import PropTypes from 'prop-types';
import { useMemo, useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';

// material-ui
import { useTheme, alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import Checkbox from '@mui/material/Checkbox';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import Alert from '@mui/material/Alert';
import AlertTitle from '@mui/material/AlertTitle';
import Badge from '@mui/material/Badge';
import MenuItem from '@mui/material/MenuItem';

// icons
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';
import CloseCircleFilled from '@ant-design/icons/CloseCircleFilled';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import SyncOutlined from '@ant-design/icons/SyncOutlined';
import PauseCircleOutlined from '@ant-design/icons/PauseCircleOutlined';
import MinusCircleOutlined from '@ant-design/icons/MinusCircleOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import ApartmentOutlined from '@ant-design/icons/ApartmentOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import SettingOutlined from '@ant-design/icons/SettingOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import EyeInvisibleOutlined from '@ant-design/icons/EyeInvisibleOutlined';
import UserOutlined from '@ant-design/icons/UserOutlined';
import LinkOutlined from '@ant-design/icons/LinkOutlined';
import {
  PIPELINE_STEPS_ORDER,
  PIPELINE_STEP_LABELS,
  PIPELINE_STEP_CONFIG,
  CYCLE_DERIVED_STATUS_LABELS,
  CYCLE_STATUS_COLORS,
} from 'api/accounts/decisionCycles';

import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';
import LinkActivityModal from './LinkActivityModal';
import CycleCloseDialog, { useCycleCloseReopen } from 'sections/accounts/dc-workspace/CycleCloseDialog';

// ==============================|| LOCALSTORAGE HELPERS ||============================== //

const STORAGE_KEY_PREFIX = 'convyns_pipeline_columns_';

/**
 * Get hidden columns from localStorage for a specific cycle
 */
const getHiddenColumns = (cycleId) => {
  if (typeof window === 'undefined' || !cycleId) return [];
  try {
    const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${cycleId}`);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
};

/**
 * Save hidden columns to localStorage for a specific cycle
 */
const saveHiddenColumns = (cycleId, hiddenColumns) => {
  if (typeof window === 'undefined' || !cycleId) return;
  try {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${cycleId}`, JSON.stringify(hiddenColumns));
  } catch {
    // localStorage might be full or disabled
  }
};

// ==============================|| STATUS CONFIG ||============================== //

/**
 * Step derived status config for timeline columns.
 * Status is 100% derived from activities by backend.
 * 
 * WON/REJECTED/ON_HOLD removed — now handled at cycle level via CycleOutcome.
 * STALLED added — deal dormant, no planned activities in last completed step.
 */
const STATUS_CONFIG = {
  OVERDUE: {
    color: 'error',
    bgColor: 'error.lighter',
    icon: ClockCircleOutlined,
    label: 'Overdue'
  },
  VALIDATED: {
    color: 'primary',
    bgColor: 'primary.lighter',
    icon: CheckCircleFilled,
    label: 'Validated'
  },
  IN_PROGRESS: {
    color: 'secondary',
    bgColor: 'secondary.lighter',
    icon: SyncOutlined,
    label: 'In Progress'
  },
  STALLED: {
    color: 'warning',
    bgColor: 'warning.lighter',
    icon: PauseCircleOutlined,
    label: 'Stalled'
  },
  IN_CHASING: {
    color: 'warning',
    bgColor: 'warning.lighter',
    icon: ClockCircleOutlined,
    label: 'In Chasing'
  },
  NOT_STARTED: {
    color: 'default',
    bgColor: 'grey.200',
    icon: MinusCircleOutlined,
    label: 'Not Started'
  },
  CYCLE_LOST: {
    color: 'error',
    bgColor: 'error.lighter',
    icon: CloseCircleFilled,
    label: 'Lost'
  },
  CYCLE_ON_HOLD: {
    color: 'warning',
    bgColor: 'warning.lighter',
    icon: PauseCircleOutlined,
    label: 'On Hold'
  },
  CYCLE_NOT_QUALIFIED: {
    color: 'error',
    bgColor: 'error.lighter',
    icon: CloseCircleFilled,
    label: 'Not Qualified'
  } 
};

// ==============================|| ACTIVITY TYPE ICONS ||============================== //

const ACTIVITY_TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: MailOutlined,
  OTHER: CalendarOutlined
};

// ==============================|| ACTIVITY CARD ||============================== //

/**
 * Activity Status Configuration
 */
const ACTIVITY_STATUS_CONFIG = {
  PLANNED: { color: 'info', label: 'Planned', icon: CalendarOutlined },
  IN_PROGRESS: { color: 'warning', label: 'In Progress', icon: SyncOutlined },
  COMPLETED: { color: 'success', label: 'Completed', icon: CheckCircleFilled },
  CANCELLED: { color: 'default', label: 'Cancelled', icon: CloseCircleFilled }
};

/**
 * Activity Outcome Configuration
 * 
 * Keys match backend ActivityOutcome choices.
 * Category determines border/background color on activity cards:
 * - positive: green (deal advancing)
 * - neutral: warning (needs attention, ambiguous)
 * - negative: error (deal at risk)
 */
const ACTIVITY_OUTCOME_CONFIG = {
  SUCCESSFUL:         { color: 'success', label: 'Successful',         category: 'positive' },
  MEETING_SCHEDULED:  { color: 'success', label: 'Meeting Scheduled',  category: 'positive' },
  NO_ANSWER:          { color: 'warning', label: 'No Answer',          category: 'neutral' },
  CALLBACK_REQUESTED: { color: 'info',    label: 'Callback Requested', category: 'neutral' },
  FOLLOW_UP_NEEDED:   { color: 'warning', label: 'Follow-up Needed',  category: 'neutral' },
  OTHER:              { color: 'default', label: 'Other',              category: 'neutral' },
  NOT_INTERESTED:     { color: 'error',   label: 'Not Interested',     category: 'negative' },
  WRONG_CONTACT:      { color: 'error',   label: 'Wrong Contact',      category: 'negative' }
};

/**
 * Activity Card Component
 * 
 * Enriched card for displaying an activity within a pipeline step.
 * Shows: title, type, date/time, contact, status, outcome
 */
function ActivityCard({ activity, onClick }) {
  const theme = useTheme();
  
  const TypeIcon = ACTIVITY_TYPE_ICONS[activity.activity_type] || CalendarOutlined;
  const statusConfig = ACTIVITY_STATUS_CONFIG[activity.status] || ACTIVITY_STATUS_CONFIG.PLANNED;
  const outcomeConfig = activity.outcome ? ACTIVITY_OUTCOME_CONFIG[activity.outcome] : null;
  
  const isCompleted = activity.status === 'COMPLETED';
  const isCancelled = activity.status === 'CANCELLED';
  // Overdue: check scheduled_date first, fallback to due_date
  const activityDate = activity.scheduled_date || activity.due_date;
  const isOverdue = activityDate && 
    new Date(activityDate) < new Date() && 
    !isCompleted && !isCancelled;
  
  // Format date with relative display
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
    if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
    
    // Show day of week if within 7 days
    const diffDays = Math.ceil((date - today) / (1000 * 60 * 60 * 24));
    if (diffDays > 0 && diffDays <= 7) {
      return date.toLocaleDateString('en-US', { weekday: 'short' });
    }
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };
  
  // Format time (HH:MM)
  const formatTime = (timeStr) => {
    if (!timeStr) return null;
    return timeStr.slice(0, 5);
  };

  // Outcome category for completed activities (positive/neutral/negative)
  const outcomeCategory = outcomeConfig?.category || 'neutral';

  // Get border color based on state + outcome
  const getBorderColor = () => {
    if (isCancelled) return theme.palette.grey[300];
    if (isCompleted) {
      if (outcomeCategory === 'positive') return theme.palette.success.light;
      if (outcomeCategory === 'negative') return theme.palette.error.light;
      return theme.palette.warning.light; // neutral outcome
    }
    if (isOverdue) return theme.palette.error.light;
    return theme.palette.divider;
  };
  
  // Get background color based on state + outcome
  const getBgColor = () => {
    if (isCancelled) return alpha(theme.palette.grey[500], 0.04);
    if (isCompleted) {
      if (outcomeCategory === 'positive') return alpha(theme.palette.success.main, 0.04);
      if (outcomeCategory === 'negative') return alpha(theme.palette.error.main, 0.04);
      return alpha(theme.palette.warning.main, 0.04); // neutral outcome
    }
    if (isOverdue) return alpha(theme.palette.error.main, 0.04);
    return 'background.paper';
  };

  return (
    <Paper
      elevation={0}
      onClick={() => onClick?.(activity)}
      sx={{
        p: 1.25,
        cursor: 'pointer',
        border: '1px solid',
        borderColor: getBorderColor(),
        borderRadius: 1.5,
        bgcolor: getBgColor(),
        opacity: isCancelled ? 0.6 : 1,
        transition: 'all 0.2s ease',
        '&:hover': {
          borderColor: 'primary.main',
          bgcolor: alpha(theme.palette.primary.main, 0.04),
          transform: 'translateY(-1px)',
          boxShadow: theme.shadows[2]
        }
      }}
    >
      <Stack spacing={0.75}>
        {/* Row 1: Type icon + Title + Status indicator */}
        <Stack direction="row" alignItems="flex-start" spacing={0.75}>
          <Tooltip title={activity.activity_type_display || activity.activity_type}>
            <Box
              sx={{
                p: 0.5,
                borderRadius: 1,
                bgcolor: isOverdue 
                  ? alpha(theme.palette.error.main, 0.12) 
                  : alpha(theme.palette.text.secondary, 0.08),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <TypeIcon style={{ 
                fontSize: theme.iconSizes.sm, 
                color: isOverdue ? theme.palette.error.main : theme.palette.text.secondary 
              }} />
            </Box>
          </Tooltip>
          <Typography 
            variant="body2" 
            fontWeight={theme.typography.fontWeightMedium}
            sx={{ 
              flex: 1,
              lineHeight: 1.3,
              textDecoration: isCancelled ? 'line-through' : 'none',
              color: isCancelled ? 'text.disabled' : isCompleted ? 'text.secondary' : 'text.primary',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden'
            }}
          >
            {activity.title || activity.activity_type_display || 'Activity'}
          </Typography>
        </Stack>
        
        {/* Row 2: Date/Time */}
        <Stack direction="row" alignItems="center" spacing={0.5} flexWrap="wrap">
          {activityDate && (
            <Stack direction="row" alignItems="center" spacing={0.25}>
              <CalendarOutlined style={{ fontSize: theme.iconSizes?.xs, color: isOverdue ? theme.palette.error.main : theme.palette.text.disabled }} />
              <Typography 
                variant="caption" 
                sx={{
                  color: isOverdue ? 'error.main' : 'text.secondary',
                  fontWeight: isOverdue ? 600 : 400
                }}
              >
                {formatDate(activityDate)}
              </Typography>
            </Stack>
          )}
          {activity.scheduled_time && (
            <Typography variant="caption" color="text.secondary">
              {formatTime(activity.scheduled_time)}
            </Typography>
          )}
        </Stack>
        
        {/* Row 3: Primary contact */}
        {activity.primary_contact && (
          <Stack direction="row" alignItems="center" spacing={0.5}>
            <UserOutlined style={{ fontSize: 11, color: theme.palette.text.disabled }} />
            <Typography variant="caption" color="text.secondary" noWrap sx={{ flex: 1 }}>
              {activity.primary_contact.name}
              {activity.primary_contact.job_title && (
                <Typography component="span" variant="caption" color="text.disabled">
                  {' · '}{activity.primary_contact.job_title}
                </Typography>
              )}
            </Typography>
            {activity.contacts_count > 1 && (
              <Chip
                label={`+${activity.contacts_count - 1}`}
                size="small"
                variant="outlined"
                sx={{ height: 16, fontSize: '0.6rem', '& .MuiChip-label': { px: 0.5 } }}
              />
            )}
          </Stack>
        )}
        
        {/* Row 4: Status + Outcome (if completed) */}
        <Stack direction="row" alignItems="center" justifyContent="space-between" spacing={0.5}>
          <Chip
            label={isOverdue ? 'Overdue' : statusConfig.label}
            size="small"
            color={isOverdue ? 'error' : statusConfig.color}
            variant={isCompleted || isCancelled || isOverdue ? 'filled' : 'outlined'}
            sx={{ height: 18, fontSize: '0.65rem', '& .MuiChip-label': { px: 0.75 } }}
          />
          {outcomeConfig && (
            <Chip
              label={outcomeConfig.label}
              size="small"
              color={outcomeConfig.color}
              variant="filled"
              sx={{ height: 18, fontSize: '0.65rem', '& .MuiChip-label': { px: 0.75 } }}
            />
          )}
        </Stack>
      </Stack>
    </Paper>
  );
}

ActivityCard.propTypes = {
  activity: PropTypes.object.isRequired,
  onClick: PropTypes.func
};

// ==============================|| PIPELINE STEP COLUMN ||============================== //

/**
 * Pipeline Step Column Component
 * 
 * A single column representing a fixed pipeline step.
 * Displays step header with status + activities as cards.
 */
function PipelineStepColumn({ 
  step, 
  activities,
  onStepClick, 
  onActivityClick,
  onAddActivity,
  onLinkExisting,
  isCycleClosed = false
}) {
  const theme = useTheme();
  
  if (!step) return null;
  
  const statusConfig = STATUS_CONFIG[step.derived_status] || STATUS_CONFIG.NOT_STARTED;
  const StatusIcon = statusConfig.icon;
  const stepConfig = PIPELINE_STEP_CONFIG[step.stage] || {};
  const isActivityOptional = stepConfig.activity_optional || step.is_activity_optional || false;
  
  // Determine column state from derived status
  const isValidated = step.derived_status === 'VALIDATED';
  const isOverdue = step.derived_status === 'OVERDUE';
  const isStalled = step.derived_status === 'STALLED';
  
  // Filter out cancelled activities — not visible, not counted
  const visibleActivities = activities?.filter(a => a.status !== 'CANCELLED') || [];
  const hasActivities = visibleActivities.length > 0;
  
  // Activity statistics
  const totalActivities = visibleActivities.length;
  const completedActivities = visibleActivities.filter(a => a.status === 'COMPLETED').length;
  const progressPercent = totalActivities > 0 ? Math.round((completedActivities / totalActivities) * 100) : 0;
  
 // Short date formatter
  const formatShortDate = (dateStr) => {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Step lifecycle states
  const STARTED_STATUSES = ['IN_PROGRESS', 'OVERDUE', 'STALLED', 'IN_CHASING', 'VALIDATED'];
  const CLOSED_STATUSES = ['VALIDATED', 'CYCLE_LOST', 'CYCLE_NOT_QUALIFIED', 'CYCLE_ON_HOLD'];

  const isStepStarted = STARTED_STATUSES.includes(step.derived_status) || CLOSED_STATUSES.includes(step.derived_status);
  const isStepClosed = CLOSED_STATUSES.includes(step.derived_status);
  // Start date: effective_start_date (observed) > start_date (manual)
  const startDateValue = step.effective_start_date || step.start_date || null;
  const isStartConfirmed = isStepStarted && !!startDateValue;

  // End date: completed_at (closed) > effective_end_date (last activity) > expected_end (manual fallback)
  // STALLED: no end date shown — step is stuck, not ended
  const isEndSettled = isStepClosed;
  const endDateValue = isStalled
    ? null
    : isEndSettled
      ? (step.completed_at || step.effective_end_date || step.expected_end)
      : (step.effective_end_date || step.expected_end || null);
  const isEndConfirmed = isStepClosed && !!endDateValue;

  // Overdue: end date is past and step is NOT closed and NOT stalled
  const isEndOverdue = !isEndSettled && !isStalled && endDateValue && new Date(endDateValue) < new Date();
  
  // Column border color — derived from step status
  const getBorderColor = () => {
    if (step.derived_status === 'CYCLE_LOST' || step.derived_status === 'CYCLE_NOT_QUALIFIED') return theme.palette.error.main;
    if (step.derived_status === 'CYCLE_ON_HOLD') return theme.palette.warning.main;
    if (isValidated) return theme.palette.primary.main;
    if (isOverdue) return theme.palette.error.light;
    if (isStalled) return theme.palette.warning.light;
    if (step.derived_status === 'IN_PROGRESS') return theme.palette.secondary.main;
    return theme.palette.divider;
  };

  return (
    <Paper
      elevation={0}
      sx={{
        flex: '0 0 220px',
        minWidth: 220,
        maxWidth: 260,
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: getBorderColor(),
        borderRadius: 2,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        transition: 'border-color 0.2s ease'
      }}
    >
      {/* Step Header - Clickable */}
      <Box
        onClick={() => onStepClick?.(step)}
        sx={{
          p: 1.5,
          bgcolor: (isValidated || isOverdue || isStalled)
            ? alpha(theme.palette[statusConfig.color]?.main || theme.palette.grey[500], 0.08)
            : alpha(theme.palette.background.default, 0.6),
          borderBottom: '1px solid',
          borderColor: 'divider',
          cursor: 'pointer',
          transition: 'background-color 0.2s ease',
          '&:hover': {
            bgcolor: alpha(theme.palette[statusConfig.color]?.main || theme.palette.primary.main, 0.14)
          }
        }}
      >
        <Stack spacing={0.75}>
          {/* Step name + Status icon */}
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle2" fontWeight={theme.typography.fontWeightBold} noWrap sx={{ flex: 1 }}>
              {step.name}
            </Typography>
            <Tooltip title={statusConfig.label}>
              <StatusIcon style={{ 
                fontSize: theme.iconSizes.md, 
                color: theme.palette[statusConfig.color]?.main || theme.palette.grey[500]
              }} />
            </Tooltip>
          </Stack>
          
          {/* Activity progress bar (only if has activities) */}
          {totalActivities > 0 && (
            <Box>
              <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 0.25 }}>
                <Typography variant="caption" color="text.secondary">
                  {completedActivities}/{totalActivities} activities
                </Typography>
                <Typography variant="caption" color={progressPercent === 100 ? 'success.main' : 'text.secondary'}>
                  {progressPercent}%
                </Typography>
              </Stack>
              <Box
                sx={{
                  height: 4,
                  borderRadius: 2,
                  bgcolor: 'grey.200',
                  overflow: 'hidden'
                }}
              >
                <Box
                  sx={{
                    height: '100%',
                    width: `${progressPercent}%`,
                    bgcolor: progressPercent === 100 ? 'success.main' : 'primary.main',
                    borderRadius: 2,
                    transition: 'width 0.3s ease'
                  }}
                />
              </Box>
            </Box>
          )}
          
          {/* Aggregated departments
          {step.all_departments_list && step.all_departments_list.length > 0 && (
            <Stack direction="row" alignItems="center" spacing={0.75} flexWrap="wrap" sx={{ mt: 0.25 }}>
              {step.all_departments_list.map((dept) => (
                <Chip
                  key={dept.id}
                  label={dept.name}
                  size="small"
                  variant="outlined"
                  sx={{ 
                    height: 16, 
                    fontSize: '0.6rem', 
                    '& .MuiChip-label': { px: 0.5 },
                    borderColor: 'grey.300',
                    color: 'text.secondary'
                  }}
                />
              ))}
            </Stack>
          )} */}

          {/* Timeline: Start ←→ End */}
          {(startDateValue || endDateValue) && (
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              {/* Start date */}
              {startDateValue ? (
                <Tooltip title={isStartConfirmed ? 'Started' : 'Projected start'}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'text.secondary',
                      fontStyle: isStartConfirmed ? 'normal' : 'italic',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.25
                    }}
                  >
                    <CalendarOutlined style={{ fontSize: theme.iconSizes?.xs, color: theme.palette.text.disabled }} />
                    {isStartConfirmed
                      ? formatShortDate(startDateValue)
                      : `(${formatShortDate(startDateValue)})`
                    }
                  </Typography>
                </Tooltip>
              ) : (
                <Box />
              )}

             {/* End date — STALLED shows warning icon instead of date */}
              {isStalled ? (
                <Tooltip title="Stalled — no planned activities">
                  <Typography
                    variant="caption"
                    sx={{
                      color: 'warning.main',
                      fontWeight: theme.typography.fontWeightMedium,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.25
                    }}
                  >
                    <PauseCircleOutlined style={{ fontSize: theme.iconSizes.xs, color: theme.palette.warning.main }} />
                    Stalled
                  </Typography>
                </Tooltip>
              ) : endDateValue ? (
                <Tooltip title={
                  isEndConfirmed ? 'Closed'
                    : isEndOverdue ? 'Overdue'
                    : 'Expected end'
                }>
                  <Typography
                    variant="caption"
                    sx={{
                      color: isEndConfirmed
                        ? 'success.main'
                        : isEndOverdue ? 'error.main'
                        : 'text.secondary',
                      fontStyle: isEndConfirmed ? 'normal' : 'italic',
                      fontWeight: (isEndConfirmed || isEndOverdue) ? theme.typography.fontWeightMedium : theme.typography.fontWeightRegular,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.25
                    }}
                  >
                    {isEndConfirmed
                      ? <CheckCircleFilled style={{ fontSize: theme.iconSizes.xs, color: theme.palette.success.main }} />
                      : <ClockCircleOutlined style={{ fontSize: theme.iconSizes.xs, color: isEndOverdue ? theme.palette.error.main : theme.palette.text.disabled }} />
                    }
                    {isEndConfirmed
                      ? formatShortDate(endDateValue)
                      : `(${formatShortDate(endDateValue)})`
                    }
                  </Typography>
                </Tooltip>
              ) : (
                <Box />
              )}
            </Stack>
          )}
        </Stack>
      </Box>
      
      {/* Activities List */}
      <Box
        sx={{
          flex: 1,
          p: 1,
          minHeight: 100,
          maxHeight: 300,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 1
        }}
      >
        {!hasActivities ? (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              p: 2
            }}
          >
            <Typography variant="caption" color="text.disabled" textAlign="center">
              {isActivityOptional 
                ? 'No activity required' 
                : 'No activities yet'
              }
            </Typography>
          </Box>
        ) : (
          visibleActivities.map((activity) => (
            <ActivityCard
              key={activity.id}
              activity={activity}
              onClick={onActivityClick}
            />
          ))
        )}
      </Box>
      
      {/* Action Buttons (hidden when cycle is closed) */}
      {!isCycleClosed && (
        <Box sx={{ p: 1, borderTop: '1px solid', borderColor: 'divider' }}>
          <Stack spacing={0.5}>
            {/* Add New Activity */}
            <Button
              size="small"
              startIcon={<PlusOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onAddActivity?.(step);
              }}
              fullWidth
              sx={{
                justifyContent: 'flex-start',
                color: 'text.secondary',
                '&:hover': {
                  bgcolor: 'primary.lighter',
                  color: 'primary.main'
                }
              }}
            >
              Add Activity
            </Button>
            
            {/* Link Existing Activity */}
            <Button
              size="small"
              startIcon={<LinkOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                onLinkExisting?.(step);
              }}
              fullWidth
              sx={{
                justifyContent: 'flex-start',
                color: 'text.secondary',
                '&:hover': {
                  bgcolor: 'secondary.lighter',
                  color: 'secondary.main'
                }
              }}
            >
              Link Existing
            </Button>
          </Stack>
        </Box>
      )}
    </Paper>
  );
}

PipelineStepColumn.propTypes = {
  step: PropTypes.object,
  activities: PropTypes.array,
  onStepClick: PropTypes.func,
  onActivityClick: PropTypes.func,
  onAddActivity: PropTypes.func,
  onLinkExisting: PropTypes.func,
  isCycleClosed: PropTypes.bool
};

// ==============================|| COLUMN VISIBILITY MENU ||============================== //

/**
 * Column Visibility Menu
 * 
 * Allows users to show/hide pipeline columns.
 */
function ColumnVisibilityMenu({ steps, hiddenColumns, onToggleColumn, onShowAll }) {
  const [anchorEl, setAnchorEl] = useState(null);
  const open = Boolean(anchorEl);
  
  const hiddenCount = hiddenColumns.length;
  
  const handleClick = (event) => {
    setAnchorEl(event.currentTarget);
  };
  
  const handleClose = () => {
    setAnchorEl(null);
  };
  
  const handleToggle = (stepId) => {
    onToggleColumn(stepId);
  };

  return (
    <>
      <Tooltip title="Configure pipeline steps">
        <IconButton 
          onClick={handleClick}
          size="small"
          sx={{ 
            border: '1px solid',
            borderColor: hiddenCount > 0 ? 'primary.main' : 'divider',
            bgcolor: hiddenCount > 0 ? 'primary.lighter' : 'transparent'
          }}
        >
          <Badge badgeContent={hiddenCount} color="primary" max={9}>
            <SettingOutlined />
          </Badge>
        </IconButton>
      </Tooltip>
      
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        PaperProps={{
          sx: { minWidth: 250, maxHeight: 400 }
        }}
      >
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant="subtitle2" color="text.secondary">
            Pipeline Steps
          </Typography>
        </Box>
        
        <Divider />
        
        {steps.map((step) => {
          const isHidden = hiddenColumns.includes(step.id);
          const stepConfig = PIPELINE_STEP_CONFIG[step.stage] || {};
          const visibleActivities = (step.activities || []).filter(a => a.status !== 'CANCELLED');
          const hasActivities = visibleActivities.length > 0;
          // Cannot uncheck (hide) a step that has activities
          const isLocked = !isHidden && hasActivities;
          
          return (
            <Tooltip
              key={step.id}
              title={isLocked ? 'Cannot hide — step has activities' : ''}
              placement="left"
            >
              <span>
                <MenuItem 
                  onClick={() => !isLocked && handleToggle(step.id)}
                  dense
                  disabled={isLocked}
                >
                  <ListItemIcon>
                    <Checkbox
                      checked={!isHidden}
                      size="small"
                      disabled={isLocked}
                      sx={{ p: 0 }}
                    />
                  </ListItemIcon>
                  <ListItemText 
                    primary={step.name}
                    secondary={stepConfig.activity_optional ? 'Optional' : hasActivities ? `${visibleActivities.length} activit${visibleActivities.length > 1 ? 'ies' : 'y'}` : null}
                    primaryTypographyProps={{ variant: 'body2' }}
                    secondaryTypographyProps={{ variant: 'caption' }}
                  />
                  {isHidden ? (
                    <EyeInvisibleOutlined style={{ fontSize: 14, color: 'grey' }} />
                  ) : (
                    <EyeOutlined style={{ fontSize: 14 }} />
                  )}
                </MenuItem>
              </span>
            </Tooltip>
          );
        })}
        
        <Divider sx={{ my: 1 }} />
        
        <Box sx={{ px: 1, pb: 1 }}>
          <Button 
            size="small" 
            onClick={() => { onShowAll(); handleClose(); }}
            disabled={hiddenCount === 0}
            fullWidth
          >
            Show All Steps
          </Button>
        </Box>
      </Menu>
    </>
  );
}

ColumnVisibilityMenu.propTypes = {
  steps: PropTypes.array.isRequired,
  hiddenColumns: PropTypes.array.isRequired,
  onToggleColumn: PropTypes.func.isRequired,
  onShowAll: PropTypes.func.isRequired
};

// ==============================|| HIDDEN COLUMNS INDICATOR ||============================== //

/**
 * Shows hidden columns as chips that can be clicked to reveal
 */
function HiddenColumnsIndicator({ steps, hiddenColumns, onToggleColumn }) {
  const hiddenSteps = steps.filter(s => hiddenColumns.includes(s.id));
  
  if (hiddenSteps.length === 0) return null;
  
  return (
    <Stack direction="row" spacing={0.5} alignItems="center" sx={{ ml: 2 }}>
      <Typography variant="caption" color="text.secondary">
        Disabled:
      </Typography>
      {hiddenSteps.map((step) => (
        <Chip
          key={step.id}
          label={step.name}
          size="small"
          variant="outlined"
          onClick={() => onToggleColumn(step.id)}
          onDelete={() => onToggleColumn(step.id)}
          deleteIcon={<EyeOutlined style={{ fontSize: 12 }} />}
          sx={{ 
            height: 24,
            '& .MuiChip-label': { px: 1, fontSize: '0.7rem' }
          }}
        />
      ))}
    </Stack>
  );
}

HiddenColumnsIndicator.propTypes = {
  steps: PropTypes.array.isRequired,
  hiddenColumns: PropTypes.array.isRequired,
  onToggleColumn: PropTypes.func.isRequired
};

// ==============================|| DECISION CYCLE TIMELINE ||============================== //

/**
 * Main Pipeline Timeline Component
 * 
 * @param {Object} props
 * @param {Object} props.cycle - Decision cycle data with steps
 * @param {Function} props.onStepClick - Callback when step header clicked
 * @param {Function} props.onActivityClick - Callback when activity card clicked
 * @param {Function} props.onAddActivity - Callback when add activity clicked (receives step)
 * @param {boolean} props.loading - Loading state
 */
export default function DecisionCycleTimeline({ 
  cycle, 
  accountId,
  onStepClick, 
  onActivityClick,
  onAddActivity,
  onRefresh,
  loading = false 
}) {
  const theme = useTheme();
  const router = useRouter();
  
  // Hidden columns state (persisted per cycle)
  const [hiddenColumns, setHiddenColumns] = useState(() => 
    getHiddenColumns(cycle?.id)
  );

  // Link Activity Modal state
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkModalStep, setLinkModalStep] = useState(null);
  
  // Load hidden columns from localStorage when cycle changes
  useEffect(() => {
    if (cycle?.id) {
      const stored = getHiddenColumns(cycle.id);
      setHiddenColumns(stored);
    }
  }, [cycle?.id]);
  
  // Get steps sorted by order
  const steps = useMemo(() => {
    if (!cycle?.steps) return [];
    return [...cycle.steps].sort((a, b) => (a.order || 0) - (b.order || 0));
  }, [cycle?.steps]);
  
  // Group activities by step
  const activitiesByStep = useMemo(() => {
    const grouped = {};
    steps.forEach(step => {
      grouped[step.id] = step.activities || [];
    });
    return grouped;
  }, [steps]);
  
  // Derive cycle closed state from explicit outcome (two-layer architecture)
  const cycleOutcome = cycle?.outcome || null;
  const isCycleClosed = ['WON', 'LOST', 'NOT_QUALIFIED'].includes(cycleOutcome);
  const isCyclePaused = cycleOutcome === 'ON_HOLD';

  // Override step statuses based on cycle outcome:
  // WON → all STALLED become VALIDATED (deal completed, everything is past)
  // LOST / NOT_QUALIFIED / ON_HOLD → only the last step with activities gets overridden,
  //   all other steps keep their natural derived status from backend
  const effectiveSteps = useMemo(() => {
    if (!isCycleClosed && !isCyclePaused) return steps;

    // WON: all STALLED → VALIDATED
    if (cycleOutcome === 'WON') {
      return steps.map(s =>
        s.derived_status === 'STALLED' ? { ...s, derived_status: 'VALIDATED' } : s
      );
    }

    // LOST / NOT_QUALIFIED / ON_HOLD: highlight only the last active step
    const OUTCOME_TO_STATUS = {
      LOST: 'CYCLE_LOST',
      NOT_QUALIFIED: 'CYCLE_NOT_QUALIFIED',
      ON_HOLD: 'CYCLE_ON_HOLD'
    };
    const overrideStatus = OUTCOME_TO_STATUS[cycleOutcome];
    if (!overrideStatus) return steps;

     // Find last step (highest order) that has visible (non-cancelled) activities
    let lastActiveIndex = -1;
    steps.forEach((s, i) => {
      const visibleCount = (s.activities || []).filter(a => a.status !== 'CANCELLED').length;
      if (visibleCount > 0) {
        lastActiveIndex = i;
      }
    });

    if (lastActiveIndex === -1) return steps;

    return steps.map((s, i) => {
      if (i === lastActiveIndex) return { ...s, derived_status: overrideStatus };
      return s; // keep natural derived status from backend
    });
  }, [steps, isCycleClosed, isCyclePaused, cycleOutcome]);

  // Visible steps (filtered by hidden)
  const visibleSteps = useMemo(() => {
    return effectiveSteps.filter(s => !hiddenColumns.includes(s.id));
  }, [effectiveSteps, hiddenColumns]);

 // Calculate pipeline progress (based on visible/selected steps only)
  const pipelineProgress = useMemo(() => {
    if (!visibleSteps.length) return { validated: 0, total: 0, percent: 0 };
    const validated = visibleSteps.filter(s => s.derived_status === 'VALIDATED').length;
    return {
      validated,
      total: visibleSteps.length,
      percent: Math.round((validated / visibleSteps.length) * 100)
    };
  }, [visibleSteps]);

  // Expected closing date = furthest end date among visible steps
  // Same priority as step columns: completed_at > effective_end_date > expected_end
  const expectedClosingDate = useMemo(() => {
    let furthest = null;
    visibleSteps.forEach(s => {
      const endDate = s.completed_at || s.effective_end_date || s.expected_end;
      if (endDate) {
        if (!furthest || new Date(endDate) > new Date(furthest)) {
          furthest = endDate;
        }
      }
    });
    return furthest;
  }, [visibleSteps]);

  // Cycle close/reopen (shared hook)
  const closeReopen = useCycleCloseReopen({ cycle, onRefresh });
  
  // Toggle column visibility
  // Rule: cannot hide a step that has visible (non-cancelled) activities
  const handleToggleColumn = useCallback((stepId) => {
    setHiddenColumns(prev => {
      const isCurrentlyHidden = prev.includes(stepId);
      
      // If trying to HIDE (not currently hidden → will become hidden)
      if (!isCurrentlyHidden) {
        const step = steps.find(s => s.id === stepId);
        const visibleActivities = (step?.activities || []).filter(a => a.status !== 'CANCELLED');
        if (visibleActivities.length > 0) {
          return prev; // Block — step has activities
        }
      }
      
      const newHidden = isCurrentlyHidden
        ? prev.filter(id => id !== stepId)
        : [...prev, stepId];
      
      // Save to localStorage
      if (cycle?.id) {
        saveHiddenColumns(cycle.id, newHidden);
      }
      
      return newHidden;
    });
  }, [cycle?.id, steps]);
  
  // Show all columns
  const handleShowAll = useCallback(() => {
    setHiddenColumns([]);
    if (cycle?.id) {
      saveHiddenColumns(cycle.id, []);
    }
  }, [cycle?.id]);
  
  // Hide optional columns (based on step-level flag from backend)
  const handleHideOptional = useCallback(() => {
    const optionalStepIds = steps
      .filter(s => s.is_activity_optional)
      .map(s => s.id);
    
    setHiddenColumns(optionalStepIds);
    if (cycle?.id) {
      saveHiddenColumns(cycle.id, optionalStepIds);
    }
  }, [steps, cycle?.id]);
  
  // Default handlers - use callbacks or fallback to correct routes
  const handleStepClick = (step) => {
    if (onStepClick) {
      onStepClick(step);
    } else if (accountId) {
      router.push(`/accounts/${accountId}/decisionSteps/${step.id}`);
    }
  };
  
  const handleActivityClick = (activity) => {
    if (onActivityClick) {
      onActivityClick(activity);
    } else {
      router.push(`/activities/${activity.id}`);
    }
  };

  // Handle link existing activity
  const handleLinkExisting = useCallback((step) => {
    setLinkModalStep(step);
    setLinkModalOpen(true);
  }, []);
  
  // Handle link modal close
  const handleLinkModalClose = useCallback(() => {
    setLinkModalOpen(false);
    setLinkModalStep(null);
  }, []);
  
  // Handle link success
  const handleLinkSuccess = useCallback((linkedActivities) => {
    // Trigger refresh of cycle data
    onRefresh?.();
  }, [onRefresh]);
  
  const handleAddActivity = (step) => {
    if (onAddActivity) {
      onAddActivity(step);
    }
  };

  if (!cycle) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">No cycle selected</Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Pipeline Header — single line */}
      <Stack direction="row" alignItems="center" spacing={2} sx={{ mb: 2 }}>
        {/* Status chip */}
        <Chip 
          label={CYCLE_DERIVED_STATUS_LABELS[cycleOutcome || cycle.cycle_status] || cycle.cycle_status || 'Active'}
          size="small"
          color={CYCLE_STATUS_COLORS[cycleOutcome || cycle.cycle_status] || 'default'}
          variant="filled"
          icon={cycleOutcome === 'WON' ? <CheckCircleFilled /> : 
                cycleOutcome === 'ON_HOLD' ? <PauseCircleOutlined /> : 
                cycleOutcome ? <CloseCircleFilled /> : undefined}
        />

        {/* Start date (first activity) */}
        <Typography variant="caption" color="text.secondary" noWrap>
          {cycle.created_at
            ? new Date(cycle.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
            : '—'
          }
        </Typography>

        {/* Progress bar: validated steps / visible steps */}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ minWidth: 140 }}>
          <Box sx={{ flex: 1, height: 6, borderRadius: 3, bgcolor: 'grey.200', overflow: 'hidden' }}>
            <Box
              sx={{
                height: '100%',
                width: `${pipelineProgress.percent}%`,
                bgcolor: pipelineProgress.percent === 100 ? 'success.main' : 'primary.main',
                borderRadius: 3,
                transition: 'width 0.3s ease'
              }}
            />
          </Box>
          <Typography variant="caption" color="text.secondary" noWrap>
            {pipelineProgress.validated}/{pipelineProgress.total}
          </Typography>
        </Stack>

        {/* End date — outcome-aware display
         * ON_HOLD  → hold_until in warning (or error if past)
         * WON      → outcome_date in success
         * LOST/NQ  → outcome_date in error
         * Open     → expectedClosingDate in italic (overdue if past)
         */}
        {(cycle.outcome_date || cycle.hold_until || expectedClosingDate) ? (
          <Stack direction="row" spacing={0.5} alignItems="center">
            {isCyclePaused ? (() => {
              // ON_HOLD: show hold_until date + outcome_notes tooltip
              const holdDate = cycle.hold_until;
              const isHoldOverdue = holdDate && new Date(holdDate) < new Date(new Date().toDateString());
              const holdColor = isHoldOverdue ? theme.palette.error.main : theme.palette.warning.main;
              return (
                <Tooltip title={cycle.outcome_notes || 'On Hold'} arrow>
                  <Stack direction="row" spacing={0.5} alignItems="center">
                    <PauseCircleOutlined style={{ fontSize: 12, color: holdColor }} />
                    <Typography variant="caption" noWrap sx={{ color: holdColor, fontWeight: 500 }}>
                      On untill {holdDate
                        ? new Date(holdDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })
                        : '—'
                      }
                    </Typography>
                  </Stack>
                </Tooltip>
              );
            })() : cycle.outcome_date ? (
              <>
                {cycleOutcome === 'WON' ? (
                  <CheckCircleFilled style={{ fontSize: 12, color: theme.palette.success.main }} />
                ) : (
                  <CloseCircleFilled style={{ fontSize: 12, color: theme.palette.error.main }} />
                )}
                <Typography
                  variant="caption"
                  noWrap
                  sx={{
                    color: cycleOutcome === 'WON' ? 'success.main' : 'error.main',
                    fontWeight: 500
                  }}
                >
                  {new Date(cycle.outcome_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  {cycle.closed_by_name ? ` by ${cycle.closed_by_name}` : ''}
                </Typography>
              </>
            ) : (() => {
              const isOverdue = new Date(expectedClosingDate) < new Date();
              return (
                <>
                  <ClockCircleOutlined style={{ fontSize: 12, color: isOverdue ? theme.palette.error.main : theme.palette.text.disabled }} />
                  <Typography
                    variant="caption"
                    noWrap
                    sx={{
                      color: isOverdue ? 'error.main' : 'text.secondary',
                      fontStyle: 'italic',
                      fontWeight: isOverdue ? 500 : 400
                    }}
                  >
                    ({new Date(expectedClosingDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: '2-digit' })})
                  </Typography>
                </>
              );
            })()}
          </Stack>
        ) : (
          <Typography variant="caption" color="text.disabled">—</Typography>
        )}

        {/* Disabled steps indicator */}
        <HiddenColumnsIndicator 
          steps={steps}
          hiddenColumns={hiddenColumns}
          onToggleColumn={handleToggleColumn}
        />

        {/* Spacer */}
        <Box sx={{ flex: 1 }} />

        {/* Close / Reopen cycle action */}
        {(isCycleClosed || isCyclePaused) ? (
          <Button
            size="small"
            variant="outlined"
            onClick={closeReopen.handleReopenCycle}
            disabled={closeReopen.reopenLoading}
          >
            {closeReopen.reopenLoading ? 'Reopening...' : 'Reopen Cycle'}
          </Button>
        ) : (
          <Button
            size="small"
            variant="outlined"
            color="warning"
            onClick={() => closeReopen.setCloseDialogOpen(true)}
          >
            Close Cycle
          </Button>
        )}
        
        {/* Pipeline steps settings */}
        <ColumnVisibilityMenu
          steps={steps}
          hiddenColumns={hiddenColumns}
          onToggleColumn={handleToggleColumn}
          onShowAll={handleShowAll}
        />
      </Stack>
      
      {/* Cycle-Level Risk/Stalled Alert — hidden when cycle is closed or paused */}
      {!isCycleClosed && !isCyclePaused && (cycle?.is_at_risk || cycle?.stalled_steps_count > 0) && (
        <Alert 
          severity={cycle?.is_at_risk ? 'error' : 'warning'}
          variant="outlined"
          sx={{ mb: 2 }}
        >
          <AlertTitle>
            {cycle?.is_at_risk ? 'Cycle at risk' : 'Attention needed'}
          </AlertTitle>
          {cycle?.stalled_steps_count > 0 && (
            <Typography variant="body2">
              {cycle.stalled_steps_count} step{cycle.stalled_steps_count > 1 ? 's' : ''} stalled — 
              click on the step header to take action.
            </Typography>
          )}
          {cycle?.is_at_risk && cycle?.stalled_steps_count === 0 && (
            <Typography variant="body2">
              This cycle is at risk. Review step statuses and plan next actions.
            </Typography>
          )}
        </Alert>
      )}
      
      {/* Pipeline Columns */}
     <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          gap: 2,
          overflowX: 'auto',
          pb: 2,
          '&::-webkit-scrollbar': {
            height: 8
          },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: 'grey.300',
            borderRadius: 4
          }
        }}
      >
        {visibleSteps.map((step) => (
            <PipelineStepColumn
              key={step.id}
              step={step}
              activities={activitiesByStep[step.id] || []}
              onStepClick={handleStepClick}
              onActivityClick={handleActivityClick}
              onAddActivity={onAddActivity}
              onLinkExisting={handleLinkExisting}
              isCycleClosed={isCycleClosed}
            />
          ))}
        
        {/* Empty state when all columns hidden */}
        {visibleSteps.length === 0 && steps.length > 0 && (
          <Box 
            sx={{ 
              flex: 1, 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              p: 4,
              bgcolor: 'grey.50',
              borderRadius: 2,
              border: '1px dashed',
              borderColor: 'divider'
            }}
          >
            <Stack alignItems="center" spacing={1}>
              <EyeInvisibleOutlined style={{ fontSize: 32, color: 'grey' }} />
              <Typography color="text.secondary">All columns are hidden</Typography>
              <Button size="small" onClick={handleShowAll}>
                Show All Columns
              </Button>
            </Stack>
          </Box>
        )}
      </Box>
      {/* Link Activity Modal */}
      <LinkActivityModal
        open={linkModalOpen}
        onClose={handleLinkModalClose}
        accountId={accountId}
        cycleId={cycle?.id}
        step={linkModalStep}
        onSuccess={handleLinkSuccess}
      />

      {/* Close Cycle Dialog */}
      <CycleCloseDialog
        open={closeReopen.closeDialogOpen}
        onClose={closeReopen.handleCloseDialogDismiss}
        formik={closeReopen.closeFormik}
      />
    </Box>
  );
}

DecisionCycleTimeline.propTypes = {
  cycle: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    steps: PropTypes.array,
    expected_closing_date: PropTypes.string
  }),
  accountId: PropTypes.string,
  onStepClick: PropTypes.func,
  onActivityClick: PropTypes.func,
  onAddActivity: PropTypes.func,
  onRefresh: PropTypes.func,
  loading: PropTypes.bool
};