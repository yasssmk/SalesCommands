// frontend/src/sections/accounts/decision-cycles/DecisionCycleTimeline.jsx
/**
 * Decision Cycle Timeline Component
 * 
 * Displays a horizontal timeline of decision steps organized by stages.
 * Uses MUI Stepper as base with heavy customization.
 * 
 * Features:
 * - 5 fixed stages as column headers
 * - Steps displayed under their assigned stage
 * - Color-coded status indicators
 * - Hover for quick preview (popover)
 * - Click for full edit modal
 * - Add step button per stage
 */

'use client';

import PropTypes from 'prop-types';
import { useMemo, useState } from 'react';

// material-ui
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';

// icons
import PlusOutlined from '@ant-design/icons/PlusOutlined';
import CheckCircleFilled from '@ant-design/icons/CheckCircleFilled';
import CloseCircleFilled from '@ant-design/icons/CloseCircleFilled';
import ClockCircleOutlined from '@ant-design/icons/ClockCircleOutlined';
import SyncOutlined from '@ant-design/icons/SyncOutlined';
import PauseCircleOutlined from '@ant-design/icons/PauseCircleOutlined';
import MinusCircleOutlined from '@ant-design/icons/MinusCircleOutlined';

// project imports
import DecisionStepNode from './DecisionStepNode';
import DecisionStepPreview from './DecisionStepPreview';
import { DECISION_STAGES, STAGE_ORDER, DECISION_STEP_STATUSES } from 'api/accounts/decisionCycles';

// ==============================|| STAGE LABELS ||============================== //

const STAGE_LABELS = {
  EXPLORATION: 'Exploration',
  CRITERIA_VALIDATION: 'Criteria Validation',
  SOLUTION_CONFIRMATION: 'Solution Confirmation',
  BUSINESS_VALIDATION: 'Business Validation',
  FORMALIZATION: 'Formalization'
};

const STAGE_DESCRIPTIONS = {
  EXPLORATION: 'Initial discovery and need identification',
  CRITERIA_VALIDATION: 'Defining and validating decision criteria',
  SOLUTION_CONFIRMATION: 'Technical and functional validation',
  BUSINESS_VALIDATION: 'Budget and business case approval',
  FORMALIZATION: 'Contract and legal finalization'
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
  }
};

// ==============================|| STAGE COLUMN ||============================== //

/**
 * Single stage column component
 */
function StageColumn({ 
  stage, 
  steps, 
  onAddStep, 
  onStepClick, 
  onStepHover,
  hoveredStepId 
}) {
  const theme = useTheme();
  const stageSteps = steps.filter(step => step.stage === stage);
  const validatedCount = stageSteps.filter(s => s.status === 'VALIDATED').length;
  
  return (
    <Paper
      elevation={0}
      sx={{
        flex: 1,
        minWidth: 200,
        maxWidth: 280,
        bgcolor: 'background.default',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}
    >
      {/* Stage Header */}
      <Box
        sx={{
          p: 1.5,
          bgcolor: 'grey.50',
          borderBottom: '1px solid',
          borderColor: 'divider'
        }}
      >
        <Stack spacing={0.5}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle2" fontWeight={600}>
              {STAGE_LABELS[stage]}
            </Typography>
            {stageSteps.length > 0 && (
              <Chip
                size="small"
                label={`${validatedCount}/${stageSteps.length}`}
                color={validatedCount === stageSteps.length && stageSteps.length > 0 ? 'success' : 'default'}
                sx={{ height: 20, fontSize: '0.7rem' }}
              />
            )}
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ display: { xs: 'none', md: 'block' } }}>
            {STAGE_DESCRIPTIONS[stage]}
          </Typography>
        </Stack>
      </Box>
      
      {/* Steps List */}
      <Box
        sx={{
          flex: 1,
          p: 1.5,
          minHeight: 120,
          display: 'flex',
          flexDirection: 'column',
          gap: 1
        }}
      >
        {stageSteps.length === 0 ? (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
          >
            <Typography variant="caption" color="text.disabled">
              No steps yet
            </Typography>
          </Box>
        ) : (
          stageSteps.map((step) => (
            <DecisionStepNode
              key={step.id}
              step={step}
              statusConfig={STATUS_CONFIG[step.status]}
              onClick={() => onStepClick(step)}
              onMouseEnter={(e) => onStepHover(step, e.currentTarget)}
              onMouseLeave={() => onStepHover(null, null)}
              isHovered={hoveredStepId === step.id}
            />
          ))
        )}
      </Box>
      
      {/* Add Step Button */}
      <Box sx={{ p: 1, borderTop: '1px solid', borderColor: 'divider' }}>
        <Button
          size="small"
          startIcon={<PlusOutlined />}
          onClick={() => onAddStep(stage)}
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
          Add Step
        </Button>
      </Box>
    </Paper>
  );
}

