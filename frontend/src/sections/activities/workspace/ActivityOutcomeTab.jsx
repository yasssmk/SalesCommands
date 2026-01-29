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
  markNoNextStep,
  markNextStepAgreed,
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
import LinkExistingActivityModal from './LinkExistingActivityModal';

// Icons
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import BulbOutlined from '@ant-design/icons/BulbOutlined';
import RocketOutlined from '@ant-design/icons/RocketOutlined';
import StopOutlined from '@ant-design/icons/StopOutlined';
import LinkOutlined from '@ant-design/icons/LinkOutlined';

// ==============================|| SECTION CARD WRAPPER ||============================== //

function SectionCard({ title, icon: Icon, children, action }) {
  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
          <Stack direction="row" spacing={1} alignItems="center">
            {Icon && <Icon style={{ fontSize: 18, color: '#8c8c8c' }} />}
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

function KeyTakeawaysSection({ activity, onSave }) {
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
          onClick={() => setEditing(true)}
          sx={{
            p: 2,
            borderRadius: 1,
            bgcolor: 'action.hover',
            cursor: 'pointer',
            minHeight: 80,
            '&:hover': {
              bgcolor: 'action.selected'
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

// ==============================|| NEXT STEPS SECTION ||============================== //

function NextStepsSection({ activity, onCreateActivity, onLinkExisting, onUpdate }) {
  const router = useRouter();
  const theme = useTheme();
  
  // Check if activity belongs to a decision cycle
  const hasCycle = Boolean(activity?.decision_cycle);
  
  // Get next activities from sequence_context (calculated) or legacy field (manual)
  const sequenceContext = activity?.sequence_context;
  const nextActivitiesFromSequence = sequenceContext?.next_activities || [];
  const legacyNextActivity = activity?.next_activity_info;
  
  // Determine what to display
  const nextActivities = hasCycle 
    ? nextActivitiesFromSequence 
    : (legacyNextActivity ? [legacyNextActivity] : []);
  const hasNextActivity = nextActivities.length > 0;
  
  // Sequence position info
  const position = sequenceContext?.position;
  const total = sequenceContext?.total;
  const isLastInSequence = position === total;

  // Navigate to activity workspace
  const handleActivityClick = (activityId) => {
    if (activityId) {
      router.push(`/activities/${activityId}`);
    }
  };

  // Unlink next activity (only for standalone activities without cycle)
  const handleUnlinkActivity = async () => {
    if (!activity?.id || hasCycle) return;
    
    try {
      const result = await updateActivity(activity.id, {
        next_activity_id: null
      });
      if (result.success) {
        displaySuccessSnackbar('Next activity unlinked');
        onUpdate?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to unlink activity');
      }
    } catch (error) {
      displayErrorSnackbar('An error occurred');
    }
  };

  // Format date helper
  const formatDate = (dateStr) => {
    if (!dateStr) return null;
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <SectionCard title="Next Steps" icon={RocketOutlined}>
      <Stack spacing={2}>
        {/* Action buttons row */}
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => onCreateActivity('MEETING')}
          >
            Schedule Meeting
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => onCreateActivity('CALL')}
          >
            Schedule Call
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => onCreateActivity('EMAIL')}
          >
            Send Email
          </Button>
          <Button
            variant="outlined"
            size="small"
            startIcon={<PlusOutlined />}
            onClick={() => onCreateActivity('TASK')}
          >
            Internal Task
          </Button>
          {/* Link Existing only for standalone activities (no cycle) */}
          {!hasCycle && (
            <Button
              variant="outlined"
              size="small"
              color="secondary"
              startIcon={<LinkOutlined />}
              onClick={onLinkExisting}
            >
              Link Existing
            </Button>
          )}
        </Stack>

        {/* Next Activities Display */}
        {hasNextActivity && (
          <Box>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {hasCycle ? 'Next in sequence:' : 'Linked next activity:'}
              </Typography>
              {hasCycle && nextActivities.length > 1 && (
                <Chip
                  label={`${nextActivities.length} activities`}
                  size="small"
                  variant="outlined"
                  sx={{ height: 18, fontSize: '0.7rem' }}
                />
              )}
            </Stack>
            
            <Stack spacing={1}>
              {nextActivities.map((nextAct) => (
                <Card 
                  key={nextAct.id}
                  variant="outlined" 
                  sx={{ 
                    p: 1.5, 
                    cursor: 'pointer',
                    '&:hover': { bgcolor: 'action.hover' }
                  }}
                >
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Stack 
                      direction="row" 
                      spacing={1.5} 
                      alignItems="center"
                      onClick={() => handleActivityClick(nextAct.id)}
                      sx={{ flex: 1, cursor: 'pointer' }}
                    >
                      <Chip
                        label={ACTIVITY_TYPE_LABELS[nextAct.activity_type] || nextAct.activity_type}
                        size="small"
                        variant="outlined"
                      />
                      <Typography variant="body2" fontWeight={500}>
                        {nextAct.title}
                      </Typography>
                      {(nextAct.scheduled_date || nextAct.due_date) && (
                        <Typography variant="caption" color="text.secondary">
                          {formatDate(nextAct.scheduled_date || nextAct.due_date)}
                        </Typography>
                      )}
                      <Chip
                        label={ACTIVITY_STATUS_LABELS[nextAct.status] || nextAct.status}
                        size="small"
                        color={ACTIVITY_STATUS_COLORS[nextAct.status] || 'default'}
                      />
                    </Stack>
                    {/* Unlink button only for standalone activities (no cycle) */}
                    {!hasCycle && (
                      <IconButton 
                        size="small" 
                        onClick={(e) => {
                          e.stopPropagation();
                          handleUnlinkActivity();
                        }}
                        sx={{ ml: 1 }}
                      >
                        <CloseOutlined />
                      </IconButton>
                    )}
                  </Stack>
                </Card>
              ))}
            </Stack>
          </Box>
        )}

        {/* Empty state hint */}
        {!hasNextActivity && (
          <Box
            sx={{
              p: 2,
              borderRadius: 1,
              bgcolor: theme.palette.grey[50],
              border: '1px dashed',
              borderColor: theme.palette.grey[300]
            }}
          >
            {hasCycle ? (
              isLastInSequence ? (
                <Typography variant="body2" color="text.secondary" textAlign="center">
                  This is the last activity in the sequence. Create a new activity to continue the cycle.
                </Typography>
              ) : (
                <Typography variant="body2" color="text.secondary" textAlign="center">
                  No activities scheduled after this one in the cycle. Create a follow-up to continue.
                </Typography>
              )
            ) : (
              <Typography variant="body2" color="text.secondary" textAlign="center">
                Create or link a follow-up activity. If completed without a next step, it will be marked as "No next step agreed".
              </Typography>
            )}
          </Box>
        )}
      </Stack>
    </SectionCard>
  );
}

NextStepsSection.propTypes = {
  activity: PropTypes.object,
  onCreateActivity: PropTypes.func.isRequired,
  onLinkExisting: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};

// ==============================|| RESULT SECTION ||============================== //

function ResultSection({ activity, onUpdate }) {
  const [selectedOutcome, setSelectedOutcome] = useState(activity?.outcome || '');
  const [outcomeNotes, setOutcomeNotes] = useState(activity?.outcome_notes || '');
  const [completing, setCompleting] = useState(false);

  const isCompleted = activity?.status === 'COMPLETED';
  const isCancelled = activity?.status === 'CANCELLED';

  // Check if activity has a next step linked
  const hasNextStep = Boolean(activity?.next_activity);

  const handleComplete = async () => {
    if (!selectedOutcome) {
      displayErrorSnackbar('Please select an outcome');
      return;
    }

    setCompleting(true);
    try {
      // Build payload
      const payload = {
        outcome: selectedOutcome,
        outcome_notes: outcomeNotes.trim() || null
      };

      // If no next step is linked, auto-set next_step_agreed to false
      if (!hasNextStep) {
        payload.next_step_agreed = false;
      }

      const result = await completeActivity(activity.id, payload);

      if (result.success) {
        displaySuccessSnackbar('Activity completed successfully');
        onUpdate?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to complete activity');
      }
    } catch (error) {
      displayErrorSnackbar('An error occurred');
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
              rows={3}
              size="small"
              placeholder="Add notes about the outcome..."
              value={outcomeNotes}
              onChange={(e) => setOutcomeNotes(e.target.value)}
            />
          </Box>

          {/* Warning if no next step */}
          {!hasNextStep && (
            <Alert severity="info" icon={false} sx={{ py: 0.5 }}>
              <Typography variant="caption">
                No next step linked. Completing will mark this as "No next step agreed".
              </Typography>
            </Alert>
          )}

          {/* Complete Button */}
          <Button
            variant="contained"
            color="success"
            startIcon={<CheckCircleOutlined />}
            onClick={handleComplete}
            disabled={!selectedOutcome || completing}
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

export default function ActivityOutcomeTab({ activity, onSave, onUpdate }) {
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityModalType, setActivityModalType] = useState(null);
  const [linkModalOpen, setLinkModalOpen] = useState(false);

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
    
    // Auto-set next_step_agreed=true when creating follow-up
    if (activity?.id && activity?.next_step_agreed !== true) {
      try {
        await markNextStepAgreed(activity.id);
      } catch (error) {
        console.error('Failed to mark next step agreed:', error);
      }
    }
    
    onUpdate?.();
    displaySuccessSnackbar('Follow-up activity created');
  };

  // Handle link existing activity
  const handleLinkExisting = () => {
    setLinkModalOpen(true);
  };

  const handleLinkModalClose = () => {
    setLinkModalOpen(false);
  };

  const handleLinkSuccess = () => {
    setLinkModalOpen(false);
    onUpdate?.();
    displaySuccessSnackbar('Activity linked as next step');
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
              onLinkExisting={handleLinkExisting}
              onUpdate={onUpdate}
            />
            <KeyTakeawaysSection activity={activity} onSave={onSave} />
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

      {linkModalOpen && (
        <LinkExistingActivityModal
          open={linkModalOpen}
          onClose={handleLinkModalClose}
          currentActivity={activity}
          onSuccess={handleLinkSuccess}
        />
      )}

    </Box>
  );
}

ActivityOutcomeTab.propTypes = {
  activity: PropTypes.object.isRequired,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};