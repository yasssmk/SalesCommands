// frontend/src/sections/accounts/decision-cycles/DecisionStepActivitiesTab.jsx

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';

// MUI
import { useTheme } from '@mui/material/styles';
import { alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';

// Icons
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import RightOutlined from '@ant-design/icons/RightOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import LinkedinOutlined from '@ant-design/icons/LinkedinOutlined';
import QuestionCircleOutlined from '@ant-design/icons/QuestionCircleOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';

// Project imports
import ActivityModal from 'sections/accounts/activities/ActivityModal';
import ActivityCompleteModal from 'sections/accounts/activities/ActivityCompleteModal';
import AlertActivityCancel from '../activities/AlertActivityCancel';
import { 
  useGetActivitiesByStep,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS
} from 'api/accounts/activities';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';
import { formatDateOnly } from 'config/formatters';

// ==============================|| TYPE ICONS ||============================== //

const TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined
};

// ==============================|| ACTIVITY ROW (with navigation) ||============================== //

function ActivityRow({ activity, onNavigate, onComplete, onCancel }) {
  const theme = useTheme();

  const TypeIcon = TYPE_ICONS[activity.activity_type] || QuestionCircleOutlined;
  const isCompleted = activity.status === 'COMPLETED';
  const isCancelled = activity.status === 'CANCELLED';
  const canComplete = !isCompleted && !isCancelled;
  
  return (
    <Box
      onClick={() => onNavigate(activity)}
      sx={{
        p: 2,
        borderRadius: 1,
        bgcolor: (theme) => alpha(theme.palette.primary.main, 0.02),
        border: '1px solid',
        borderColor: 'divider',
        cursor: 'pointer',
        transition: 'all 0.2s',
        '&:hover': {
          bgcolor: (theme) => alpha(theme.palette.primary.main, 0.06),
          borderColor: 'primary.light',
          transform: 'translateX(4px)'
        }
      }}
    >
      <Stack direction="row" alignItems="center" spacing={2}>
        {/* Type Icon */}
        <Tooltip title={ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type}>
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: 'action.hover'
            }}
          >
            <TypeIcon style={{ fontSize: theme.iconSizes.lg}} />
          </Box>
        </Tooltip>
        
        {/* Title & Info */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography 
            variant="body1" 
            fontWeight={500} 
            noWrap
            sx={{
              textDecoration: isCancelled ? 'line-through' : 'none',
              color: isCancelled ? 'text.disabled' : 'text.primary'
            }}
          >
            {activity.title}
          </Typography>
          <Stack direction="row" alignItems="center" spacing={2} sx={{ mt: 0.5 }}>
            <Typography variant="caption" color="text.secondary">
              {ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type}
            </Typography>
            {activity.scheduled_date && (
              <Stack direction="row" alignItems="center" spacing={0.5}>
                <CalendarOutlined style={{ fontSize: theme.iconSizes.xs , opacity: 0.6 }} />
                <Typography variant="caption" color="text.secondary">
                  {formatDateOnly(activity.scheduled_date)}
                </Typography>
              </Stack>
            )}
            {activity.owner_detail?.full_name && (
              <Typography variant="caption" color="text.secondary">
                {activity.owner_detail.full_name}
              </Typography>
            )}
          </Stack>
        </Box>
        
        {/* Status Chip */}
        <Chip
          label={ACTIVITY_STATUS_LABELS[activity.status] || activity.status}
          color={ACTIVITY_STATUS_COLORS[activity.status] || 'default'}
          size="small"
          sx={{ minWidth: 80 }}
        />
        
        {/* Quick Actions */}
        <Stack direction="row" spacing={0.5} onClick={(e) => e.stopPropagation()}>
          {canComplete && (
            <Tooltip title="Mark Complete">
              <IconButton size="small" color="success" onClick={() => onComplete(activity)}>
                <CheckCircleOutlined style={{ fontSize: theme.iconSizes.md  }} />
              </IconButton>
            </Tooltip>
          )}
          {canComplete && (
            <Tooltip title="Cancel">
              <IconButton size="small" color="warning" onClick={() => onCancel(activity)}>
                <CloseCircleOutlined style={{ fontSize: theme.iconSizes.md  }} />
              </IconButton>
            </Tooltip>
          )}
        </Stack>
        
        {/* Navigate arrow */}
        <RightOutlined style={{ fontSize: theme.iconSizes.sm, opacity: 0.4 }} />
      </Stack>
    </Box>
  );
}

ActivityRow.propTypes = {
  activity: PropTypes.object.isRequired,
  onNavigate: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired
};

// ==============================|| DECISION STEP ACTIVITIES TAB ||============================== //

/**
 * Decision Step Activities Tab
 * 
 * Displays activities linked to a decision step with:
 * - Click to navigate to activity workspace
 * - Quick complete/cancel actions
 * - Create new activity button
 * 
 * @param {object} step - Decision Step data
 * @param {string} accountId - Account UUID
 * @param {function} onUpdate - Callback to refresh step data
 */
