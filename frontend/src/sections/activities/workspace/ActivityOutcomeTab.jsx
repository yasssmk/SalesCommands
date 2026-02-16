// frontend/src/sections/activities/workspace/ActivityOutcomeTab.jsx
/**
 * Activity Outcome Tab Component
 * 
 * Post-activity workflow tab with 3 fixed sections:
 * 1. Key Takeaways - Notes capture + signals CTA stub
 * 2. Next Steps - Create follow-up Activity/Step or mark "No next step"
 * 3. Result - Outcome selection + Complete action
 * 
 * Designed for fast, non-form-like post-call workflow.
 */




'use client';

import { useState } from 'react';
import PropTypes from 'prop-types';
import { useTheme } from '@mui/material/styles';

// MUI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Grid from '@mui/material/Grid';
import IconButton from '@mui/material/IconButton';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';

// Project imports
import {
  completeActivity,
  updateActivity,
  ACTIVITY_OUTCOME_LABELS,
  ACTIVITY_OUTCOME_COLORS,
  ACTIVITY_TYPE_LABELS,
  ACTIVITY_STATUS_LABELS,
  ACTIVITY_STATUS_COLORS
} from 'api/accounts/activities';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

// Navigation
import { useRouter } from 'next/navigation'

// Modals
import ActivityModal from 'sections/accounts/activities/ActivityModal';

// Icons
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import BulbOutlined from '@ant-design/icons/BulbOutlined';
import RocketOutlined from '@ant-design/icons/RocketOutlined';
import StopOutlined from '@ant-design/icons/StopOutlined';
import LinkOutlined from '@ant-design/icons/LinkOutlined';
import WarningOutlined from '@ant-design/icons/WarningOutlined';
import TrophyOutlined from '@ant-design/icons/TrophyOutlined';
import CloseCircleOutlined from '@ant-design/icons/CloseCircleOutlined';
import PauseCircleOutlined from '@ant-design/icons/PauseCircleOutlined';

// ==============================|| SECTION CARD WRAPPER ||============================== //

function SectionCard({ title, icon: Icon, children, action }) {
  const theme = useTheme();
  
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            {Icon && <Icon style={{ fontSize: theme.iconSizes.md, color: '#8c8c8c' }} />}
            <Typography variant="subtitle1" fontWeight={600}>
              {title}
            </Typography>
          </Stack>
          {action}
        </Stack>
        {children}
      </CardContent>
    </Card>
  );
}

SectionCard.propTypes = {
  title: PropTypes.string.isRequired,
  icon: PropTypes.elementType,
  children: PropTypes.node,
  action: PropTypes.node
};

// ==============================|| KEY TAKEAWAYS SECTION ||============================== //

function KeyTakeawaysSection({ activity, onSave, isLocked = false }){
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(activity?.outcome_notes || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (value === (activity?.outcome_notes || '')) {
      setEditing(false);
      return;
    }
    setSaving(true);
    const success = await onSave('outcome_notes', value);
    setSaving(false);
    if (success) {
      setEditing(false);
    }
  };

  const handleCancel = () => {
    setValue(activity?.outcome_notes || '');
    setEditing(false);
  };

  return (
    <SectionCard
      title="Key Takeaways"
      icon={BulbOutlined}
      action={
        !editing && (
          <Button
            size="small"
            startIcon={<PlusOutlined />}
            disabled
            sx={{ opacity: 0.5 }}
          >
            Add Signal (Coming Soon)
          </Button>
        )
      }
    >
      {editing ? (
        <Stack spacing={1.5}>
          <TextField
            multiline
            rows={4}
            fullWidth
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Capture key information from this activity..."
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
              disabled={saving}
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
            minHeight: 80,
            '&:hover': {
              bgcolor: isLocked ? 'action.hover' : 'action.selected'
            }
          }}
        >
          {activity?.outcome_notes ? (
            <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
              {activity.outcome_notes}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Click to add notes about this activity...
            </Typography>
          )}
        </Box>
      )}
    </SectionCard>
  );
}

KeyTakeawaysSection.propTypes = {
  activity: PropTypes.object,
  onSave: PropTypes.func.isRequired
};

// ==============================|| ACTIVITY MINI CARD (Reusable) ||============================== //

