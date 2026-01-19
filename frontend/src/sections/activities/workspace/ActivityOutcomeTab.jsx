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

// MUI
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Grid from '@mui/material/Grid';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';

// Project imports
import MainCard from 'components/MainCard';
import {
  completeActivity,
  updateActivity,
  ACTIVITY_OUTCOMES,
  ACTIVITY_OUTCOME_LABELS,
  ACTIVITY_OUTCOME_COLORS,
  ACTIVITY_STATUS_LABELS
} from 'api/accounts/activities';
import {
  useGetDecisionStepsByCycle,
  STATUS_COLORS,
  STATUS_LABELS
} from 'api/accounts/decisionCycles';
import { displaySuccessSnackbar, displayErrorSnackbar } from 'utils/displayError';

// Navigation
import { useRouter } from 'next/navigation';

// Modals
import ActivityModal from 'sections/accounts/activities/ActivityModal';
import DecisionStepModal from 'sections/accounts/decision-cycles/DecisionStepModal';


// Icons
import CheckCircleOutlined from '@ant-design/icons/CheckCircleOutlined';
import EditOutlined from '@ant-design/icons/EditOutlined';
import CheckOutlined from '@ant-design/icons/CheckOutlined';
import CloseOutlined from '@ant-design/icons/CloseOutlined';
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import BulbOutlined from '@ant-design/icons/BulbOutlined';
import RocketOutlined from '@ant-design/icons/RocketOutlined';

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

function NextStepsSection({ activity, onCreateActivity, onCreateStep }) {
  const router = useRouter();
  const hasLinkedStep = Boolean(activity?.decision_step);
  const hasNextActivity = Boolean(activity?.next_activity);
  const hasCycle = Boolean(activity?.decision_cycle);

  // Fetch existing steps for the cycle
  const { steps, stepsLoading } = useGetDecisionStepsByCycle(activity?.decision_cycle);

  // Navigate to step workspace
  const handleStepClick = (stepId) => {
    router.push(`/decision-steps/${stepId}`);
  };

  return (
    <SectionCard title="Next Steps" icon={RocketOutlined}>
      <Stack spacing={2}>
        {/* Show existing next activity if present */}
        {hasNextActivity && (
          <Alert severity="info" sx={{ mb: 1 }}>
            A follow-up activity is already linked to this activity.
          </Alert>
        )}

        {/* Quick action buttons */}
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
        </Stack>

        <Divider sx={{ my: 1 }} />

        {/* Decision Step section */}
        <Box>
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1.5 }}>
            {hasCycle ? (
              <Button
                variant="text"
                size="small"
                startIcon={<PlusOutlined />}
                onClick={onCreateStep}
                color="secondary"
              >
                Add Decision Step
              </Button>
            ) : (
              <Typography variant="body2" color="text.secondary">
                Link this activity to a Decision Cycle to create steps.
              </Typography>
            )}
            {hasLinkedStep && (
              <Chip
                label={`Current: ${activity.decision_step_detail?.name || 'Step'}`}
                size="small"
                variant="filled"
                color="primary"
                onClick={() => handleStepClick(activity.decision_step)}
                sx={{ cursor: 'pointer' }}
              />
            )}
          </Stack>

          {/* Existing steps in cycle */}
          {hasCycle && !stepsLoading && steps.length > 0 && (
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                Steps in this cycle ({steps.length}):
              </Typography>
              <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
                {steps.map((step) => (
                  <Chip
                    key={step.id}
                    label={step.name}
                    size="small"
                    variant={step.id === activity?.decision_step ? 'filled' : 'outlined'}
                    color={STATUS_COLORS[step.status] || 'default'}
                    onClick={() => handleStepClick(step.id)}
                    sx={{ 
                      cursor: 'pointer',
                      mb: 0.5,
                      '&:hover': { opacity: 0.8 }
                    }}
                  />
                ))}
              </Stack>
            </Box>
          )}
        </Box>

        {/* No next step option - Stub for now */}
        <Typography variant="caption" color="text.secondary" sx={{ mt: 1 }}>
          No follow-up needed? Complete the activity with the appropriate outcome below.
        </Typography>
      </Stack>
    </SectionCard>
  );
}

NextStepsSection.propTypes = {
  activity: PropTypes.object,
  onCreateActivity: PropTypes.func.isRequired,
  onCreateStep: PropTypes.func.isRequired
};

// ==============================|| RESULT SECTION ||============================== //

