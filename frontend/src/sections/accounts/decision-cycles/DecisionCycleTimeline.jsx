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
import MenuItem from '@mui/material/MenuItem';
import Checkbox from '@mui/material/Checkbox';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import Divider from '@mui/material/Divider';
import Badge from '@mui/material/Badge';

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
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import SettingOutlined from '@ant-design/icons/SettingOutlined';
import EyeOutlined from '@ant-design/icons/EyeOutlined';
import EyeInvisibleOutlined from '@ant-design/icons/EyeInvisibleOutlined';

// project imports
import { 
  PIPELINE_STEPS_ORDER, 
  PIPELINE_STEP_LABELS, 
  PIPELINE_STEP_CONFIG,
  STATUS_COLORS,
  STATUS_LABELS,
  ACTIVITY_OPTIONAL_STEPS
} from 'api/accounts/decisionCycles';

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

const STATUS_CONFIG = {
  NOT_STARTED: {
    color: 'default',
    bgColor: 'grey.200',
    icon: MinusCircleOutlined,
    label: 'Not Started'
  },
  PENDING_CLIENT: {
    color: 'warning',
    bgColor: 'warning.lighter',
    icon: PauseCircleOutlined,
    label: 'Pending Client'
  },
  IN_PROGRESS: {
    color: 'info',
    bgColor: 'info.lighter',
    icon: SyncOutlined,
    label: 'In Progress'
  },
  IN_CHASING: {
    color: 'secondary',
    bgColor: 'secondary.lighter',
    icon: ClockCircleOutlined,
    label: 'In Chasing'
  },
  VALIDATED: {
    color: 'success',
    bgColor: 'success.lighter',
    icon: CheckCircleFilled,
    label: 'Validated'
  },
  REJECTED: {
    color: 'error',
    bgColor: 'error.lighter',
    icon: CloseCircleFilled,
    label: 'Rejected'
  },
  ON_HOLD: {
    color: 'warning',
    bgColor: 'warning.lighter',
    icon: PauseCircleOutlined,
    label: 'On Hold'
  },
  CANCELLED: {
    color: 'default',
    bgColor: 'grey.200',
    icon: CloseCircleFilled,
    label: 'Cancelled'
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
 * Activity Card Component
 * 
 * Lightweight card for displaying an activity within a pipeline step.
 */
function ActivityCard({ activity, onClick }) {
  const theme = useTheme();
  
  const TypeIcon = ACTIVITY_TYPE_ICONS[activity.activity_type] || CalendarOutlined;
  const isCompleted = activity.status === 'COMPLETED';
  const isPast = activity.scheduled_date && new Date(activity.scheduled_date) < new Date();
  
  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    const date = new Date(dateStr);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    
    if (date.toDateString() === today.toDateString()) return 'Today';
    if (date.toDateString() === tomorrow.toDateString()) return 'Tomorrow';
    
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <Paper
      elevation={0}
      onClick={() => onClick?.(activity)}
      sx={{
        p: 1.5,
        cursor: 'pointer',
        border: '1px solid',
        borderColor: isCompleted ? 'success.light' : 'divider',
        borderRadius: 1.5,
        bgcolor: isCompleted ? alpha(theme.palette.success.main, 0.04) : 'background.paper',
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
        {/* Header: Type icon + Title */}
        <Stack direction="row" alignItems="center" spacing={1}>
          <TypeIcon style={{ fontSize: 14, color: theme.palette.text.secondary }} />
          <Typography 
            variant="body2" 
            fontWeight={500}
            noWrap
            sx={{ 
              flex: 1,
              textDecoration: isCompleted ? 'line-through' : 'none',
              color: isCompleted ? 'text.secondary' : 'text.primary'
            }}
          >
            {activity.subject || activity.activity_type_display || 'Activity'}
          </Typography>
        </Stack>
        
        {/* Date + Status */}
        <Stack direction="row" alignItems="center" justifyContent="space-between">
          {activity.scheduled_date && (
            <Typography 
              variant="caption" 
              color={isPast && !isCompleted ? 'error.main' : 'text.secondary'}
            >
              {formatDate(activity.scheduled_date)}
              {activity.scheduled_time && ` ${activity.scheduled_time.slice(0, 5)}`}
            </Typography>
          )}
          {activity.outcome && (
            <Chip
              label={activity.outcome_display || activity.outcome}
              size="small"
              color={activity.outcome === 'POSITIVE' ? 'success' : activity.outcome === 'NEGATIVE' ? 'error' : 'default'}
              sx={{ height: 18, fontSize: '0.65rem' }}
            />
          )}
        </Stack>
        
        {/* Contacts preview */}
        {activity.contacts_count > 0 && (
          <Typography variant="caption" color="text.secondary">
            {activity.contacts_count} contact{activity.contacts_count > 1 ? 's' : ''}
          </Typography>
        )}
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
  onAddActivity
}) {
  const theme = useTheme();
  
  if (!step) return null;
  
  const statusConfig = STATUS_CONFIG[step.status] || STATUS_CONFIG.NOT_STARTED;
  const StatusIcon = statusConfig.icon;
  const stepConfig = PIPELINE_STEP_CONFIG[step.stage] || {};
  const isActivityOptional = stepConfig.activity_optional || step.is_activity_optional || false;
  
  // Determine column state
  const isValidated = step.status === 'VALIDATED';
  const isRejected = step.status === 'REJECTED';
  const isStalled = step.is_stalled && !isActivityOptional;
  const hasActivities = activities && activities.length > 0;
  
  // Column border color
  const getBorderColor = () => {
    if (isStalled) return theme.palette.warning.main;
    if (isValidated) return theme.palette.success.main;
    if (isRejected) return theme.palette.error.main;
    if (step.status === 'IN_PROGRESS') return theme.palette.info.main;
    return theme.palette.divider;
  };

  return (
    <Paper
      elevation={0}
      sx={{
        flex: '0 0 220px',
        minWidth: 220,
        maxWidth: 260,
        bgcolor: 'background.default',
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
          bgcolor: isValidated ? 'success.lighter' : isRejected ? 'error.lighter' : 'grey.50',
          borderBottom: '1px solid',
          borderColor: 'divider',
          cursor: 'pointer',
          '&:hover': {
            bgcolor: isValidated ? 'success.light' : isRejected ? 'error.light' : 'grey.100'
          }
        }}
      >
        <Stack spacing={0.5}>
          {/* Step name + Status icon */}
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle2" fontWeight={600} noWrap sx={{ flex: 1 }}>
              {step.name}
            </Typography>
            <Tooltip title={statusConfig.label}>
              <StatusIcon style={{ 
                fontSize: 16, 
                color: theme.palette[statusConfig.color]?.main || theme.palette.grey[500]
              }} />
            </Tooltip>
          </Stack>
          
          {/* Step description */}
          <Typography variant="caption" color="text.secondary" sx={{ lineHeight: 1.3 }}>
            {step.step_description || stepConfig.description || ''}
          </Typography>
          
          {/* Expected end + Stalled warning */}
          <Stack direction="row" alignItems="center" spacing={1}>
            {step.expected_end && (
              <Typography variant="caption" color="text.secondary">
                Due: {new Date(step.expected_end).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </Typography>
            )}
            {isStalled && (
              <Tooltip title={step.stalled_reason || 'Step is stalled'}>
                <WarningOutlined style={{ fontSize: 14, color: theme.palette.warning.main }} />
              </Tooltip>
            )}
          </Stack>
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
          activities.map((activity) => (
            <ActivityCard
              key={activity.id}
              activity={activity}
              onClick={onActivityClick}
            />
          ))
        )}
      </Box>
      
      {/* Add Activity Button */}
      <Box sx={{ p: 1, borderTop: '1px solid', borderColor: 'divider' }}>
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
      </Box>
    </Paper>
  );
}

PipelineStepColumn.propTypes = {
  step: PropTypes.object,
  activities: PropTypes.array,
  onStepClick: PropTypes.func,
  onActivityClick: PropTypes.func,
  onAddActivity: PropTypes.func
};

// ==============================|| COLUMN VISIBILITY MENU ||============================== //

/**
 * Column Visibility Menu
 * 
 * Allows users to show/hide pipeline columns.
 */
function ColumnVisibilityMenu({ steps, hiddenColumns, onToggleColumn, onShowAll, onHideOptional }) {
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
      <Tooltip title="Configure visible columns">
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
            Visible Columns
          </Typography>
        </Box>
        
        <Divider />
        
        {steps.map((step) => {
          const isHidden = hiddenColumns.includes(step.id);
          const stepConfig = PIPELINE_STEP_CONFIG[step.stage] || {};
          
          return (
            <MenuItem 
              key={step.id} 
              onClick={() => handleToggle(step.id)}
              dense
            >
              <ListItemIcon>
                <Checkbox
                  checked={!isHidden}
                  size="small"
                  sx={{ p: 0 }}
                />
              </ListItemIcon>
              <ListItemText 
                primary={step.name}
                secondary={stepConfig.activity_optional ? 'Optional' : null}
                primaryTypographyProps={{ variant: 'body2' }}
                secondaryTypographyProps={{ variant: 'caption' }}
              />
              {isHidden ? (
                <EyeInvisibleOutlined style={{ fontSize: 14, color: 'grey' }} />
              ) : (
                <EyeOutlined style={{ fontSize: 14 }} />
              )}
            </MenuItem>
          );
        })}
        
        <Divider sx={{ my: 1 }} />
        
        <Box sx={{ px: 1, pb: 1 }}>
          <Stack direction="row" spacing={1}>
            <Button 
              size="small" 
              onClick={() => { onShowAll(); handleClose(); }}
              disabled={hiddenCount === 0}
              fullWidth
            >
              Show All
            </Button>
            <Button 
              size="small" 
              onClick={() => { onHideOptional(); handleClose(); }}
              fullWidth
              color="secondary"
            >
              Hide Optional
            </Button>
          </Stack>
        </Box>
      </Menu>
    </>
  );
}

ColumnVisibilityMenu.propTypes = {
  steps: PropTypes.array.isRequired,
  hiddenColumns: PropTypes.array.isRequired,
  onToggleColumn: PropTypes.func.isRequired,
  onShowAll: PropTypes.func.isRequired,
  onHideOptional: PropTypes.func.isRequired
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
        Hidden:
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
  onStepClick, 
  onActivityClick,
  onAddActivity,
  loading = false 
}) {
  const theme = useTheme();
  const router = useRouter();
  
  // Hidden columns state (persisted per cycle)
  const [hiddenColumns, setHiddenColumns] = useState([]);
  
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
  
  // Visible steps (filtered by hidden)
  const visibleSteps = useMemo(() => {
    return steps.filter(s => !hiddenColumns.includes(s.id));
  }, [steps, hiddenColumns]);
  
  // Group activities by step
  const activitiesByStep = useMemo(() => {
    const grouped = {};
    steps.forEach(step => {
      grouped[step.id] = step.activities || [];
    });
    return grouped;
  }, [steps]);
  
  // Calculate pipeline progress
  const pipelineProgress = useMemo(() => {
    if (!steps.length) return { validated: 0, total: 0, percent: 0 };
    const validated = steps.filter(s => s.status === 'VALIDATED').length;
    return {
      validated,
      total: steps.length,
      percent: Math.round((validated / steps.length) * 100)
    };
  }, [steps]);
  
  // Toggle column visibility
  const handleToggleColumn = useCallback((stepId) => {
    setHiddenColumns(prev => {
      const newHidden = prev.includes(stepId)
        ? prev.filter(id => id !== stepId)
        : [...prev, stepId];
      
      // Save to localStorage
      if (cycle?.id) {
        saveHiddenColumns(cycle.id, newHidden);
      }
      
      return newHidden;
    });
  }, [cycle?.id]);
  
  // Show all columns
  const handleShowAll = useCallback(() => {
    setHiddenColumns([]);
    if (cycle?.id) {
      saveHiddenColumns(cycle.id, []);
    }
  }, [cycle?.id]);
  
  // Hide optional columns (Implementation, Go Live)
  const handleHideOptional = useCallback(() => {
    const optionalStepIds = steps
      .filter(s => ACTIVITY_OPTIONAL_STEPS.includes(s.stage) || s.is_activity_optional)
      .map(s => s.id);
    
    setHiddenColumns(optionalStepIds);
    if (cycle?.id) {
      saveHiddenColumns(cycle.id, optionalStepIds);
    }
  }, [steps, cycle?.id]);
  
  // Default handlers
  const handleStepClick = (step) => {
    if (onStepClick) {
      onStepClick(step);
    } else {
      router.push(`/decision-steps/${step.id}`);
    }
  };
  
  const handleActivityClick = (activity) => {
    if (onActivityClick) {
      onActivityClick(activity);
    } else {
      router.push(`/activities/${activity.id}`);
    }
  };
  
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
      {/* Pipeline Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Stack direction="row" alignItems="center" spacing={2}>
          <Typography variant="h6">{cycle.name}</Typography>
          <Chip 
            label={`${pipelineProgress.validated}/${pipelineProgress.total} validated`}
            size="small"
            color={pipelineProgress.percent === 100 ? 'success' : 'default'}
          />
          
          {/* Hidden columns indicator */}
          <HiddenColumnsIndicator 
            steps={steps}
            hiddenColumns={hiddenColumns}
            onToggleColumn={handleToggleColumn}
          />
        </Stack>
        
        <Stack direction="row" alignItems="center" spacing={2}>
          {cycle.expected_closing_date && (
            <Typography variant="body2" color="text.secondary">
              Expected close: {new Date(cycle.expected_closing_date).toLocaleDateString()}
            </Typography>
          )}
          
          {/* Column visibility settings */}
          <ColumnVisibilityMenu
            steps={steps}
            hiddenColumns={hiddenColumns}
            onToggleColumn={handleToggleColumn}
            onShowAll={handleShowAll}
            onHideOptional={handleHideOptional}
          />
        </Stack>
      </Stack>
      
      {/* Pipeline Columns */}
      <Box
        sx={{
          display: 'flex',
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
            onAddActivity={handleAddActivity}
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
  onStepClick: PropTypes.func,
  onActivityClick: PropTypes.func,
  onAddActivity: PropTypes.func,
  loading: PropTypes.bool
};