function ActivityMiniCard({ activity: activityItem, onNavigate, onUnlink, showUnlink = false }) {
  const theme = useTheme();
  
  // Format date helper
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleDateString();
  };

  const displayDate = activityItem.scheduled_date || activityItem.due_date;
  const stepName = activityItem.decision_step_name;

  return (
    <Card 
      variant="outlined" 
      sx={{ 
        p: 1.5, 
        cursor: 'pointer',
        transition: 'all 0.15s ease-in-out',
        '&:hover': { 
          bgcolor: 'action.hover',
          borderColor: theme.palette.primary.light
        }
      }}
      onClick={() => onNavigate(activityItem.id)}
    >
      <Stack spacing={1}>
        {/* Row 1: Type + Title */}
        <Stack direction="row" spacing={1.5} alignItems="center">
          <Chip
            label={ACTIVITY_TYPE_LABELS[activityItem.activity_type] || activityItem.activity_type}
            size="small"
            variant="outlined"
            sx={{ minWidth: 80 }}
          />
          <Typography variant="body2" fontWeight={500} noWrap sx={{ flex: 1 }}>
            {activityItem.title}
          </Typography>
          {showUnlink && (
            <IconButton 
              size="small" 
              onClick={(e) => {
                e.stopPropagation();
                onUnlink?.();
              }}
              sx={{ ml: 'auto' }}
            >
              <CloseOutlined style={{ fontSize: theme.iconSizes.sm, }} />
            </IconButton>
          )}
        </Stack>
        
        {/* Row 2: Meta info (step, date, status) */}
        <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          {stepName && (
            <Chip
              label={stepName}
              size="small"
              variant="filled"
              sx={{ 
                height: 20, 
                fontSize: '0.7rem',
                bgcolor: theme.palette.grey[100],
                color: theme.palette.text.secondary
              }}
            />
          )}
          {displayDate && (
            <Typography variant="caption" color="text.secondary">
              {formatDate(displayDate)}
            </Typography>
          )}
          <Chip
            label={activityItem.is_overdue ? 'Overdue' : (ACTIVITY_STATUS_LABELS[activityItem.status] || activityItem.status)}
            size="small"
            color={activityItem.is_overdue ? 'error' : (ACTIVITY_STATUS_COLORS[activityItem.status] || 'default')}
            sx={{ height: 20, fontSize: '0.7rem' }}
          />
        </Stack>
      </Stack>
    </Card>
  );
}

ActivityMiniCard.propTypes = {
  activity: PropTypes.object.isRequired,
  onNavigate: PropTypes.func.isRequired,
  onUnlink: PropTypes.func,
  showUnlink: PropTypes.bool
};

// ==============================|| NEXT STEPS SECTION ||============================== //