export default function DecisionStepActivitiesTab({ step, accountId, onUpdate }) {
  const router = useRouter();
  
  // Modal states
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [activityToComplete, setActivityToComplete] = useState(null);
  const [cancelModalOpen, setCancelModalOpen] = useState(false);
  const [activityToCancel, setActivityToCancel] = useState(null);
  
  // Fetch activities
  const {
    activities,
    activitiesLoading,
    activitiesEmpty,
    mutateActivities
  } = useGetActivitiesByStep(step?.id);
  
  // ==============================|| HANDLERS ||============================== //
  
  // Navigate to activity workspace
  const handleNavigate = useCallback((activity) => {
    router.push(`/activities/${activity.id}`);
  }, [router]);
  
  // Open create modal
  const handleAdd = useCallback(() => {
    setActivityModalOpen(true);
  }, []);
  
  // Complete activity
  const handleComplete = useCallback((activity) => {
    setActivityToComplete(activity);
    setCompleteModalOpen(true);
  }, []);
  
// Cancel activity (open modal)
  const handleCancel = useCallback((activity) => {
    setActivityToCancel(activity);
    setCancelModalOpen(true);
  }, []);
  
  const handleCancelModalClose = useCallback(() => {
    setCancelModalOpen(false);
    setActivityToCancel(null);
  }, []);
  
  const handleCancelSuccess = useCallback(() => {
    setCancelModalOpen(false);
    setActivityToCancel(null);
    mutateActivities();
    onUpdate?.();
  }, [mutateActivities, onUpdate]);
  
  // Modal success handlers
  const handleModalSuccess = useCallback(() => {
    setActivityModalOpen(false);
    mutateActivities();
    onUpdate?.();
  }, [mutateActivities, onUpdate]);
  
  const handleCompleteSuccess = useCallback(() => {
    setCompleteModalOpen(false);
    setActivityToComplete(null);
    mutateActivities();
    onUpdate?.();
  }, [mutateActivities, onUpdate]);
  
  // ==============================|| RENDER ||============================== //
  
  // Group activities by status
  const pendingActivities = activities.filter(a => 
    !['COMPLETED', 'CANCELLED'].includes(a.status)
  );
  const completedActivities = activities.filter(a => 
    a.status === 'COMPLETED'
  );
  const cancelledActivities = activities.filter(a => 
    a.status === 'CANCELLED'
  );
  
  return (
    <Box>
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={3}>
        <Box>
          <Typography variant="h6">Activities</Typography>
          <Typography variant="body2" color="text.secondary">
            Activities linked to this decision step. Click to open in full workspace.
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<PlusOutlined />}
          onClick={handleAdd}
        >
          Add Activity
        </Button>
      </Stack>
      
      {/* Loading */}
      {activitiesLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </Box>
      )}
      
      {/* Empty state */}
      {!activitiesLoading && activitiesEmpty && (
        <Box
          sx={{
            py: 6,
            textAlign: 'center',
            border: '2px dashed',
            borderColor: 'divider',
            borderRadius: 2
          }}
        >
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No activities yet
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Create activities to track meetings, calls, emails, and tasks for this step.
          </Typography>
          <Button
            variant="outlined"
            startIcon={<PlusOutlined />}
            onClick={handleAdd}
          >
            Create First Activity
          </Button>
        </Box>
      )}
      
      {/* Activities list */}
      {!activitiesLoading && !activitiesEmpty && (
        <Stack spacing={3}>
          {/* Pending/In Progress */}
          {pendingActivities.length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>
                In Progress ({pendingActivities.length})
              </Typography>
              <Stack spacing={1}>
                {pendingActivities.map((activity) => (
                  <ActivityRow
                    key={activity.id}
                    activity={activity}
                    onNavigate={handleNavigate}
                    onComplete={handleComplete}
                    onCancel={handleCancel}
                  />
                ))}
              </Stack>
            </Box>
          )}
          
          {/* Completed */}
          {completedActivities.length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>
                Completed ({completedActivities.length})
              </Typography>
              <Stack spacing={1}>
                {completedActivities.map((activity) => (
                  <ActivityRow
                    key={activity.id}
                    activity={activity}
                    onNavigate={handleNavigate}
                    onComplete={handleComplete}
                    onCancel={handleCancel}
                  />
                ))}
              </Stack>
            </Box>
          )}
          
          {/* Cancelled */}
          {cancelledActivities.length > 0 && (
            <Box>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>
                Cancelled ({cancelledActivities.length})
              </Typography>
              <Stack spacing={1} sx={{ opacity: 0.6 }}>
                {cancelledActivities.map((activity) => (
                  <ActivityRow
                    key={activity.id}
                    activity={activity}
                    onNavigate={handleNavigate}
                    onComplete={handleComplete}
                    onCancel={handleCancel}
                  />
                ))}
              </Stack>
            </Box>
          )}
        </Stack>
      )}
      
      {/* Create Activity Modal */}
      <ActivityModal
        open={activityModalOpen}
        onClose={() => setActivityModalOpen(false)}
        activity={null}
        accountId={accountId}
        decisionStepId={step?.id}
        decisionCycleId={step?.cycle}
        onSuccess={handleModalSuccess}
      />
      
      {/* Complete Activity Modal */}
      {completeModalOpen && activityToComplete && (
        <ActivityCompleteModal
          open={completeModalOpen}
          onClose={() => {
            setCompleteModalOpen(false);
            setActivityToComplete(null);
          }}
          activity={activityToComplete}
          onSuccess={handleCompleteSuccess}
        />
      )}

      {/* Cancel Confirmation */}
      <AlertActivityCancel
        open={cancelModalOpen}
        handleClose={handleCancelModalClose}
        activity={activityToCancel}
        onSuccess={handleCancelSuccess}
      />
    </Box>
  );
}

DecisionStepActivitiesTab.propTypes = {
  step: PropTypes.object.isRequired,
  accountId: PropTypes.string,
  onUpdate: PropTypes.func
};