function ResultSection({ activity, onComplete, onUpdate }) {
  const [selectedOutcome, setSelectedOutcome] = useState(activity?.outcome || '');
  const [completing, setCompleting] = useState(false);

  const isCompleted = activity?.status === 'COMPLETED';
  const isCancelled = activity?.status === 'CANCELLED';
  const canComplete = !isCompleted && !isCancelled;

  const handleComplete = async () => {
    if (!selectedOutcome) {
      displayErrorSnackbar('Please select an outcome');
      return;
    }

    setCompleting(true);
    try {
      const result = await completeActivity(activity.id, {
        outcome: selectedOutcome,
        outcome_notes: activity.outcome_notes || null
      });

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
        </Stack>
      ) : isCancelled ? (
        <Alert severity="warning">
          This activity has been cancelled
        </Alert>
      ) : (
        <Stack spacing={2}>
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
  onComplete: PropTypes.func,
  onUpdate: PropTypes.func
};

// ==============================|| ACTIVITY OUTCOME TAB ||============================== //

export default function ActivityOutcomeTab({ activity, onSave, onUpdate }) {
  const [activityModalOpen, setActivityModalOpen] = useState(false);
  const [activityModalType, setActivityModalType] = useState(null);
  const [stepModalOpen, setStepModalOpen] = useState(false);
  const [createdStep, setCreatedStep] = useState(null);
  const [linkConfirmOpen, setLinkConfirmOpen] = useState(false);
  const [linking, setLinking] = useState(false);

  // Handle create follow-up activity
  const handleCreateActivity = (activityType) => {
    setActivityModalType(activityType);
    setActivityModalOpen(true);
  };

  // Handle create decision step
  const handleCreateStep = () => {
    setStepModalOpen(true);
  };

  // Close modals
  const handleActivityModalClose = () => {
    setActivityModalOpen(false);
    setActivityModalType(null);
  };

  const handleStepModalClose = () => {
    setStepModalOpen(false);
  };

  const handleLinkConfirmClose = () => {
    setLinkConfirmOpen(false);
    setCreatedStep(null);
  };

  // Success handlers
  const handleActivitySuccess = () => {
    handleActivityModalClose();
    onUpdate?.();
    displaySuccessSnackbar('Follow-up activity created');
  };

  const handleStepSuccess = (stepData) => {
    handleStepModalClose();
    onUpdate?.();
    displaySuccessSnackbar('Decision step created');
    
    // If activity is not already linked to a step, offer to link
    if (!activity?.decision_step && stepData?.id) {
      setCreatedStep(stepData);
      setLinkConfirmOpen(true);
    }
  };

  // Link activity to newly created step
  const handleLinkToStep = async () => {
    if (!createdStep?.id) return;
    
    setLinking(true);
    try {
      const result = await updateActivity(activity.id, {
        decision_step_id: createdStep.id
      });
      
      if (result.success) {
        displaySuccessSnackbar(`Activity linked to "${createdStep.name}"`);
        onUpdate?.();
      } else {
        displayErrorSnackbar(result.error || 'Failed to link activity');
      }
    } catch (error) {
      displayErrorSnackbar('An error occurred');
    } finally {
      setLinking(false);
      handleLinkConfirmClose();
    }
  };

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Left Column - Key Takeaways + Next Steps */}
        <Grid item xs={12} md={8}>
          <Stack spacing={3}>
            <KeyTakeawaysSection activity={activity} onSave={onSave} />
            <NextStepsSection
              activity={activity}
              onCreateActivity={handleCreateActivity}
              onCreateStep={handleCreateStep}
            />
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
        onSuccess={handleActivitySuccess}
      />

      {/* Step Modal - Create new decision step */}
      {activity?.decision_cycle && (
        <DecisionStepModal
          open={stepModalOpen}
          modalToggler={setStepModalOpen}
          cycleId={activity.decision_cycle}
          defaultStage={null}
          onSuccess={handleStepSuccess}
        />
      )}

      {/* Link Confirmation Dialog */}
      <Dialog
        open={linkConfirmOpen}
        onClose={handleLinkConfirmClose}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Link to this activity?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Do you want to link this activity to the newly created step "{createdStep?.name}"?
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleLinkConfirmClose} disabled={linking}>
            No, skip
          </Button>
          <Button 
            onClick={handleLinkToStep} 
            variant="contained" 
            disabled={linking}
            autoFocus
          >
            {linking ? 'Linking...' : 'Yes, link it'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}

ActivityOutcomeTab.propTypes = {
  activity: PropTypes.object.isRequired,
  onSave: PropTypes.func.isRequired,
  onUpdate: PropTypes.func
};