function NextStepsSection({ activity, onCreateActivity, onUpdate,  isLocked = false }) {
  const router = useRouter();
  const theme = useTheme();
  
  // Check if activity belongs to a sequence (Decision Cycle or future Campaign)
  // Future-ready: add || Boolean(activity?.campaign) when campaign FK is added
  const isInSequence = Boolean(activity?.decision_cycle);
  
  // Get next activities from sequence_context (calculated by backend)
  const sequenceContext = activity?.sequence_context;
  const nextActivities = sequenceContext?.next_activities || [];
  const hasNextActivity = nextActivities.length > 0;
  
  // Sequence position info
  const isLastInSequence = sequenceContext?.position === sequenceContext?.total;
  
  // Check effective next step status from API
  const effectiveHasNextStep = activity?.effective_has_next_step;

  // Navigate to activity workspace
  const handleActivityClick = (activityId) => {
    if (activityId) {
      router.push(`/activities/${activityId}`);
    }
  };

  // ========== DISABLED STATE: Not in a sequence ==========
  if (!isInSequence) {
    return (
      <SectionCard title="Next Steps" icon={RocketOutlined}>
        <Box
          sx={{
            p: 3,
            borderRadius: 1,
            bgcolor: theme.palette.grey[50],
            border: '1px dashed',
            borderColor: theme.palette.grey[200],
            opacity: 0.7,
            textAlign: 'center'
          }}
        >
          <LinkOutlined style={{ fontSize: theme.iconSizes.lg, color: theme.palette.grey[400], marginBottom: 8 }} />
          <Typography variant="body2" color="text.disabled" sx={{ mb: 0.5 }}>
            Next step planning requires a sequence.
          </Typography>
          <Typography variant="caption" color="text.disabled">
            Link this activity to a Decision Cycle from the Overview tab to enable next steps.
          </Typography>
        </Box>
      </SectionCard>
    );
  }

  // ========== ACTIVE STATE: In a sequence ==========
  return (
    <SectionCard title="Next Steps" icon={RocketOutlined}>
      <Stack spacing={2}>
        {/* Next Activities List (ordered by sequence) */}
        {hasNextActivity && (
          <Box>
            <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
              Upcoming in sequence ({nextActivities.length})
            </Typography>
            <Stack spacing={1}>
              {nextActivities.map((nextAct, index) => (
                <ActivityMiniCard
                  key={nextAct.id}
                  activity={nextAct}
                  onNavigate={handleActivityClick}
                />
              ))}
            </Stack>
          </Box>
        )}

        {/* Create follow-up buttons (hidden when locked) */}
        {!isLocked && (
          <Box>
            {hasNextActivity && (
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                Create additional follow-up
              </Typography>
            )}
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Button
                variant="outlined"
                size="small"
                startIcon={<PlusOutlined />}
                onClick={() => onCreateActivity('MEETING')}
              >
                Meeting
              </Button>
              <Button
                variant="outlined"
                size="small"
                startIcon={<PlusOutlined />}
                onClick={() => onCreateActivity('CALL')}
              >
                Call
              </Button>
              <Button
                variant="outlined"
                size="small"
                startIcon={<PlusOutlined />}
                onClick={() => onCreateActivity('EMAIL')}
              >
                Email
              </Button>
              <Button
                variant="outlined"
                size="small"
                startIcon={<PlusOutlined />}
                onClick={() => onCreateActivity('TASK')}
              >
                Task
              </Button>
            </Stack>
          </Box>
        )}

        {/* Empty state hint - only if no next activities */}
        {!hasNextActivity && !isLocked && (
          <Box
            sx={{
              p: 2,
              borderRadius: 1,
              bgcolor: theme.palette.grey[50],
              border: '1px dashed',
              borderColor: theme.palette.grey[300]
            }}
          >
            <Typography variant="body2" color="text.secondary" textAlign="center">
              {isLastInSequence
                ? 'This is the last activity in the sequence. Create a follow-up to continue the cycle.'
                : 'No activities scheduled after this one. Create a follow-up to continue.'
              }
            </Typography>
          </Box>
        )}
      </Stack>
    </SectionCard>
  );
}

NextStepsSection.propTypes = {
  activity: PropTypes.object,
  onCreateActivity: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};

// ==============================|| RESULT SECTION ||============================== //

