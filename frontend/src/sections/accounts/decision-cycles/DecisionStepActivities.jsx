// frontend/src/sections/accounts/decision-cycles/DecisionStepActivities.jsx
/**
 * Decision Step Activities Component
 * 
 * Displays activities linked to a specific decision step.
 * Compact list view with quick actions.
 */

'use client';

import PropTypes from 'prop-types';
import { useState, useCallback } from 'react';

// material-ui
import { alpha } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import IconButton from '@mui/material/IconButton';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// icons
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import DeleteOutlined from '@ant-design/icons/DeleteOutlined';
import PhoneOutlined from '@ant-design/icons/PhoneOutlined';
import MailOutlined from '@ant-design/icons/MailOutlined';
import TeamOutlined from '@ant-design/icons/TeamOutlined';
import CheckSquareOutlined from '@ant-design/icons/CheckSquareOutlined';
import LinkedinOutlined from '@ant-design/icons/LinkedinOutlined';
import QuestionCircleOutlined from '@ant-design/icons/QuestionCircleOutlined';
import CalendarOutlined from '@ant-design/icons/CalendarOutlined';

// project imports
import ActivityModal from '../activities/ActivityModal';
import ActivityCompleteModal from '../activities/ActivityCompleteModal';
import AlertActivityDelete from '../activities/AlertActivityDelete';
import { 
  useGetActivitiesByStep,
  cancelActivity,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS
} from 'api/accounts/activities';
import { formatDateOnly } from 'config/formatters';
import { displayErrorSnackbar, displaySuccessSnackbar } from 'utils/displayError';

// ==============================|| TYPE ICONS ||============================== //

const TYPE_ICONS = {
  CALL: PhoneOutlined,
  EMAIL: MailOutlined,
  MEETING: TeamOutlined,
  TASK: CheckSquareOutlined,
  LINKEDIN: LinkedinOutlined,
  OTHER: QuestionCircleOutlined
};

// ==============================|| ACTIVITY ITEM ||============================== //