StageColumn.propTypes = {
  stage: PropTypes.string.isRequired,
  steps: PropTypes.array.isRequired,
  onAddStep: PropTypes.func.isRequired,
  onStepClick: PropTypes.func.isRequired,
  onStepHover: PropTypes.func.isRequired,
  hoveredStepId: PropTypes.string
};

// ==============================|| DECISION CYCLE TIMELINE ||============================== //

/**
 * Main Timeline Component
 * 
 * @param {Object} props
 * @param {Object} props.cycle - Decision cycle data with steps
 * @param {Function} props.onAddStep - Callback when add step clicked (receives stage)
 * @param {Function} props.onEditStep - Callback when step clicked for edit
 * @param {Function} props.onStatusChange - Callback when step status changed
 * @param {boolean} props.loading - Loading state
 */
export default function DecisionCycleTimeline({
  cycle,
  onAddStep,
  onEditStep,
  onStatusChange,
  loading = false
}) {
  const theme = useTheme();
  
  // Hover state for preview popover
  const [hoveredStep, setHoveredStep] = useState(null);
  const [anchorEl, setAnchorEl] = useState(null);
  
  // Get steps from cycle
  const steps = useMemo(() => {
    return cycle?.steps || [];
  }, [cycle]);
  
  // Summary stats
  const stats = useMemo(() => {
    const total = steps.length;
    const validated = steps.filter(s => s.status === 'VALIDATED').length;
    const rejected = steps.filter(s => s.status === 'REJECTED').length;
    const inProgress = steps.filter(s => 
      s.status === 'IN_PROGRESS' || s.status === 'PENDING_CLIENT' || s.status === 'IN_CHASING'
    ).length;
    
    return { total, validated, rejected, inProgress };
  }, [steps]);
  
  // Handlers
  const handleStepClick = (step) => {
    setHoveredStep(null);
    setAnchorEl(null);
    onEditStep?.(step);
  };
  
  const handleStepHover = (step, element) => {
    setHoveredStep(step);
    setAnchorEl(element);
  };
  
  const handleAddStep = (stage) => {
    onAddStep?.(stage);
  };
  
  // ==============================|| RENDER ||============================== //
  
  return (
    <Box>
      {/* Timeline Header with Stats */}
      <Stack 
        direction="row" 
        justifyContent="space-between" 
        alignItems="center" 
        sx={{ mb: 2 }}
      >
        <Stack direction="row" spacing={2} alignItems="center">
          <Typography variant="h6">
            Decision Timeline
          </Typography>
          {stats.total > 0 && (
            <Stack direction="row" spacing={1}>
              <Chip 
                size="small" 
                label={`${stats.validated} validated`} 
                color="success" 
                variant="outlined"
              />
              {stats.inProgress > 0 && (
                <Chip 
                  size="small" 
                  label={`${stats.inProgress} in progress`} 
                  color="info" 
                  variant="outlined"
                />
              )}
              {stats.rejected > 0 && (
                <Chip 
                  size="small" 
                  label={`${stats.rejected} rejected`} 
                  color="error" 
                  variant="outlined"
                />
              )}
            </Stack>
          )}
        </Stack>
        
        {cycle?.estimated_timeline_days && (
          <Typography variant="body2" color="text.secondary">
            Est. {cycle.estimated_timeline_days} days
          </Typography>
        )}
      </Stack>
      
      {/* Stage Columns */}
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
        {STAGE_ORDER.map((stage) => (
          <StageColumn
            key={stage}
            stage={stage}
            steps={steps}
            onAddStep={handleAddStep}
            onStepClick={handleStepClick}
            onStepHover={handleStepHover}
            hoveredStepId={hoveredStep?.id}
          />
        ))}
      </Box>
      
      {/* Preview Popover */}
      <DecisionStepPreview
        step={hoveredStep}
        anchorEl={anchorEl}
        onClose={() => {
          setHoveredStep(null);
          setAnchorEl(null);
        }}
        statusConfig={hoveredStep ? STATUS_CONFIG[hoveredStep.status] : null}
      />
    </Box>
  );
}

DecisionCycleTimeline.propTypes = {
  cycle: PropTypes.shape({
    id: PropTypes.string,
    name: PropTypes.string,
    steps: PropTypes.array,
    estimated_timeline_days: PropTypes.number
  }),
  onAddStep: PropTypes.func,
  onEditStep: PropTypes.func,
  onStatusChange: PropTypes.func,
  loading: PropTypes.bool
};