function ResultSection({ activity, onUpdate }) {
  const theme = useTheme();
  const [selectedOutcome, setSelectedOutcome] = useState(activity?.outcome || '');
  const [outcomeNotes, setOutcomeNotes] = useState(activity?.outcome_notes || '');
  const [completing, setCompleting] = useState(false);

  const isCompleted = activity?.status === 'COMPLETED';
  const isCancelled = activity?.status === 'CANCELLED';

  // Completion requires only an outcome selection
  const canComplete = !!selectedOutcome;

  const handleComplete = async () => {
    if (!selectedOutcome) {
      displayErrorSnackbar({
        message: 'Please select an outcome',
        status: 400
      });
      return;
    }
    
    setCompleting(true);
    try {
      const payload = {
        outcome: selectedOutcome,
        outcome_notes: outcomeNotes.trim() || null
      };
      
      const result = await completeActivity(activity.id, payload);
      
      if (result.success) {
        displaySuccessSnackbar('Activity completed successfully');
        onUpdate?.();
      } else {
        displayErrorSnackbar({
          message: result.error || 'Failed to complete activity',
          status: result.status
        });
      }
    } catch (err) {
      displayErrorSnackbar({
        message: err?.message || 'An unexpected error occurred',
        status: 500
      });
    } finally {
      setCompleting(false);
    }
  };

  return (
    <SectionCard title="Result" icon={CheckCircleOutlined}>
      {isCompleted ? (
        <Stack spacing={2}>
          <Alert severity="success">
            Activity completed
          </Alert>
          <Stack direction="row" spacing={1} alignItems="center">
            <Typography variant="body2" color="text.secondary">
              Outcome:
            </Typography>
            <Chip
              label={ACTIVITY_OUTCOME_LABELS[activity.outcome] || activity.outcome}
              color={ACTIVITY_OUTCOME_COLORS[activity.outcome] || 'default'}
              size="small"
            />
          </Stack>
          {activity.outcome_notes && (
            <Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
                Notes:
              </Typography>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap' }}>
                {activity.outcome_notes}
              </Typography>
            </Box>
          )}
        </Stack>
      ) : isCancelled ? (
        <Alert severity="warning">
          This activity has been cancelled
        </Alert>
      ) : (
        <Stack spacing={2}>
          {/* Outcome Select */}
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Select outcome
            </Typography>
            <Select
              value={selectedOutcome}
              onChange={(e) => setSelectedOutcome(e.target.value)}
              fullWidth
              size="small"
              displayEmpty
            >
              <MenuItem value="" disabled>
                <em>Choose an outcome...</em>
              </MenuItem>
              {Object.entries(ACTIVITY_OUTCOME_LABELS).map(([value, label]) => (
                <MenuItem key={value} value={value}>
                  {label}
                </MenuItem>
              ))}
            </Select>
          </Box>

          {/* Outcome Notes */}
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Outcome notes
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={2}
              size="small"
              placeholder="Add notes about the outcome..."
              value={outcomeNotes}
              onChange={(e) => setOutcomeNotes(e.target.value)}
            />
          </Box>        

          {/* Complete Button */}
          <Button
            variant="contained"
            color="success"
            startIcon={<CheckCircleOutlined />}
            onClick={handleComplete}
            disabled={!canComplete || completing}
            fullWidth
          >
            {completing ? 'Completing...' : 'Complete Activity'}
          </Button>
        </Stack>
      )}
    </SectionCard>
  );
}

ResultSection.propTypes = {
  activity: PropTypes.object,
  onUpdate: PropTypes.func
};

// ==============================|| ACTIVITY OUTCOME TAB ||============================== //

export default function ActivityOutcomeTab({ activity, onSave, onUpdate, isLocked = false }) {
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityModalType, setActivityModalType] = useState(null);

  // Handle create follow-up activity
  const handleCreateActivity = (activityType) => {
    setActivityModalType(activityType);
    setActivityModalOpen(true);
  };

  // Close activity modal
  const handleActivityModalClose = () => {
    setActivityModalOpen(false);
    setActivityModalType(null);
  };

  // Success handler for activity creation
  const handleActivitySuccess = async () => {
    handleActivityModalClose();
    onUpdate?.();
    displaySuccessSnackbar('Follow-up activity created');
  };


  return (
    <Box>
      <Grid container spacing={3}>
        {/* Left Column - Next Steps + Key Takeaways */}
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>
            <NextStepsSection
              activity={activity}
              onCreateActivity={handleCreateActivity}
              onUpdate={onUpdate}
              isLocked={isLocked}
            />
            <KeyTakeawaysSection activity={activity} onSave={onSave} isLocked={isLocked} />
          </Stack>
        </Grid>

        {/* Right Column - Result */}
        <Grid item xs={12} md={4}>
          <ResultSection
            activity={activity}
            onUpdate={onUpdate}
          />
        </Grid>
      </Grid>

      {/* Activity Modal - Create follow-up activity */}
      <ActivityModal
        open={activityModalOpen}
        onClose={handleActivityModalClose}
        activity={null}
        accountId={activity?.account}
        decisionStepId={activity?.decision_step || null}
        decisionCycleId={activity?.decision_cycle || null}
        defaultActivityType={activityModalType}
        previousActivityId={activity?.id}
        onSuccess={handleActivitySuccess}
      />
    </Box>
  );
}

ActivityOutcomeTab.propTypes = {
  activity: PropTypes.object.isRequired,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func,
  isLocked: PropTypes.bool
};