function ActivityItem({ activity, onEdit, onDelete, onComplete, onCancel }) {
  const TypeIcon = TYPE_ICONS[activity.activity_type] || QuestionCircleOutlined;
  const isCompleted = activity.status === 'COMPLETED';
  const isCancelled = activity.status === 'CANCELLED';
  const canComplete = !isCompleted && !isCancelled;
  
  return (
    <Box
      sx={{
        p: 1.5,
        borderRadius: 1,
        bgcolor: (theme) => alpha(theme.palette.primary.main, 0.02),
        border: '1px solid',
        borderColor: 'divider',
        '&:hover': {
          bgcolor: (theme) => alpha(theme.palette.primary.main, 0.05),
          borderColor: 'primary.light'
        }
      }}
    >
      <Stack direction="row" alignItems="center" spacing={1.5}>
        {/* Type Icon */}
        <Tooltip title={ACTIVITY_TYPE_LABELS[activity.activity_type] || activity.activity_type}>
          <Box
            sx={{
              width: 28,
              height: 28,
              borderRadius: 0.5,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              bgcolor: 'action.hover'
            }}
          >
            <TypeIcon style={{ fontSize: 14 }} />
          </Box>
        </Tooltip>
        
        {/* Title & Date */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography 
            variant="body2" 
            fontWeight={500} 
            noWrap
            sx={{
              textDecoration: isCancelled ? 'line-through' : 'none',
              color: isCancelled ? 'text.disabled' : 'text.primary'
            }}
          >
            {activity.title}
          </Typography>
          {activity.scheduled_date && (
            <Stack direction="row" alignItems="center" spacing={0.5}>
              <CalendarOutlined style={{ fontSize: 10, opacity: 0.6 }} />
              <Typography variant="caption" color="text.secondary">
                {formatDateOnly(activity.scheduled_date)}
              </Typography>
            </Stack>
          )}
        </Box>
        
        {/* Status Chip */}
        <Chip
          label={ACTIVITY_STATUS_LABELS[activity.status] || activity.status}
          color={ACTIVITY_STATUS_COLORS[activity.status] || 'default'}
          size="small"
          variant="light"
          sx={{ minWidth: 70 }}
        />
        
        {/* Actions */}
        <Stack direction="row" spacing={0}>
          {canComplete && (
            <Tooltip title="Complete">
              <IconButton size="small" color="success" onClick={() => onComplete(activity)}>
                <CheckCircleOutlined style={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          )}
          {canComplete && (
            <Tooltip title="Cancel">
              <IconButton size="small" color="warning" onClick={() => onCancel(activity)}>
                <CloseCircleOutlined style={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
          )}
          <Tooltip title="Edit">
            <IconButton size="small" color="secondary" onClick={() => onEdit(activity)}>
              <EditOutlined style={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" color="secondary" onClick={() => onDelete(activity)}>
              <DeleteOutlined style={{ fontSize: 14 }} />
            </IconButton>
          </Tooltip>
        </Stack>
      </Stack>
    </Box>
  );
}

ActivityItem.propTypes = {
  activity: PropTypes.object.isRequired,
  onEdit: PropTypes.func.isRequired,
  onDelete: PropTypes.func.isRequired,
  onComplete: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired
};

// ==============================|| DECISION STEP ACTIVITIES ||============================== //

/**
 * DecisionStepActivities Component
 * 
 * @param {string} stepId - Decision Step UUID
 * @param {string} accountId - Account UUID (for creating new activities)
 * @param {string} cycleId - Decision Cycle UUID (for creating new activities)
 */
export default function DecisionStepActivities({ stepId, accountId, cycleId }) {
  
  // ==============================|| STATE ||============================== //
  
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityToEdit, setActivityToEdit] = useState(null);
  
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [activityToComplete, setActivityToComplete] = useState(null);
  
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [activityToDelete, setActivityToDelete] = useState(null);
  
  // ==============================|| DATA FETCHING ||============================== //
  
  const {
    activities,
    activitiesLoading,
    activitiesEmpty,
    mutateActivities
  } = useGetActivitiesByStep(stepId);
  
  // ==============================|| HANDLERS ||============================== //
  
  const handleAdd = useCallback(() => {
    setActivityToEdit(null);
    setActivityModalOpen(true);
  }, []);
  
  const handleEdit = useCallback((activity) => {
    setActivityToEdit(activity);
    setActivityModalOpen(true);
  }, []);
  
  const handleDelete = useCallback((activity) => {
    setActivityToDelete(activity);
    setDeleteModalOpen(true);
  }, []);
  
  const handleComplete = useCallback((activity) => {
    setActivityToComplete(activity);
    setCompleteModalOpen(true);
  }, []);
  
  const handleCancel = useCallback(async (activity) => {
    try {
      const result = await cancelActivity(activity.id);
      if (result.success) {
        displaySuccessSnackbar('Activity cancelled');
        mutateActivities();
      } else {
        displayErrorSnackbar(result.error || 'Failed to cancel activity');
      }
    } catch (error) {
      displayErrorSnackbar(error.message || 'An error occurred');
    }
  }, [mutateActivities]);
  
  const handleModalClose = useCallback(() => {
    setActivityModalOpen(false);
    setActivityToEdit(null);
  }, []);
  
  const handleCompleteClose = useCallback(() => {
    setCompleteModalOpen(false);
    setActivityToComplete(null);
  }, []);
  
  const handleDeleteClose = useCallback(() => {
    setDeleteModalOpen(false);
    setActivityToDelete(null);
  }, []);
  
  const handleSuccess = useCallback(() => {
    mutateActivities();
  }, [mutateActivities]);
  
  // ==============================|| RENDER ||============================== //
  
  return (
    <Box>
      {/* Header */}
      <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1.5}>
        <Typography variant="subtitle2" color="text.secondary">
          Activities ({activities.length})
        </Typography>
        <Button
          size="small"
          startIcon={<PlusOutlined />}
          onClick={handleAdd}
        >
          Add
        </Button>
      </Stack>
      
      {/* Content */}
      {activitiesLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress size={24} />
        </Box>
      ) : activitiesEmpty ? (
        <Box
          sx={{
            py: 3,
            textAlign: 'center',
            border: '1px dashed',
            borderColor: 'divider',
            borderRadius: 1
          }}
        >
          <Typography variant="body2" color="text.secondary">
            No activities linked to this step
          </Typography>
          <Button
            size="small"
            startIcon={<PlusOutlined />}
            onClick={handleAdd}
            sx={{ mt: 1 }}
          >
            Add Activity
          </Button>
        </Box>
      ) : (
        <Stack spacing={1}>
          {activities.map((activity) => (
            <ActivityItem
              key={activity.id}
              activity={activity}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onComplete={handleComplete}
              onCancel={handleCancel}
            />
          ))}
        </Stack>
      )}
      
      {/* Activity Modal (Create/Edit) */}
      <ActivityModal
        open={activityModalOpen}
        onClose={handleModalClose}
        activity={activityToEdit}
        accountId={accountId}
        decisionStepId={stepId}
        decisionCycleId={cycleId}
        onSuccess={handleSuccess}
      />
      
      {/* Complete Modal */}
      {completeModalOpen && (
        <ActivityCompleteModal
          open={completeModalOpen}
          onClose={handleCompleteClose}
          activity={activityToComplete}
          onSuccess={handleSuccess}
        />
      )}
      
      {/* Delete Confirmation */}
      <AlertActivityDelete
        open={deleteModalOpen}
        onClose={handleDeleteClose}
        activity={activityToDelete}
        onSuccess={handleSuccess}
      />
    </Box>
  );
}

DecisionStepActivities.propTypes = {
  stepId: PropTypes.string.isRequired,
  accountId: PropTypes.string,
  cycleId: PropTypes.string
};